"""Audio fingerprinting utilities using Chromaprint (AcoustID)."""

import json
from pathlib import Path
from typing import Any

import acoustid


def create_audio_fingerprint(audio_path: Path) -> dict[str, Any]:
    """
    Create an audio fingerprint from an audio file using Chromaprint.

    Args:
        audio_path: Path to audio file (typically .wav)

    Returns:
        Dictionary containing fingerprint data
    """
    try:
        # Generate fingerprint using chromaprint
        duration, fingerprint = acoustid.fingerprint_file(str(audio_path))

        # Convert fingerprint to string if it's bytes
        if isinstance(fingerprint, bytes):
            fingerprint = fingerprint.decode("utf-8")

        return {
            "algorithm": "chromaprint",
            "version": "1.0",
            "duration": duration,
            "fingerprint": fingerprint,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to create audio fingerprint: {e}") from e


def save_audio_fingerprint(fingerprint_data: dict[str, Any], output_path: Path) -> None:
    """
    Save audio fingerprint data to JSON file.

    Args:
        fingerprint_data: Fingerprint dictionary from create_audio_fingerprint
        output_path: Path to save JSON file
    """
    with open(output_path, "w") as f:
        json.dump(fingerprint_data, f, indent=2)


def load_audio_fingerprint(fingerprint_path: Path) -> dict[str, Any]:
    """
    Load audio fingerprint data from JSON file.

    Args:
        fingerprint_path: Path to fingerprint JSON file

    Returns:
        Fingerprint dictionary
    """
    with open(fingerprint_path) as f:
        return json.load(f)
