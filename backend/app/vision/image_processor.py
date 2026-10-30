"""
backend/app/vision/image_processor.py - Safe Image Validation and Optimization

Enforces:
- Header and magic byte validation for JPEG, PNG, and WebP.
- Boundary validation for dimensions (min 16x16, max 4096x4096).
- Sizing limits (max payload bytes).
- Smart resizing/compression: only compresses when dimensions exceed threshold
  or file size is unnecessarily high, preserving crisp resolution for 640x480 OV3660 frames.
- Ephemeral in-memory processing (zero disk retention).
"""

import io
from typing import Tuple
from PIL import Image
from .schemas import VisionImageMetadata
from .. import config

SUPPORTED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}

def validate_and_process_image(image_bytes: bytes,
                               max_dimension: int = None,
                               compress_threshold: int = None,
                               target_quality: int = None) -> Tuple[bytes, VisionImageMetadata]:
    """
    Validates image payload, verifies dimensions, and resizes/compresses only when needed.
    """
    max_dim = max_dimension or config.VISION_MAX_DIMENSION
    threshold = compress_threshold or config.VISION_COMPRESS_THRESHOLD_BYTES
    quality = target_quality or config.VISION_JPEG_QUALITY

    original_len = len(image_bytes)
    if original_len == 0:
        raise ValueError("Empty image payload received")
    if original_len > config.MAX_IMAGE_PAYLOAD_BYTES:
        raise ValueError(f"Image payload ({original_len} bytes) exceeds maximum limit of {config.MAX_IMAGE_PAYLOAD_BYTES} bytes")

    # Fast magic byte verification
    is_jpeg = (original_len >= 4 and image_bytes[0] == 0xFF and image_bytes[1] == 0xD8)
    is_png = (original_len >= 8 and image_bytes[:4] == b"\x89PNG")
    is_webp = (original_len >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP")

    if not (is_jpeg or is_png or is_webp):
        raise ValueError("Unsupported image format: Must be JPEG, PNG, or WebP")

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img_format = img.format.upper() if img.format else "UNKNOWN"
            if img_format not in SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported image format '{img_format}'")

            width, height = img.size
            if width < 16 or height < 16:
                raise ValueError(f"Image dimensions ({width}x{height}) are too small for vision processing")
            if width > 4096 or height > 4096:
                raise ValueError(f"Image dimensions ({width}x{height}) exceed maximum allowed limit of 4096px")

            was_resized = False
            was_compressed = False

            # Check if dimensions need resizing
            if width > max_dim or height > max_dim:
                was_resized = True
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                new_width, new_height = img.size

                # Convert RGB if necessary
                if img.mode != "RGB":
                    out_img = img.convert("RGB")
                else:
                    out_img = img

                out_io = io.BytesIO()
                out_img.save(out_io, format="JPEG", quality=quality, optimize=True)
                processed_bytes = out_io.getvalue()
                metadata = VisionImageMetadata(
                    width=new_width,
                    height=new_height,
                    format="JPEG",
                    original_bytes=original_len,
                    processed_bytes=len(processed_bytes),
                    was_resized=True,
                    was_compressed=True
                )
                return processed_bytes, metadata

            # Check if compression is needed based on file size
            if original_len > threshold and img_format == "JPEG":
                was_compressed = True
                out_io = io.BytesIO()
                if img.mode != "RGB":
                    out_img = img.convert("RGB")
                else:
                    out_img = img
                out_img.save(out_io, format="JPEG", quality=quality, optimize=True)
                processed_bytes = out_io.getvalue()
                metadata = VisionImageMetadata(
                    width=width,
                    height=height,
                    format="JPEG",
                    original_bytes=original_len,
                    processed_bytes=len(processed_bytes),
                    was_resized=False,
                    was_compressed=True
                )
                return processed_bytes, metadata

            # Optimal pass-through (e.g. 640x480 OV3660 camera frame)
            # Force pixel decoding to verify data integrity and catch truncated streams
            img.load()

            metadata = VisionImageMetadata(
                width=width,
                height=height,
                format=img_format,
                original_bytes=original_len,
                processed_bytes=original_len,
                was_resized=False,
                was_compressed=False
            )
            return image_bytes, metadata

    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Corrupted or invalid image data: {str(e)}")

