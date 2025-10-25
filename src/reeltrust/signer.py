"""Main signing orchestrator that creates verification packages."""

import tempfile
from pathlib import Path
from typing import Any

from .audio_fingerprint import create_audio_fingerprint, save_audio_fingerprint
from .metadata import create_metadata, save_metadata
from .signature import create_manifest, create_signature, save_manifest, save_signature
from .video_processor import compress_video, extract_audio, hash_file


def sign_video(
    video_path: Path,
    output_dir: Path,
    user_identity: str | None = None,
    gps_coords: tuple[float, float] | None = None,
    additional_info: dict[str, Any] | None = None,
    compression_width: int = 240,
) -> Path:
    """
    Create a signed verification package for a video file.

    This function:
    1. Compresses the video to a low-res reference digest
    2. Extracts and fingerprints the audio
    3. Generates metadata
    4. Creates a manifest with all file hashes
    5. Generates a signature

    Args:
        video_path: Path to input video file
        output_dir: Directory where package will be created
        user_identity: Optional user identity
        gps_coords: Optional GPS coordinates (latitude, longitude)
        additional_info: Optional additional metadata
        compression_width: Width for compressed video (default: 240)

    Returns:
        Path to the created package directory
    """
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir).resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Create package directory
    package_name = f"{video_path.stem}_package"
    package_dir = output_dir / package_name
    package_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating verification package for: {video_path.name}")
    print(f"Output directory: {package_dir}")

    # Step 1: Hash the original video
    print("1/5 Hashing original video...")
    original_video_hash = hash_file(video_path)
    print(f"    Original video hash: {original_video_hash[:16]}...")

    # Step 2: Compress video
    print(f"2/5 Compressing video to {compression_width}px width...")
    digest_video_path = package_dir / "digest_video.mp4"
    compress_video(video_path, digest_video_path, width=compression_width)
    digest_video_hash = hash_file(digest_video_path)
    print(f"    Digest created: {digest_video_path.name} ({digest_video_hash[:16]}...)")

    # Step 3: Extract and fingerprint audio
    print("3/5 Extracting and fingerprinting audio...")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_audio_path = Path(temp_dir) / "audio.wav"
        extract_audio(video_path, temp_audio_path)

        fingerprint_data = create_audio_fingerprint(temp_audio_path)
        audio_fingerprint_path = package_dir / "audio_fingerprint.json"
        save_audio_fingerprint(fingerprint_data, audio_fingerprint_path)

    audio_fingerprint_hash = hash_file(audio_fingerprint_path)
    print(f"    Fingerprint created: {fingerprint_data['duration']:.2f}s duration")

    # Step 4: Create metadata
    print("4/5 Generating metadata...")
    metadata = create_metadata(
        video_path,
        user_identity=user_identity,
        gps_coords=gps_coords,
        additional_info=additional_info,
    )
    metadata_path = package_dir / "metadata.json"
    save_metadata(metadata, metadata_path)
    metadata_hash = hash_file(metadata_path)
    print(f"    Metadata saved: {metadata_path.name}")

    # Step 5: Create manifest and signature
    print("5/5 Creating manifest and signature...")
    manifest = create_manifest(
        package_dir,
        original_video_hash,
        digest_video_hash,
        audio_fingerprint_hash,
        metadata_hash,
    )
    manifest_path = package_dir / "manifest.json"
    save_manifest(manifest, manifest_path)

    signature = create_signature(manifest)
    signature_path = package_dir / "signature.json"
    save_signature(signature, signature_path)
    print(f"    Signature created: {signature['manifest_hash'][:16]}...")

    print("\n✓ Verification package created successfully!")
    print(f"  Package ID: {manifest['package_id']}")
    print(f"  Location: {package_dir}")

    return package_dir
