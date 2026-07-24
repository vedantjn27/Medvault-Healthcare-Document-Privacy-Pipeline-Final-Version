"""OOXML text-node and embedded-image OCR extraction with exact locators."""

from __future__ import annotations

import io
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import docx2txt
from lxml import etree
from PIL import Image, UnidentifiedImageError
import pytesseract
from pytesseract import Output

from app.documents.extractors.types import ExtractedDocument, LayoutToken
from app.detection.types import StructuralContext


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_PARTS = ("word/document.xml",)


class DocxExtractionError(ValueError):
    pass


def _append_text_node(
    parts: list[str],
    tokens: list[LayoutToken],
    value: str,
    locator: str,
) -> None:
    start = sum(len(part) for part in parts)
    parts.append(value)
    for index, character in enumerate(value):
        tokens.append(
            LayoutToken(
                text=character,
                start=start + index,
                end=start + index + 1,
                locator=locator,
                local_start=index,
                local_end=index + 1,
                source="docx_xml",
            )
        )


def _extract_xml_part(
    name: str,
    content: bytes,
    parts: list[str],
    tokens: list[LayoutToken],
    contexts: list[StructuralContext],
) -> None:
    root = etree.fromstring(content)
    text_nodes = root.xpath(".//w:t", namespaces={"w": WORD_NAMESPACE})
    node_indexes = {node: index for index, node in enumerate(text_nodes)}
    paragraphs = root.xpath(".//w:p", namespaces={"w": WORD_NAMESPACE})
    previous_paragraph: str | None = None
    for paragraph in paragraphs:
        paragraph_nodes = []
        for node in paragraph.xpath(".//w:t", namespaces={"w": WORD_NAMESPACE}):
            nearest_paragraph = next(
                node.iterancestors(tag=f"{{{WORD_NAMESPACE}}}p"),
                None,
            )
            if nearest_paragraph is paragraph:
                paragraph_nodes.append(node)
        if not paragraph_nodes:
            continue
        if parts and not parts[-1].endswith("\n"):
            parts.append("\n")
        paragraph_start = sum(len(part) for part in parts)
        paragraph_text = "".join((node.text or "") for node in paragraph_nodes)
        for node in paragraph_nodes:
            value = node.text or ""
            if value:
                _append_text_node(parts, tokens, value, f"{name}|{node_indexes[node]}")
        paragraph_end = sum(len(part) for part in parts)
        if previous_paragraph and paragraph_end > paragraph_start:
            contexts.append(
                StructuralContext(paragraph_start, paragraph_end, (previous_paragraph,))
            )
        previous_paragraph = paragraph_text


def _extract_image(
    name: str,
    content: bytes,
    parts: list[str],
    tokens: list[LayoutToken],
) -> bool:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            data = pytesseract.image_to_data(image.convert("RGB"), config="--psm 6", output_type=Output.DICT)
    except (UnidentifiedImageError, OSError):
        return False
    found = False
    previous_line: tuple[int, int, int] | None = None
    for index, raw_word in enumerate(data["text"]):
        word = str(raw_word).strip()
        confidence = float(data["conf"][index]) if str(data["conf"][index]) not in {"", "-1"} else -1
        if not word or confidence < 0:
            continue
        found = True
        line = (int(data["block_num"][index]), int(data["par_num"][index]), int(data["line_num"][index]))
        if parts and previous_line is not None and line != previous_line:
            parts.append("\n")
        elif parts and not parts[-1].endswith((" ", "\n")):
            parts.append(" ")
        previous_line = line
        start = sum(len(part) for part in parts)
        parts.append(word)
        left, top = int(data["left"][index]), int(data["top"][index])
        width, height = int(data["width"][index]), int(data["height"][index])
        for character_index, character in enumerate(word):
            x0 = left + width * character_index / max(1, len(word))
            x1 = left + width * (character_index + 1) / max(1, len(word))
            tokens.append(
                LayoutToken(
                    text=character,
                    start=start + character_index,
                    end=start + character_index + 1,
                    bbox=(x0, top, x1, top + height),
                    locator=f"{name}|word:{index}",
                    local_start=character_index,
                    local_end=character_index + 1,
                    source="docx_image_ocr",
                )
            )
    return found


def extract_docx(path: Path, *, tesseract_cmd: Path | None = None) -> ExtractedDocument:
    if tesseract_cmd is not None:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)
    parts: list[str] = []
    tokens: list[LayoutToken] = []
    contexts: list[StructuralContext] = []
    image_entries: list[str] = []
    used_fallback = False
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            xml_parts = [
                name
                for name in names
                if name == "word/document.xml"
                or name.startswith("word/header") and name.endswith(".xml")
                or name.startswith("word/footer") and name.endswith(".xml")
            ]
            for name in sorted(xml_parts, key=lambda item: (item != "word/document.xml", item)):
                _extract_xml_part(name, archive.read(name), parts, tokens, contexts)
            for name in sorted(entry for entry in names if entry.startswith("word/media/")):
                if _extract_image(name, archive.read(name), parts, tokens):
                    image_entries.append(name)
    except (BadZipFile, etree.XMLSyntaxError, KeyError) as exc:
        raise DocxExtractionError("Word document structure is invalid") from exc

    if not parts:
        try:
            fallback = docx2txt.process(str(path)) or ""
        except Exception as exc:
            raise DocxExtractionError("Word document extraction failed") from exc
        if fallback:
            parts.append(fallback)
            used_fallback = True
    return ExtractedDocument(
        text="".join(parts),
        tokens=tokens,
        structural_contexts=contexts,
        metadata={"embedded_images_with_text": image_entries, "used_docx2txt_fallback": used_fallback},
    )
