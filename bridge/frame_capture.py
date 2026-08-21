"""Frame capture and image utilities for DaVinci Resolve AI Bridge."""

import base64
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def get_capture_dir() -> Path:
    """Return a temporary directory for frame dumps."""
    capture_dir = Path(tempfile.gettempdir()) / "resolve-frame-captures"
    capture_dir.mkdir(parents=True, exist_ok=True)
    return capture_dir


def encode_image_base64(file_path: Path) -> Tuple[str, int, int]:
    """Read an image from disk, returning base64 data and (width, height)."""
    with open(file_path, "rb") as f:
        raw_bytes = f.read()
    b64_str = base64.b64encode(raw_bytes).decode("ascii")

    # Determine dimensions
    width, height = 1920, 1080
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            width, height = img.size
    except Exception:
        try:
            import cv2
            img = cv2.imread(str(file_path))
            if img is not None:
                height, width = img.shape[:2]
        except Exception:
            pass
    return b64_str, width, height


def resize_image_if_needed(file_path: Path, max_width: int = 1280) -> Path:
    """Downscale image if its width exceeds max_width to conserve LLM context tokens."""
    if max_width <= 0:
        return file_path

    try:
        from PIL import Image
        with Image.open(file_path) as img:
            if img.width > max_width:
                ratio = max_width / float(img.width)
                new_height = int(img.height * ratio)
                resized = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                resized.save(file_path, quality=85, optimize=True)
                return file_path
    except Exception:
        pass

    try:
        import cv2
        img = cv2.imread(str(file_path))
        if img is not None and img.shape[1] > max_width:
            ratio = max_width / float(img.shape[1])
            new_height = int(img.shape[0] * ratio)
            resized = cv2.resize(img, (max_width, new_height), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(file_path), resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            return file_path
    except Exception:
        pass

    return file_path


def extract_source_frame(video_path: str, timestamp_sec: float, output_path: Path) -> bool:
    """Extract a single frame from a video file at a given timestamp in seconds."""
    # 1. Try OpenCV
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec * 1000.0))
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                cv2.imwrite(str(output_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                if output_path.exists() and output_path.stat().st_size > 0:
                    return True
    except Exception:
        pass

    # 2. Try ffmpeg if available
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss",
            f"{max(0.0, timestamp_sec):.3f}",
            "-i",
            str(video_path),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return True

    return False
