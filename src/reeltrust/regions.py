"""Extract and process spatial regions from videos for alignment and cropping detection."""

import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .video_processor import CompressionQuality


# Default quality for alignment stripes (MEDIUM = CRF 23)
DEFAULT_STRIPE_QUALITY = CompressionQuality.MEDIUM


def extract_horizontal_stripe(
    video_path: Path,
    output_path: Path,
    vertical_position: float,
    stripe_height: int = 3,
    quality: CompressionQuality = DEFAULT_STRIPE_QUALITY,
) -> dict[str, Any]:
    """
    Extract a horizontal stripe VIDEO from a video at a specific vertical position.

    This creates a high-resolution horizontal slice across all frames that can be used
    for alignment detection and validation of cropping/panning operations.

    Args:
        video_path: Path to input video
        output_path: Path to save the stripe video (should end in .mp4)
        vertical_position: Vertical position as fraction (0.0 = top, 0.5 = center, 1.0 = bottom)
        stripe_height: Height of stripe in pixels (default: 3)
        quality: Compression quality setting for stripe video

    Returns:
        Dictionary with stripe metadata:
        {
            'position': float,  # Vertical position fraction
            'height': int,      # Stripe height in pixels
            'video_width': int, # Full video width
            'video_height': int, # Full video height
            'stripe_y': int,    # Absolute Y position in pixels
        }
    """
    # Read the first frame to get dimensions
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    ret, frame = cap.read()
    if not ret:
        raise RuntimeError(f"Failed to read frame from video: {video_path}")

    video_height, video_width = frame.shape[:2]
    cap.release()

    # Calculate the Y position for the stripe
    stripe_y = int(vertical_position * video_height)

    # Ensure stripe doesn't extend beyond frame boundaries
    stripe_y_start = max(0, stripe_y - stripe_height // 2)
    stripe_y_end = min(video_height, stripe_y_start + stripe_height)
    actual_height = stripe_y_end - stripe_y_start

    # Use ffmpeg to extract the stripe video with crop filter
    # crop=w:h:x:y where w=width, h=height, x=left, y=top
    # Sample at 4fps to reduce size while maintaining temporal coverage
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"crop={video_width}:{actual_height}:0:{stripe_y_start},fps=4",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(quality.value),
        "-an",  # No audio
        "-y",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract stripe: {e.stderr}") from e

    return {
        "position": vertical_position,
        "height": actual_height,
        "video_width": video_width,
        "video_height": video_height,
        "stripe_y": stripe_y_start,
    }


def extract_all_alignment_stripes(
    video_path: Path,
    output_dir: Path,
    stripe_height: int = 3,
    quality: CompressionQuality = DEFAULT_STRIPE_QUALITY,
) -> dict[str, Any]:
    """
    Extract all alignment stripes from a video as a single stacked video.

    Creates 5 horizontal stripes at key positions and stacks them vertically
    into one video for better compression (shared colors/motion across stripes).

    Stripe positions:
    - stripe_75top: Top edge of 75% box (12.5%)
    - stripe_50top: Top edge of 50% box (25%)
    - stripe_mid: Center (50%)
    - stripe_50bot: Bottom edge of 50% box (75%)
    - stripe_75bot: Bottom edge of 75% box (87.5%)

    Args:
        video_path: Path to input video
        output_dir: Directory to save stripe video
        stripe_height: Height of each stripe in pixels (default: 3)
        quality: Compression quality setting for stripe video

    Returns:
        Dictionary with stripe metadata including row positions in merged video
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video dimensions
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError(f"Failed to read frame from video: {video_path}")
    video_height, video_width = frame.shape[:2]
    cap.release()

    # Define stripe positions (top to bottom order for stacking)
    stripes_ordered = [
        ("stripe_75top", 0.125),   # Top edge of 75% box
        ("stripe_50top", 0.25),    # Top edge of 50% box
        ("stripe_mid", 0.50),      # Center
        ("stripe_50bot", 0.75),    # Bottom edge of 50% box
        ("stripe_75bot", 0.875),   # Bottom edge of 75% box
    ]

    # Build filter to stack all stripes vertically in one pass
    # Each stripe: crop to position, then vstack them all
    filters = []
    for i, (name, position) in enumerate(stripes_ordered):
        stripe_y = int(position * video_height)
        stripe_y_start = max(0, stripe_y - stripe_height // 2)
        stripe_y_end = min(video_height, stripe_y_start + stripe_height)

        # Crop filter for this stripe
        filters.append(f"[0:v]crop={video_width}:{stripe_y_end - stripe_y_start}:0:{stripe_y_start}[stripe{i}]")

    # Vertical stack all stripes
    vstack_inputs = "".join(f"[stripe{i}]" for i in range(len(stripes_ordered)))
    filters.append(f"{vstack_inputs}vstack=inputs={len(stripes_ordered)}[stacked]")

    # Apply fps filter to stacked result
    filters.append("[stacked]fps=4[out]")

    filter_complex = ";".join(filters)

    output_path = output_dir / "digest_stacked_stripes.mp4"

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(quality.value),
        "-an",
        "-y",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract stacked stripes: {e.stderr}") from e

    # Build metadata with row positions for each stripe
    results = {}
    current_row = 0
    for name, position in stripes_ordered:
        stripe_y = int(position * video_height)
        stripe_y_start = max(0, stripe_y - stripe_height // 2)
        stripe_y_end = min(video_height, stripe_y_start + stripe_height)
        actual_height = stripe_y_end - stripe_y_start

        results[name] = {
            "position": position,
            "height": actual_height,
            "video_width": video_width,
            "video_height": video_height,
            "stripe_y": stripe_y_start,
            "stacked_row_start": current_row,
            "stacked_row_end": current_row + actual_height,
            "file": "video_digests/digest_stacked_stripes.mp4"
        }
        current_row += actual_height

    return results


def compute_region_fingerprints(
    video_path: Path,
    region_fraction: float,
    quality: CompressionQuality = CompressionQuality.HIGH,  # Use high quality for temporary processing
) -> tuple[bytes, bytes, list[dict[str, Any]]]:
    """
    Compute fingerprints (dHash, pHash, frame statistics) for a concentric rectangle region.

    Args:
        video_path: Path to input video
        region_fraction: Size of the concentric rectangle as a fraction (e.g., 0.75 for 75%)
        quality: Quality for temporary cropped video (default HIGH for accurate fingerprinting)

    Returns:
        Tuple of (dhash_data, phash_data, frame_stats_data)
    """
    # Import fingerprint functions
    from .fingerprints import compute_dhash, compute_phash, compute_frame_statistics

    # First, get video dimensions
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    ret, frame = cap.read()
    if not ret:
        raise RuntimeError(f"Failed to read frame from video: {video_path}")

    video_height, video_width = frame.shape[:2]
    cap.release()

    # Calculate crop dimensions for the concentric rectangle
    # For X% region, the margins are (1-X)/2 on each side
    margin_fraction = (1.0 - region_fraction) / 2.0

    crop_x = int(video_width * margin_fraction)
    crop_y = int(video_height * margin_fraction)
    crop_width = int(video_width * region_fraction)
    crop_height = int(video_height * region_fraction)

    # Create a temporary cropped video
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        # Use ffmpeg to crop the video
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(quality.value),
            "-an",  # No audio
            "-y",
            str(tmp_path),
        ]

        subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Compute fingerprints on the cropped video
        dhash_data, _, _ = compute_dhash(tmp_path)
        phash_data, _, _ = compute_phash(tmp_path)
        frame_stats, _, _ = compute_frame_statistics(tmp_path)

        return dhash_data, phash_data, frame_stats

    finally:
        # Clean up temporary file
        if tmp_path.exists():
            tmp_path.unlink()


def create_region_fingerprints(
    video_path: Path,
    output_dir: Path,
    regions: list[float] | None = None,
) -> dict[str, Any]:
    """
    Create fingerprints for multiple concentric rectangle regions.

    Args:
        video_path: Path to input video
        output_dir: Directory to save fingerprint files
        regions: List of region fractions (default: [0.75, 0.50])

    Returns:
        Dictionary with region fingerprint metadata
    """
    if regions is None:
        regions = [0.75, 0.50]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for region in regions:
        region_name = f"region_{int(region * 100)}"
        region_dir = output_dir / region_name

        print(f"    Computing fingerprints for {int(region * 100)}% concentric region...")

        # Compute fingerprints
        dhash_data, phash_data, frame_stats = compute_region_fingerprints(
            video_path, region
        )

        # Save fingerprints
        region_dir.mkdir(parents=True, exist_ok=True)

        dhash_path = region_dir / "dhash.bin"
        dhash_path.write_bytes(dhash_data)

        phash_path = region_dir / "phash.bin"
        phash_path.write_bytes(phash_data)

        # Save frame statistics
        import json
        stats_path = region_dir / "frame_stats.json"
        with open(stats_path, 'w') as f:
            json.dump(frame_stats, f, indent=2)

        # Make paths relative to package root (parent of output_dir's parent which is 'fingerprints')
        # output_dir is 'fingerprints/regions', so parent.parent is package root
        package_root = output_dir.parent.parent

        results[region_name] = {
            "fraction": region,
            "dhash_file": str(dhash_path.relative_to(package_root)),
            "phash_file": str(phash_path.relative_to(package_root)),
            "frame_stats_file": str(stats_path.relative_to(package_root)),
            "frame_count": len(frame_stats),
        }

    return results
