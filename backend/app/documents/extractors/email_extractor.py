"""EML/MBOX header, body, and recursively routed attachment extraction."""

from __future__ import annotations

import mailbox
import tempfile
from dataclasses import dataclass, replace
from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import Path

from app.detection.types import StructuralContext
from app.documents.extractors.dicom_extractor import extract_dicom
from app.documents.extractors.docx_extractor import extract_docx
from app.documents.file_types import FileType, InvalidDocumentError, classify_document
from app.documents.extractors.image_extractor import extract_image
from app.documents.extractors.pdf_extractor import extract_pdf
from app.documents.extractors.types import ExtractedDocument, LayoutToken
from app.documents.extractors.xlsx_extractor import extract_xlsx
from app.storage.temp_manager import sanitize_filename


MAX_ATTACHMENT_DEPTH = 5
HEADER_NAMES = ("From", "To", "Cc", "Subject")


class EmailExtractionError(ValueError):
    pass


@dataclass(slots=True)
class AttachmentExtraction:
    message_index: int
    part_path: tuple[int, ...]
    filename: str
    file_type: FileType
    start: int
    end: int
    extracted: ExtractedDocument


def _extract_by_type(path: Path, file_type: FileType, tesseract_cmd, depth: int) -> ExtractedDocument:
    if file_type == FileType.PDF:
        return extract_pdf(path, tesseract_cmd=tesseract_cmd)
    if file_type == FileType.DOCX:
        return extract_docx(path, tesseract_cmd=tesseract_cmd)
    if file_type == FileType.XLSX:
        return extract_xlsx(path, tesseract_cmd=tesseract_cmd)
    if file_type in {FileType.JPEG, FileType.PNG, FileType.TIFF}:
        return extract_image(path, tesseract_cmd=tesseract_cmd)
    if file_type == FileType.DICOM:
        return extract_dicom(path, tesseract_cmd=tesseract_cmd)
    if file_type in {FileType.EML, FileType.MBOX}:
        return extract_email(path, file_type=file_type, tesseract_cmd=tesseract_cmd, depth=depth + 1)
    raise EmailExtractionError("Unsupported recursive attachment format")


def _shift_document(document: ExtractedDocument, offset: int) -> tuple[list[LayoutToken], list, list]:
    tokens = [replace(token, start=token.start + offset, end=token.end + offset) for token in document.tokens]
    contexts = [replace(context, start=context.start + offset, end=context.end + offset) for context in document.structural_contexts]
    candidates = [replace(item, start=item.start + offset, end=item.end + offset) for item in document.preclassified_candidates]
    return tokens, contexts, candidates


def _append_text(
    parts: list[str],
    tokens: list[LayoutToken],
    contexts: list[StructuralContext],
    value: str,
    locator: str,
    source: str,
    label: str | None = None,
) -> None:
    if parts:
        parts.append("\n")
    start = sum(len(part) for part in parts)
    parts.append(value)
    end = start + len(value)
    for index, character in enumerate(value):
        tokens.append(
            LayoutToken(
                text=character,
                start=start + index,
                end=start + index + 1,
                locator=locator,
                local_start=index,
                local_end=index + 1,
                source=source,
            )
        )
    if label and end > start:
        contexts.append(StructuralContext(start, end, (label,)))


def _walk_parts(message: Message, path: tuple[int, ...] = ()):
    if message.is_multipart():
        for index, part in enumerate(message.iter_parts()):
            yield from _walk_parts(part, path + (index,))
    else:
        yield path, message


def _extract_message(
    message: Message,
    message_index: int,
    parent: Path,
    tesseract_cmd,
    depth: int,
    parts: list[str],
    tokens: list[LayoutToken],
    contexts: list[StructuralContext],
    forced: list,
    attachments: list[AttachmentExtraction],
) -> None:
    for header in HEADER_NAMES:
        value = str(message.get(header, ""))
        if value:
            _append_text(
                parts, tokens, contexts, value,
                f"email:{message_index}:header:{header.lower()}", "email_header", header,
            )
    for part_path, part in _walk_parts(message):
        filename = part.get_filename()
        if filename:
            if depth >= MAX_ATTACHMENT_DEPTH:
                raise EmailExtractionError("Email attachment nesting exceeds the safe limit")
            payload = part.get_payload(decode=True)
            if payload is None and part.get_content_type() == "message/rfc822":
                nested = part.get_payload()
                payload = nested[0].as_bytes(policy=policy.default) if isinstance(nested, list) and nested else b""
            payload = payload or b""
            safe_name = sanitize_filename(filename)
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=parent,
                    prefix="email_attachment_",
                    suffix=Path(safe_name).suffix,
                    delete=False,
                ) as temporary:
                    temporary.write(payload)
                    temporary_path = Path(temporary.name)
                file_type = classify_document(temporary_path, safe_name)
                extracted = _extract_by_type(temporary_path, file_type, tesseract_cmd, depth)
            except InvalidDocumentError as exc:
                raise EmailExtractionError(f"Unsupported attachment format: {safe_name}") from exc
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
            if parts:
                parts.append("\n")
            start = sum(len(item) for item in parts)
            parts.append(extracted.text)
            end = start + len(extracted.text)
            shifted_tokens, shifted_contexts, shifted_candidates = _shift_document(extracted, start)
            tokens.extend(shifted_tokens)
            contexts.extend(shifted_contexts)
            forced.extend(shifted_candidates)
            attachments.append(
                AttachmentExtraction(
                    message_index, part_path, safe_name, file_type, start, end, extracted
                )
            )
            continue
        if part.get_content_maintype() != "text":
            continue
        try:
            value = part.get_content()
        except (LookupError, UnicodeError) as exc:
            raise EmailExtractionError("Email text part could not be decoded") from exc
        _append_text(
            parts, tokens, contexts, str(value),
            f"email:{message_index}:part:{'.'.join(map(str, part_path))}", "email_body",
        )


def extract_email(
    path: Path,
    *,
    file_type: FileType,
    tesseract_cmd: Path | None = None,
    depth: int = 0,
) -> ExtractedDocument:
    parts: list[str] = []
    tokens: list[LayoutToken] = []
    contexts: list[StructuralContext] = []
    forced: list = []
    attachments: list[AttachmentExtraction] = []
    try:
        if file_type == FileType.EML:
            with path.open("rb") as source:
                messages = [BytesParser(policy=policy.default).parse(source)]
        elif file_type == FileType.MBOX:
            archive = mailbox.mbox(path, create=False)
            try:
                messages = [BytesParser(policy=policy.default).parsebytes(item.as_bytes()) for item in archive]
            finally:
                archive.close()
        else:
            raise EmailExtractionError("Expected EML or MBOX input")
        for index, message in enumerate(messages):
            _extract_message(
                message, index, path.parent, tesseract_cmd, depth,
                parts, tokens, contexts, forced, attachments,
            )
    except EmailExtractionError:
        raise
    except Exception as exc:
        raise EmailExtractionError("Email archive extraction failed") from exc
    return ExtractedDocument(
        text="".join(parts),
        tokens=tokens,
        structural_contexts=contexts,
        preclassified_candidates=forced,
        metadata={
            "message_count": len(messages),
            "attachment_count": len(attachments),
            "attachments": attachments,
            "email_file_type": file_type.value,
        },
    )
