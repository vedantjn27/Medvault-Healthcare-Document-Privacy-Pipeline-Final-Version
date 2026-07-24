"""Content-based supported-document classification and extension validation."""

from __future__ import annotations

from email import policy
from email.parser import BytesParser
from enum import StrEnum
from pathlib import Path
import warnings
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError
from pydicom.misc import is_dicom


class FileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    DICOM = "dicom"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    EML = "eml"
    MBOX = "mbox"


ALLOWED_EXTENSIONS: dict[FileType, frozenset[str]] = {
    FileType.PDF: frozenset({".pdf"}),
    FileType.DOCX: frozenset({".docx"}),
    FileType.XLSX: frozenset({".xlsx"}),
    FileType.DICOM: frozenset({".dcm", ".dicom"}),
    FileType.JPEG: frozenset({".jpg", ".jpeg"}),
    FileType.PNG: frozenset({".png"}),
    FileType.TIFF: frozenset({".tif", ".tiff"}),
    FileType.EML: frozenset({".eml"}),
    FileType.MBOX: frozenset({".mbox"}),
}


class InvalidDocumentError(ValueError):
    pass


def _classify_zip(path: Path) -> FileType | None:
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if len(entries) > 10_000:
                raise InvalidDocumentError("Office archive contains too many entries")
            if sum(entry.file_size for entry in entries) > 200 * 1024 * 1024:
                raise InvalidDocumentError("Office archive expands beyond the safe preview limit")
            for entry in entries:
                if entry.file_size > 100 * 1024 * 1024:
                    raise InvalidDocumentError("Office archive contains an oversized entry")
                if entry.compress_size and entry.file_size > 10 * 1024 * 1024:
                    if entry.file_size / entry.compress_size > 1_000:
                        raise InvalidDocumentError("Office archive has an unsafe compression ratio")
            if "[Content_Types].xml" not in names:
                return None
            if "word/document.xml" in names:
                return FileType.DOCX
            if "xl/workbook.xml" in names:
                return FileType.XLSX
    except BadZipFile:
        return None
    return None


def _classify_image(path: Path) -> FileType | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image.verify()
                image_format = image.format
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None
    return {
        "JPEG": FileType.JPEG,
        "PNG": FileType.PNG,
        "TIFF": FileType.TIFF,
    }.get(image_format or "")


def _looks_like_email(path: Path) -> bool:
    with path.open("rb") as source:
        sample = source.read(262_144)
    if b"\x00" in sample:
        return False
    try:
        message = BytesParser(policy=policy.default).parsebytes(sample, headersonly=True)
    except (TypeError, ValueError):
        return False
    return any(message.get(header) for header in ("From", "To", "Date", "Subject", "Message-ID"))


def classify_document(path: Path, original_filename: str) -> FileType:
    """Classify real content and require a matching supported extension."""

    with path.open("rb") as source:
        header = source.read(4096)
    detected: FileType | None = None
    if header.startswith(b"%PDF-"):
        detected = FileType.PDF
    elif header.startswith(b"PK\x03\x04"):
        detected = _classify_zip(path)
    elif is_dicom(str(path)):
        detected = FileType.DICOM
    else:
        detected = _classify_image(path)

    suffix = Path(original_filename).suffix.lower()
    if detected is None and suffix == ".mbox" and header.startswith(b"From "):
        detected = FileType.MBOX
    if detected is None and suffix == ".eml" and _looks_like_email(path):
        detected = FileType.EML
    if detected is None:
        raise InvalidDocumentError("File content is not a supported document format")
    if suffix not in ALLOWED_EXTENSIONS[detected]:
        raise InvalidDocumentError(
            f"File extension does not match detected {detected.value} content"
        )
    return detected
