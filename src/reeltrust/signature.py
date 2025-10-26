"""Digital signature and manifest generation."""

import hashlib
import json
from pathlib import Path
from typing import Any


def calculate_manifest_hash(manifest_data: dict[str, Any]) -> str:
    """
    Calculate SHA-256 hash of manifest data.

    Args:
        manifest_data: Manifest dictionary

    Returns:
        Hex string of SHA-256 hash
    """
    # Convert to canonical JSON (sorted keys, no whitespace)
    canonical_json = json.dumps(manifest_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode()).hexdigest()


def create_manifest(
    package_dir: Path,
    original_video_hash: str,
    digest_video_hash: str,
    audio_fingerprint_hash: str,
    metadata_hash: str,
    digest_properties: dict[str, Any] | None = None,
    fingerprint_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a manifest containing all file hashes and references.

    Args:
        package_dir: Directory containing the package files
        original_video_hash: SHA-256 hash of original video
        digest_video_hash: SHA-256 hash of compressed digest video
        audio_fingerprint_hash: SHA-256 hash of audio fingerprint JSON
        metadata_hash: SHA-256 hash of metadata JSON
        digest_properties: Optional dict with frame_count, fps, duration (for optimization)
        fingerprint_metadata: Optional dict with perceptual fingerprint metadata

    Returns:
        Manifest dictionary
    """
    digest_entry = {
        "sha256": digest_video_hash,
        "description": "Compressed reference video digest",
    }
    if digest_properties:
        if "frame_count" in digest_properties:
            digest_entry["frame_count"] = digest_properties["frame_count"]
        if "fps" in digest_properties:
            digest_entry["fps"] = digest_properties["fps"]
        if "duration" in digest_properties:
            digest_entry["duration"] = digest_properties["duration"]

    manifest = {
        "version": "1.0",
        "package_id": original_video_hash[
            :16
        ],  # Use first 16 chars of original video hash as ID
        "files": {
            "digest_video.mp4": digest_entry,
            "audio_fingerprint.json": {
                "sha256": audio_fingerprint_hash,
                "description": "Audio fingerprint data",
            },
            "metadata.json": {
                "sha256": metadata_hash,
                "description": "Video metadata and creation info",
            },
        },
        "original_video": {
            "sha256": original_video_hash,
            "description": "SHA-256 hash of the original source video",
        },
    }

    # Add fingerprint metadata if provided
    if fingerprint_metadata:
        manifest["fingerprints"] = fingerprint_metadata

    return manifest


def create_signature(manifest_data: dict[str, Any]) -> dict[str, Any]:
    """
    Create a signature for the manifest.

    For this POC, we're using SHA-256 hashing. In the future, this will
    support cryptographic signing with RSA/ECDSA and certificate chains.

    Args:
        manifest_data: Manifest dictionary

    Returns:
        Signature dictionary
    """
    manifest_hash = calculate_manifest_hash(manifest_data)

    signature = {
        "version": "1.0",
        "algorithm": "SHA-256",
        "manifest_hash": manifest_hash,
        "note": "This is a cryptographic hash. Future versions will support digital signatures with certificate chains.",
    }

    return signature


def save_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    """
    Save manifest to JSON file.

    Args:
        manifest: Manifest dictionary
        output_path: Path to save JSON file
    """
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)


def save_signature(signature: dict[str, Any], output_path: Path) -> None:
    """
    Save signature to JSON file.

    Args:
        signature: Signature dictionary
        output_path: Path to save JSON file
    """
    with open(output_path, "w") as f:
        json.dump(signature, f, indent=2)


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """
    Load manifest from JSON file.

    Args:
        manifest_path: Path to manifest JSON file

    Returns:
        Manifest dictionary
    """
    with open(manifest_path) as f:
        return json.load(f)


def load_signature(signature_path: Path) -> dict[str, Any]:
    """
    Load signature from JSON file.

    Args:
        signature_path: Path to signature JSON file

    Returns:
        Signature dictionary
    """
    with open(signature_path) as f:
        return json.load(f)
