"""Native pdfplumber extraction with 300-DPI Tesseract fallback and layout offsets."""

from __future__ import annotations

from pathlib import Path

import fitz
import pdfplumber
from PIL import Image
import pytesseract
from pytesseract import Output

from app.documents.extractors.types import ExtractedDocument, LayoutToken


class PdfExtractionError(ValueError):
    pass


def _append_word(
    parts: list[str],
    tokens: list[LayoutToken],
    word: str,
    bbox: tuple[float, float, float, float],
    page_number: int,
    locator: str,
    source: str,
    char_boxes: list[tuple[float, float, float, float]] | None = None,
) -> None:
    if parts and not parts[-1].endswith(("\n", " ")):
        parts.append(" ")
    word_start = sum(len(part) for part in parts)
    parts.append(word)
    if char_boxes and len(char_boxes) == len(word):
        for index, character in enumerate(word):
            tokens.append(
                LayoutToken(
                    text=character,
                    start=word_start + index,
                    end=word_start + index + 1,
                    page_number=page_number,
                    bbox=char_boxes[index],
                    locator=locator,
                    local_start=index,
                    local_end=index + 1,
                    source=source,
                )
            )
    else:
        width = max(0.1, bbox[2] - bbox[0])
        for index, character in enumerate(word):
            x0 = bbox[0] + width * index / max(1, len(word))
            x1 = bbox[0] + width * (index + 1) / max(1, len(word))
            tokens.append(
                LayoutToken(
                    text=character,
                    start=word_start + index,
                    end=word_start + index + 1,
                    page_number=page_number,
                    bbox=(x0, bbox[1], x1, bbox[3]),
                    locator=locator,
                    local_start=index,
                    local_end=index + 1,
                    source=source,
                )
            )


def _native_page(
    page,
    parts: list[str],
    tokens: list[LayoutToken],
    page_number: int,
) -> int:
    words = page.extract_words(
        use_text_flow=True,
        keep_blank_chars=False,
        return_chars=True,
    )
    character_count = sum(len(str(word.get("text", "")).strip()) for word in words)
    if character_count < 20:
        return character_count
    previous_top: float | None = None
    for index, word_data in enumerate(words):
        word = str(word_data.get("text", "")).strip()
        if not word:
            continue
        top = float(word_data["top"])
        if previous_top is not None and abs(top - previous_top) > max(4.0, float(word_data["bottom"]) - top):
            parts.append("\n")
        previous_top = top
        chars = word_data.get("chars") or []
        char_boxes = [
            (float(char["x0"]), float(char["top"]), float(char["x1"]), float(char["bottom"]))
            for char in chars
        ]
        _append_word(
            parts,
            tokens,
            word,
            (
                float(word_data["x0"]),
                top,
                float(word_data["x1"]),
                float(word_data["bottom"]),
            ),
            page_number,
            f"page:{page_number}:word:{index}",
            "native",
            char_boxes,
        )
    return character_count


def _ocr_page(
    fitz_page: fitz.Page,
    parts: list[str],
    tokens: list[LayoutToken],
    page_number: int,
) -> None:
    scale = 300.0 / 72.0
    pixmap = fitz_page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    data = pytesseract.image_to_data(image, config="--psm 6", output_type=Output.DICT)
    x_scale = fitz_page.rect.width / image.width
    y_scale = fitz_page.rect.height / image.height
    previous_line: tuple[int, int, int] | None = None
    for index, raw_word in enumerate(data["text"]):
        word = str(raw_word).strip()
        confidence = float(data["conf"][index]) if str(data["conf"][index]) not in {"", "-1"} else -1.0
        if not word or confidence < 0:
            continue
        line = (int(data["block_num"][index]), int(data["par_num"][index]), int(data["line_num"][index]))
        if previous_line is not None and line != previous_line:
            parts.append("\n")
        previous_line = line
        left, top = int(data["left"][index]), int(data["top"][index])
        width, height = int(data["width"][index]), int(data["height"][index])
        bbox = (
            left * x_scale,
            top * y_scale,
            (left + width) * x_scale,
            (top + height) * y_scale,
        )
        _append_word(
            parts,
            tokens,
            word,
            bbox,
            page_number,
            f"page:{page_number}:ocr:{index}",
            "ocr",
        )


def extract_pdf(path: Path, *, tesseract_cmd: Path | None = None) -> ExtractedDocument:
    if tesseract_cmd is not None:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)
    parts: list[str] = []
    tokens: list[LayoutToken] = []
    scanned_pages: list[int] = []
    try:
        fitz_document = fitz.open(path)
        if fitz_document.needs_pass:
            fitz_document.close()
            raise PdfExtractionError("Password-protected PDFs are not supported")
        with pdfplumber.open(path) as plumber_document:
            if len(plumber_document.pages) != fitz_document.page_count:
                raise PdfExtractionError("PDF page count could not be reconciled")
            for page_index, plumber_page in enumerate(plumber_document.pages):
                if parts:
                    parts.append("\n\n")
                count = _native_page(plumber_page, parts, tokens, page_index + 1)
                if count < 20:
                    _ocr_page(fitz_document.load_page(page_index), parts, tokens, page_index + 1)
                    scanned_pages.append(page_index + 1)
        page_count = fitz_document.page_count
        fitz_document.close()
    except PdfExtractionError:
        raise
    except Exception as exc:
        raise PdfExtractionError("PDF extraction failed") from exc
    return ExtractedDocument(
        text="".join(parts),
        tokens=tokens,
        metadata={"page_count": page_count, "scanned_pages": scanned_pages},
    )
