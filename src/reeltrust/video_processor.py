"""Video processing utilities for creating compressed reference digests."""

import hashlib
import subprocess
from enum import Enum
from pathlib import Path


class CompressionQuality(Enum):
    """
    H.264 CRF quality settings for video compression in ReelTrust packages.

    Used for both low-res digest videos and alignment stripe videos.
    Lower CRF = higher quality = larger files = better tamper detection.

    Test results for low-res digest (240px width, preset=slow):
    - MAXIMUM: 12.9 MB package, SSIM differential 0.0183 (1.87%) - Best tamper detection
    - HIGH:     7.5 MB package, SSIM differential 0.0131 (1.36%) - Recommended balance
    - MEDIUM:   4.7 MB package, SSIM differential 0.0058 (0.62%) - Weak signal
    - LOW:      3.5 MB package, SSIM differential 0.0005 (0.05%) - Insufficient signal

    SSIM differential = gap between clean re-encoded video and tampered video SSIM scores.
    Higher differential enables more reliable tamper detection.

    Usage:
    - Low-res digest: Default is HIGH (CRF 23) for good tamper detection
    - Alignment stripes: Default is MEDIUM (CRF 28) for space efficiency
    - Region fingerprints: Use MAXIMUM (CRF 18) for temporary processing accuracy
    """

    MAXIMUM = 18  # Visually lossless, best tamper detection, largest files
    HIGH = 23     # Recommended for digest: good signal at reasonable size
    MEDIUM = 28   # Recommended for stripes: balance size vs precision
    LOW = 32      # Minimal signal, not recommended for tamper detection


# Default quality setting for low-res digest
DEFAULT_DIGEST_QUALITY = CompressionQuality.HIGH


def compress_video(
    input_path: Path,
    output_path: Path,
    width: int = 240,
    quality: CompressionQuality = DEFAULT_DIGEST_QUALITY,
) -> None:
    """
    Compress video to a low-resolution reference digest.

    Args:
        input_path: Path to input video file
        output_path: Path to save compressed video
        width: Target width in pixels (height will be calculated to maintain aspect ratio)
        quality: Compression quality setting (affects tamper detection accuracy vs size)
    """
    # Use ffmpeg to compress video for SSIM-based verification
    # -vf scale: resize to target width, maintaining aspect ratio
    # -crf: quality setting (from CompressionQuality enum)
    # -preset slow: better compression efficiency (encoding done once, verified many times)
    cmd = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-vf",
        f"scale={width}:-2",  # -2 ensures height is divisible by 2
        "-c:v",
        "libx264",
        "-crf",
        str(quality.value),
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
