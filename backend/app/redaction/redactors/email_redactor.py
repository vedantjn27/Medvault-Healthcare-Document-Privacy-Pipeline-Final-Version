"""MIME-safe EML/MBOX redaction with recursively processed attachments."""

from __future__ import annotations

import mailbox
import tempfile
from dataclasses import replace
from email import encoders, policy
from email.message import Message
from email.parser import BytesParser
from pathlib import Path

from app.detection.types import DetectionCandidate, DetectionDecision
from app.documents.extractors.email_extractor import AttachmentExtraction
from app.documents.extractors.types import ExtractedDocument, LayoutToken
from app.documents.file_types import FileType
from app.redaction.redactors.dicom_redactor import redact_dicom
from app.redaction.redactors.docx_redactor import redact_docx
from app.redaction.redactors.image_redactor import redact_image
from app.redaction.redactors.pdf_redactor import redact_pdf
from app.redaction.redactors.xlsx_redactor import redact_xlsx


class EmailRedactionError(ValueError):
    pass


def _messages_from_file(path: Path, file_type: FileType) -> list[Message]:
    if file_type == FileType.EML:
        with path.open("rb") as source:
            return [BytesParser(policy=policy.default).parse(source)]
    archive = mailbox.mbox(path, create=False)
    try:
        return [BytesParser(policy=policy.default).parsebytes(item.as_bytes()) for item in archive]
    finally:
        archive.close()


def _part_at(message: Message, path: tuple[int, ...]) -> Message:
    current = message
    for index in path:
        current = list(current.iter_parts())[index]
    return current


def _text_operations(extracted: ExtractedDocument, candidates, verbose):
    operations: dict[str, list[tuple[int, int, str]]] = {}
    for candidate in sorted(candidates, key=lambda item: item.start, reverse=True):
        tokens = [
            token for token in extracted.tokens_for(candidate)
            if token.source in {"email_header", "email_body"} and token.locator
        ]
        if not tokens:
            continue
        grouped: dict[str, list[LayoutToken]] = {}
        for token in tokens:
            grouped.setdefault(token.locator, []).append(token)
        first = min(grouped, key=lambda key: min(token.start for token in grouped[key]))
        label = candidate.replacement_text or (
            f"[REDACTED: {candidate.entity_type}]" if verbose else "[REDACTED]"
        )
        for locator, locator_tokens in grouped.items():
            start = min(token.local_start for token in locator_tokens)
            end = max(token.local_end or token.local_start + 1 for token in locator_tokens)
            operations.setdefault(locator, []).append((start, end, label if locator == first else ""))
    return operations


def _apply_string(value: str, operations) -> str:
    for start, end, replacement in sorted(operations, reverse=True):
        value = value[:start] + replacement + value[end:]
    return value


def _local_candidates(candidates, attachment: AttachmentExtraction):
    local = []
    for candidate in candidates:
        if candidate.start < attachment.end and candidate.end > attachment.start:
            local.append(
                replace(
                    candidate,
                    start=max(0, candidate.start - attachment.start),
                    end=min(attachment.end, candidate.end) - attachment.start,
                )
            )
    return local


def _redact_attachment(content: bytes, attachment: AttachmentExtraction, candidates, verbose) -> bytes:
    suffix = Path(attachment.filename).suffix
    source_path = output_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source_file:
            source_file.write(content)
            source_path = Path(source_file.name)
        output_path = source_path.with_name(source_path.stem + "_redacted" + suffix)
        local = _local_candidates(candidates, attachment)
        if attachment.file_type == FileType.PDF:
            redact_pdf(source_path, output_path, attachment.extracted, local, verbose_labels=verbose)
        elif attachment.file_type == FileType.DOCX:
            redact_docx(source_path, output_path, attachment.extracted, local, verbose_labels=verbose)
        elif attachment.file_type == FileType.XLSX:
            redact_xlsx(source_path, output_path, attachment.extracted, local, verbose_labels=verbose)
        elif attachment.file_type in {FileType.JPEG, FileType.PNG, FileType.TIFF}:
            redact_image(source_path, output_path, attachment.extracted, local)
        elif attachment.file_type == FileType.DICOM:
            redact_dicom(source_path, output_path, attachment.extracted, local)
        elif attachment.file_type in {FileType.EML, FileType.MBOX}:
            redact_email(source_path, output_path, attachment.extracted, local, verbose_labels=verbose)
        else:
            raise EmailRedactionError("Unsupported recursive attachment format")
        return output_path.read_bytes()
    finally:
        if source_path is not None:
            source_path.unlink(missing_ok=True)
        if output_path is not None:
            output_path.unlink(missing_ok=True)


def redact_email(
    source: Path,
    destination: Path,
    extracted: ExtractedDocument,
    candidates: list[DetectionCandidate],
    *,
    verbose_labels: bool = False,
) -> int:
    redactions = [item for item in candidates if item.decision == DetectionDecision.AUTO_REDACT]
    file_type = FileType(str(extracted.metadata["email_file_type"]))
    messages = _messages_from_file(source, file_type)
    operations = _text_operations(extracted, redactions, verbose_labels)
    attachments: list[AttachmentExtraction] = extracted.metadata.get("attachments", [])
    try:
        for message_index, message in enumerate(messages):
            for header in ("from", "to", "cc", "subject"):
                locator = f"email:{message_index}:header:{header}"
                if locator in operations and message.get(header):
                    message.replace_header(header, _apply_string(str(message.get(header)), operations[locator]))
            for part_path, part in _walk_message_parts(message):
                locator = f"email:{message_index}:part:{'.'.join(map(str, part_path))}"
                if locator in operations and part.get_content_maintype() == "text":
                    current = str(part.get_content())
                    subtype = part.get_content_subtype()
                    part.set_content(_apply_string(current, operations[locator]), subtype=subtype)
            for attachment in [item for item in attachments if item.message_index == message_index]:
                part = _part_at(message, attachment.part_path)
                content = part.get_payload(decode=True)
                if content is None and part.get_content_type() == "message/rfc822":
                    nested = part.get_payload()
                    content = nested[0].as_bytes(policy=policy.default) if isinstance(nested, list) and nested else b""
                content = content or b""
                redacted_content = _redact_attachment(
                    content, attachment, redactions, verbose_labels
                )
                if part.get("Content-Transfer-Encoding"):
                    del part["Content-Transfer-Encoding"]
                part.set_payload(redacted_content)
                encoders.encode_base64(part)

        destination.parent.mkdir(parents=True, exist_ok=True)
        if file_type == FileType.EML:
            destination.write_bytes(messages[0].as_bytes(policy=policy.default))
        else:
            archive = mailbox.mbox(destination, create=True)
            try:
                for message in messages:
                    archive.add(message)
                archive.flush()
            finally:
                archive.close()
    except Exception as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, EmailRedactionError):
            raise
        raise EmailRedactionError("Email archive redaction failed") from exc
    return len(redactions)


def _walk_message_parts(message: Message, path: tuple[int, ...] = ()):
    if message.is_multipart():
        for index, part in enumerate(message.iter_parts()):
            yield from _walk_message_parts(part, path + (index,))
    else:
        yield path, message
