#!/usr/bin/env python3
"""Validate a visually selected resume image and emit an auditable photo object."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path


PHOTO_MAX_BYTES = 2 * 1024 * 1024
PHOTO_MIN_DIMENSION = 48
PHOTO_MAX_DIMENSION = 2400
PHOTO_MAX_DATA_URI_CHARS = len("data:image/png;base64,") + 4 * ((PHOTO_MAX_BYTES + 2) // 3)
SOURCE_DOCUMENT = "input/resume-original.pdf"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package a visually confirmed resume portrait as a bounded offline data URI."
    )
    parser.add_argument("--input", required=True, type=Path, help="Visually confirmed PNG portrait")
    parser.add_argument("--resume-pdf", required=True, type=Path, help="Original resume PDF used for selection")
    parser.add_argument("--page", required=True, type=int, help="One-based resume page containing the portrait")
    parser.add_argument(
        "--extraction-method",
        required=True,
        choices=("embedded_image", "page_crop"),
        help="How the selected image was obtained from the resume PDF",
    )
    parser.add_argument("--image-index", type=int, help="Zero-based pdfimages output index for embedded_image")
    parser.add_argument("--crop-box", help="Pixel crop x,y,width,height for page_crop")
    return parser.parse_args()


def detect_mime(raw: bytes) -> str:
    if raw.startswith(PNG_SIGNATURE):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        raise ValueError("JPEG portraits must be converted to PNG and visually rechecked before embedding")
    raise ValueError("unsupported image type; use PNG")


def _validate_photo_dimensions(width: int, height: int) -> None:
    if not (
        PHOTO_MIN_DIMENSION <= width <= PHOTO_MAX_DIMENSION
        and PHOTO_MIN_DIMENSION <= height <= PHOTO_MAX_DIMENSION
    ):
        raise ValueError(
            "photo dimensions must each be from "
            f"{PHOTO_MIN_DIMENSION} to {PHOTO_MAX_DIMENSION} pixels"
        )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _png_scanline_layout(
    width: int,
    height: int,
    bits_per_pixel: int,
    interlace: int,
) -> list[tuple[int, int]]:
    if interlace == 0:
        return [(height, (width * bits_per_pixel + 7) // 8)]
    passes = (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    )
    layout: list[tuple[int, int]] = []
    for x_start, y_start, x_step, y_step in passes:
        pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
        pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
        if pass_width and pass_height:
            layout.append((pass_height, (pass_width * bits_per_pixel + 7) // 8))
    return layout


def _validate_png_pixels(
    compressed: bytes,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> None:
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    layout = _png_scanline_layout(width, height, channels * bit_depth, interlace)
    expected_size = sum(rows * (row_bytes + 1) for rows, row_bytes in layout)
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(compressed, expected_size + 1)
        if decompressor.unconsumed_tail or len(decoded) > expected_size:
            raise ValueError("PNG image data exceeds the declared dimensions")
        decoded += decompressor.flush()
    except zlib.error as exc:
        raise ValueError("PNG image data could not be decompressed") from exc
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("PNG image data is incomplete or has trailing compressed bytes")
    if len(decoded) != expected_size:
        raise ValueError("PNG image data does not match the declared dimensions")
    offset = 0
    for rows, row_bytes in layout:
        for _ in range(rows):
            if decoded[offset] > 4:
                raise ValueError("PNG contains an invalid row filter")
            offset += row_bytes + 1


def sanitize_png(raw: bytes) -> tuple[bytes, int, int]:
    """Validate PNG structure and return bytes without metadata or trailing content."""
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("invalid PNG signature")
    index = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    palette: bytes | None = None
    transparency: bytes | None = None
    idat_parts: list[bytes] = []
    seen_iend = False
    idat_closed = False
    while index < len(raw):
        if index + 12 > len(raw):
            raise ValueError("PNG chunk is truncated")
        length = struct.unpack(">I", raw[index:index + 4])[0]
        kind = raw[index + 4:index + 8]
        payload_start = index + 8
        payload_end = payload_start + length
        chunk_end = payload_end + 4
        if chunk_end > len(raw):
            raise ValueError("PNG chunk exceeds the file boundary")
        expected_crc = struct.unpack(">I", raw[payload_end:chunk_end])[0]
        if zlib.crc32(kind + raw[payload_start:payload_end]) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG chunk CRC is invalid")
        payload = raw[payload_start:payload_end]
        if ihdr is None and kind != b"IHDR":
            raise ValueError("PNG must start with IHDR")
        if kind == b"IHDR":
            if ihdr is not None or length != 13:
                raise ValueError("PNG must contain one valid IHDR")
            ihdr = payload
        elif kind == b"PLTE":
            if palette is not None or idat_parts or not 3 <= length <= 768 or length % 3:
                raise ValueError("PNG contains an invalid PLTE chunk")
            palette = payload
        elif kind == b"tRNS":
            if transparency is not None or idat_parts:
                raise ValueError("PNG contains an invalid tRNS chunk")
            transparency = payload
        elif kind == b"IDAT":
            if idat_closed:
                raise ValueError("PNG IDAT chunks must be consecutive")
            idat_parts.append(payload)
        elif kind == b"IEND":
            if length != 0 or not idat_parts:
                raise ValueError("PNG must end after image data")
            seen_iend = True
            break
        else:
            if idat_parts:
                idat_closed = True
            if kind and kind[0] & 0x20 == 0:
                raise ValueError(f"unsupported critical PNG chunk {kind!r}")
        index = chunk_end
    if ihdr is None or not seen_iend:
        raise ValueError("PNG is missing image data or IEND")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    valid_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if width <= 0 or height <= 0 or color_type not in valid_depths or bit_depth not in valid_depths[color_type]:
        raise ValueError("PNG has unsupported dimensions, color type, or bit depth")
    _validate_photo_dimensions(width, height)
    if compression != 0 or filtering != 0 or interlace not in {0, 1}:
        raise ValueError("PNG uses an unsupported compression, filter, or interlace method")
    if color_type == 3 and palette is None:
        raise ValueError("indexed PNG requires a palette")
    if transparency is not None:
        if color_type == 0 and len(transparency) != 2:
            raise ValueError("grayscale PNG has invalid transparency data")
        if color_type == 2 and len(transparency) != 6:
            raise ValueError("truecolor PNG has invalid transparency data")
        if color_type == 3 and (palette is None or len(transparency) > len(palette) // 3):
            raise ValueError("indexed PNG has invalid transparency data")
        if color_type in {4, 6}:
            raise ValueError("PNG with an alpha channel must not contain tRNS")
    compressed = b"".join(idat_parts)
    _validate_png_pixels(compressed, width, height, bit_depth, color_type, interlace)
    sanitized = bytearray(PNG_SIGNATURE)
    sanitized.extend(_png_chunk(b"IHDR", ihdr))
    if palette is not None:
        sanitized.extend(_png_chunk(b"PLTE", palette))
    if transparency is not None:
        sanitized.extend(_png_chunk(b"tRNS", transparency))
    sanitized.extend(_png_chunk(b"IDAT", compressed))
    sanitized.extend(_png_chunk(b"IEND", b""))
    return bytes(sanitized), width, height


def sanitize_image(raw: bytes, mime_type: str) -> tuple[bytes, int, int]:
    if mime_type == "image/png":
        return sanitize_png(raw)
    raise ValueError("unsupported image type; use PNG")


def image_dimensions(raw: bytes, mime_type: str) -> tuple[int, int]:
    _, width, height = sanitize_image(raw, mime_type)
    return width, height


def parse_crop_box(value: str | None) -> list[int] | None:
    if value is None:
        return None
    try:
        parts = [int(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise ValueError("--crop-box must be x,y,width,height integers") from exc
    if len(parts) != 4 or parts[0] < 0 or parts[1] < 0 or parts[2] <= 0 or parts[3] <= 0:
        raise ValueError("--crop-box must be x,y,width,height with positive width and height")
    return parts


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    try:
        image_path = args.input.expanduser().resolve(strict=True)
        if not image_path.is_file():
            raise ValueError("--input must be a regular image file")
        if image_path.stat().st_size > PHOTO_MAX_BYTES:
            raise ValueError(f"photo exceeds the {PHOTO_MAX_BYTES} byte limit")
        raw = image_path.read_bytes()
        mime_type = detect_mime(raw)
        sanitized, width, height = sanitize_image(raw, mime_type)

        resume_path = args.resume_pdf.expanduser().resolve(strict=True)
        if not resume_path.is_file():
            raise ValueError("--resume-pdf must be a regular PDF file")
        if resume_path.name != "resume-original.pdf" or resume_path.parent.name != "input":
            raise ValueError("--resume-pdf must be the canonical case file input/resume-original.pdf")
        with resume_path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("--resume-pdf does not have a PDF header")
        if args.page < 1:
            raise ValueError("--page must be one or greater")
        crop_box = parse_crop_box(args.crop_box)
        if args.extraction_method == "embedded_image":
            if args.image_index is None or args.image_index < 0:
                raise ValueError("embedded_image requires a non-negative --image-index")
            if crop_box is not None:
                raise ValueError("embedded_image must not include --crop-box")
        else:
            if crop_box is None:
                raise ValueError("page_crop requires --crop-box")
            if args.image_index is not None:
                raise ValueError("page_crop must not include --image-index")

        payload = {
            "status": "included",
            "data_uri": f"data:{mime_type};base64,{base64.b64encode(sanitized).decode('ascii')}",
            "mime_type": mime_type,
            "byte_length": len(sanitized),
            "pixel_width": width,
            "pixel_height": height,
            "sha256": hashlib.sha256(sanitized).hexdigest(),
            "provenance": {
                "source_kind": "resume_pdf",
                "source_document": SOURCE_DOCUMENT,
                "source_document_sha256": sha256_file(resume_path),
                "page": args.page,
                "extraction_method": args.extraction_method,
                "image_index": args.image_index,
                "crop_box": crop_box,
            },
        }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (OSError, OverflowError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
