"""Video processing utilities for creating compressed reference digests."""

import hashlib
import subprocess
from pathlib import Path


def compress_video(input_path: Path, output_path: Path, width: int = 240) -> None:
    """
    Compress video to a low-resolution reference digest.

    Args:
        input_path: Path to input video file
        output_path: Path to save compressed video
        width: Target width in pixels (height will be calculated to maintain aspect ratio)
    """
    # Use ffmpeg to compress video with high quality for better SSIM verification
    # -vf scale: resize to target width, maintaining aspect ratio
    # -crf 18: visually lossless quality for better tamper detection
    # -preset slow: better compression efficiency (encoding done once, verified many times)
    # -c:a copy: skip audio (we'll fingerprint it separately)
    cmd = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-vf",
        f"scale={width}:-2",  # -2 ensures height is divisible by 2
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "slow",
        "-an",  # Remove audio (no audio stream)
        "-y",  # Overwrite output file
        str(output_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to compress video: {e.stderr}") from e


def extract_audio(input_path: Path, output_path: Path) -> None:
    """
    Extract audio from video file.

    Args:
        input_path: Path to input video file
        output_path: Path to save extracted audio (typically .wav)
    """
    cmd = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-vn",  # No video
        "-acodec",
        "pcm_s16le",  # PCM 16-bit for fingerprinting
        "-ar",
        "44100",  # Sample rate
        "-ac",
        "2",  # Stereo
        "-y",  # Overwrite output file
        str(output_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract audio: {e.stderr}") from e


def hash_file(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file.

    Args:
        file_path: Path to file to hash

    Returns:
        Hex string of SHA-256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
