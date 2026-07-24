"""Tesseract, MediaPipe BlazeFace, and pyzbar extraction for raster images."""

from __future__ import annotations

import threading
import warnings
from functools import lru_cache
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions
from PIL import Image, ImageSequence
import pytesseract
from pytesseract import Output
from pyzbar.pyzbar import decode as decode_barcodes

from app.detection.types import DetectionCandidate, DetectionDecision, DetectorSource
from app.documents.extractors.types import ExtractedDocument, LayoutToken


FACE_MODEL_PATH = Path(__file__).resolve().parents[2] / "assets" / "blaze_face_short_range.tflite"
_FACE_LOCK = threading.Lock()


class ImageExtractionError(ValueError):
    pass


@lru_cache(maxsize=1)
def get_face_detector() -> vision.FaceDetector:
    if not FACE_MODEL_PATH.is_file():
        raise ImageExtractionError("Local MediaPipe face detector model is missing")
    options = vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(FACE_MODEL_PATH)),
        running_mode=vision.RunningMode.IMAGE,
        min_detection_confidence=0.5,
        min_suppression_threshold=0.3,
    )
    return vision.FaceDetector.create_from_options(options)


def detect_faces(image: Image.Image) -> list[tuple[float, float, float, float]]:
    rgb = np.ascontiguousarray(image.convert("RGB"), dtype=np.uint8)
    media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    with _FACE_LOCK:
        result = get_face_detector().detect(media_image)
    boxes = []
    for detection in result.detections:
        box = detection.bounding_box
        pad_x, pad_y = box.width * 0.1, box.height * 0.1
        boxes.append(
            (
                max(0.0, box.origin_x - pad_x),
                max(0.0, box.origin_y - pad_y),
                min(float(image.width), box.origin_x + box.width + pad_x),
                min(float(image.height), box.origin_y + box.height + pad_y),
            )
        )
    return boxes


def detect_barcode_regions(image: Image.Image) -> list[tuple[float, float, float, float]]:
    boxes = []
    for barcode in decode_barcodes(image.convert("RGB")):
        rectangle = barcode.rect
        boxes.append(
            (
                float(max(0, rectangle.left)),
                float(max(0, rectangle.top)),
                float(min(image.width, rectangle.left + rectangle.width)),
                float(min(image.height, rectangle.top + rectangle.height)),
            )
        )
    return boxes


def _append_visual_candidate(
    parts: list[str],
    tokens: list[LayoutToken],
    candidates: list[DetectionCandidate],
    marker: str,
    entity_type: str,
    bbox: tuple[float, float, float, float],
    frame: int,
    locator: str,
    source: DetectorSource,
    reason: str,
) -> None:
    if parts:
        parts.append("\n")
    start = sum(len(part) for part in parts)
    parts.append(marker)
    end = start + len(marker)
    tokens.append(
        LayoutToken(
            text=marker,
            start=start,
            end=end,
            page_number=frame + 1,
            bbox=bbox,
            locator=locator,
            source="visual_region",
        )
    )
    candidates.append(
        DetectionCandidate(
            entity_type=entity_type,
            start=start,
            end=end,
            matched_text=marker,
            detector_score=1.0,
            pattern_validation=1.0,
            context_boost=1.0,
            detector_sources={source},
            trigger_reasons=[reason],
            confidence=1.0,
            decision=DetectionDecision.AUTO_REDACT,
            page_number=frame + 1,
        )
    )


def _append_ocr(
    image: Image.Image,
    parts: list[str],
    tokens: list[LayoutToken],
    frame: int,
    locator_prefix: str,
) -> None:
    data = pytesseract.image_to_data(image.convert("RGB"), config="--psm 6", output_type=Output.DICT)
    previous_line = None
    for index, raw_word in enumerate(data["text"]):
        word = str(raw_word).strip()
        confidence = float(data["conf"][index]) if str(data["conf"][index]) not in {"", "-1"} else -1
        if not word or confidence < 0:
            continue
        line = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        if parts and previous_line is not None and line != previous_line:
            parts.append("\n")
        elif parts and not parts[-1].endswith((" ", "\n")):
            parts.append(" ")
        previous_line = line
        start = sum(len(part) for part in parts)
        parts.append(word)
        left, top = int(data["left"][index]), int(data["top"][index])
        width, height = int(data["width"][index]), int(data["height"][index])
        for char_index, character in enumerate(word):
            x0 = left + width * char_index / max(1, len(word))
            x1 = left + width * (char_index + 1) / max(1, len(word))
            tokens.append(
                LayoutToken(
                    text=character,
                    start=start + char_index,
                    end=start + char_index + 1,
                    page_number=frame + 1,
                    bbox=(x0, top, x1, top + height),
                    locator=f"{locator_prefix}:ocr:{index}",
                    local_start=char_index,
                    local_end=char_index + 1,
                    source="image_ocr",
                )
            )


def analyze_image_frames(
    frames: list[Image.Image],
    *,
    locator_prefix: str = "image",
) -> ExtractedDocument:
    parts: list[str] = []
    tokens: list[LayoutToken] = []
    forced: list[DetectionCandidate] = []
    face_count = barcode_count = 0
    for frame_index, frame in enumerate(frames):
        image = frame.convert("RGB")
        for index, bbox in enumerate(detect_faces(image)):
            face_count += 1
            _append_visual_candidate(
                parts, tokens, forced, "[FACE_REGION]", "FACE", bbox, frame_index,
                f"{locator_prefix}:frame:{frame_index}:face:{index}", DetectorSource.COMPUTER_VISION,
                "MediaPipe detected a face region",
            )
        for index, bbox in enumerate(detect_barcode_regions(image)):
            barcode_count += 1
            _append_visual_candidate(
                parts, tokens, forced, "[BARCODE_REGION]", "BARCODE", bbox, frame_index,
                f"{locator_prefix}:frame:{frame_index}:barcode:{index}", DetectorSource.BARCODE,
                "a barcode or QR code can encode a direct identifier",
            )
        _append_ocr(image, parts, tokens, frame_index, f"{locator_prefix}:frame:{frame_index}")
    return ExtractedDocument(
        text="".join(parts),
        tokens=tokens,
        preclassified_candidates=forced,
        metadata={"frame_count": len(frames), "face_count": face_count, "barcode_count": barcode_count},
    )


def extract_image(path: Path, *, tesseract_cmd: Path | None = None) -> ExtractedDocument:
    if tesseract_cmd is not None:
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as source:
                frames = [frame.copy() for frame in ImageSequence.Iterator(source)]
    except Exception as exc:
        raise ImageExtractionError("Image extraction failed") from exc
    return analyze_image_frames(frames)
