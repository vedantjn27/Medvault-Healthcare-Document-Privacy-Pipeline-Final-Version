"""Formatting-preserving OOXML and embedded-image destructive redaction."""

from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree
from PIL import Image, ImageDraw, ImageFont

from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.docx_extractor import WORD_NAMESPACE
from app.documents.extractors.types import ExtractedDocument, LayoutToken


XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


class DocxRedactionError(ValueError):
    pass


def _replacement(candidate: DetectionCandidate, verbose: bool) -> str:
    if candidate.replacement_text is not None:
        return candidate.replacement_text
    return f"[REDACTED: {candidate.entity_type}]" if verbose else "[REDACTED]"


def _xml_operations(
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
    verbose: bool,
) -> dict[str, list[tuple[int, int, str]]]:
    operations: dict[str, list[tuple[int, int, str]]] = {}
    for candidate in sorted(candidates, key=lambda item: item.start, reverse=True):
        tokens = [
            token
            for token in extracted.tokens_for(candidate)
            if token.source == "docx_xml" and token.locator is not None
        ]
        if not tokens:
            continue
        grouped: dict[str, list[LayoutToken]] = {}
        for token in tokens:
            grouped.setdefault(token.locator, []).append(token)
        first_locator = min(grouped, key=lambda locator: min(token.start for token in grouped[locator]))
        for locator, locator_tokens in grouped.items():
            start = min(token.local_start for token in locator_tokens)
            end = max(token.local_end or token.local_start + 1 for token in locator_tokens)
            operations.setdefault(locator, []).append(
                (start, end, _replacement(candidate, verbose) if locator == first_locator else "")
            )
    return operations


def _apply_xml_operations(name: str, content: bytes, operations) -> bytes:
    relevant = {key: value for key, value in operations.items() if key.startswith(f"{name}|")}
    if not relevant:
        return content
    root = etree.fromstring(content)
    nodes = root.xpath(".//w:t", namespaces={"w": WORD_NAMESPACE})
    for index, node in enumerate(nodes):
        locator = f"{name}|{index}"
        value = node.text or ""
        for start, end, replacement in sorted(relevant.get(locator, []), reverse=True):
            value = value[:start] + replacement + value[end:]
        node.text = value
        if value.startswith(" ") or value.endswith(" "):
            node.set(XML_SPACE, "preserve")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _redact_image(content: bytes, groups: list[tuple[list[LayoutToken], str]]) -> bytes:
    with Image.open(io.BytesIO(content)) as source:
        image_format = source.format or "PNG"
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for tokens, label in groups:
        boxes = [token.bbox for token in tokens if token.bbox is not None]
        if not boxes:
            continue
        rectangle = (
            int(min(box[0] for box in boxes)),
            int(min(box[1] for box in boxes)),
            int(max(box[2] for box in boxes)),
            int(max(box[3] for box in boxes)),
        )
        draw.rectangle(rectangle, fill="black")
        short_label = label if draw.textlength(label, font=font) <= rectangle[2] - rectangle[0] else "[REDACTED]"
        draw.text((rectangle[0], rectangle[1]), short_label, fill="white", font=font)
    output = io.BytesIO()
    save_format = "JPEG" if image_format.upper() in {"JPEG", "JPG"} else image_format
    image.save(output, format=save_format)
    return output.getvalue()


def redact_docx(
    source: Path,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
    *,
    verbose_labels: bool = False,
) -> int:
    redactions = [item for item in candidates if item.decision == DetectionDecision.AUTO_REDACT]
    for candidate in redactions:
        if not any(
            token.source in {"docx_xml", "docx_image_ocr"}
            for token in extracted.tokens_for(candidate)
        ):
            raise DocxRedactionError("Detected span could not be mapped safely to Word content")
    operations = _xml_operations(extracted, redactions, verbose_labels)
    image_groups: dict[str, list[tuple[list[LayoutToken], str]]] = {}
    for candidate in redactions:
        grouped: dict[str, list[LayoutToken]] = {}
        for token in extracted.tokens_for(candidate):
            if token.source == "docx_image_ocr" and token.locator:
                media_name = token.locator.split("|", 1)[0]
                grouped.setdefault(media_name, []).append(token)
        for name, tokens in grouped.items():
            image_groups.setdefault(name, []).append((tokens, _replacement(candidate, verbose_labels)))

    if redactions and not operations and not image_groups:
        raise DocxRedactionError("Detected spans could not be mapped safely to Word content")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(source) as input_archive, ZipFile(destination, "w", compression=ZIP_DEFLATED) as output_archive:
            for info in input_archive.infolist():
                content = input_archive.read(info.filename)
                if info.filename.endswith(".xml"):
                    content = _apply_xml_operations(info.filename, content, operations)
                if info.filename in image_groups:
                    content = _redact_image(content, image_groups[info.filename])
                output_archive.writestr(info, content)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, DocxRedactionError):
            raise
        raise DocxRedactionError("Word redaction failed") from exc
    return len(redactions)
