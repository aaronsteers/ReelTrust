"""Metadata generation and management."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def extract_video_metadata(video_path: Path) -> dict[str, Any]:
    """
    Extract metadata from video file using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Dictionary containing video metadata
    """
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to extract video metadata: {e.stderr}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}") from e


def create_metadata(
    video_path: Path,
    user_identity: str | None = None,
    gps_coords: tuple[float, float] | None = None,
    additional_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create metadata for a video file.

    Args:
        video_path: Path to original video file
        user_identity: Optional user identity (username, email, etc.)
        gps_coords: Optional GPS coordinates as (latitude, longitude)
        additional_info: Optional additional metadata to include

    Returns:
        Dictionary containing metadata
    """
    # Get file stats
    file_stats = os.stat(video_path)

    # Extract video metadata
    ffprobe_data = extract_video_metadata(video_path)

    # Build metadata
    metadata = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file": {
            "name": video_path.name,
            "size_bytes": file_stats.st_size,
            "creation_time": datetime.fromtimestamp(
                file_stats.st_ctime, tz=timezone.utc
            ).isoformat(),
            "modification_time": datetime.fromtimestamp(
                file_stats.st_mtime, tz=timezone.utc
            ).isoformat(),
        },
        "video_info": {
            "duration": float(ffprobe_data.get("format", {}).get("duration", 0)),
            "format": ffprobe_data.get("format", {}).get("format_name", "unknown"),
            "streams": len(ffprobe_data.get("streams", [])),
        },
    }

    # Add optional fields
    if user_identity:
        metadata["user_identity"] = user_identity

    if gps_coords:
        metadata["gps_location"] = {
            "latitude": gps_coords[0],
            "longitude": gps_coords[1],
        }

    if additional_info:
        metadata["additional_info"] = additional_info

    # Try to extract creation time from video metadata if available
    format_tags = ffprobe_data.get("format", {}).get("tags", {})
    if "creation_time" in format_tags:
        metadata["video_creation_time"] = format_tags["creation_time"]

    return metadata


def save_metadata(metadata: dict[str, Any], output_path: Path) -> None:
    """
    Save metadata to JSON file.

    Args:
        metadata: Metadata dictionary
        output_path: Path to save JSON file
    """
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)


def load_metadata(metadata_path: Path) -> dict[str, Any]:
    """
    Load metadata from JSON file.

    Args:
        metadata_path: Path to metadata JSON file

    Returns:
        Metadata dictionary
    """
    with open(metadata_path) as f:
        return json.load(f)
