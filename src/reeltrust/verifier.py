"""Video digest verification module for ReelTrust."""

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from reeltrust.signature import calculate_manifest_hash, load_manifest, load_signature
from reeltrust.video_processor import compress_video, hash_file


class VerificationResult:
    """Result of a video digest verification."""

    def __init__(
        self,
        is_valid: bool,
        checks: Dict[str, bool],
        details: Dict[str, Any],
        errors: Optional[list[str]] = None,
    ):
        """
        Initialize a verification result.

        Args:
            is_valid: Overall verification status (True if all checks pass)
            checks: Dictionary of individual check results
            details: Additional details about the verification
            errors: List of error messages if verification failed
        """
        self.is_valid = is_valid
        self.checks = checks
        self.details = details
        self.errors = errors or []

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        status = "VALID" if self.is_valid else "INVALID"
        lines = [f"Verification Result: {status}"]
        lines.append("\nChecks:")
        for check_name, passed in self.checks.items():
            status_symbol = "✓" if passed else "✗"
            lines.append(f"  {status_symbol} {check_name}")

        if self.details:
            lines.append("\nDetails:")
            for key, value in self.details.items():
                lines.append(f"  {key}: {value}")

        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)


def compute_ssim(video1_path: Path, video2_path: Path) -> float:
    """
    Compute SSIM (Structural Similarity Index) between two videos using FFmpeg.

    Uses FFmpeg's SSIM filter to compare two videos frame by frame.
    Returns the average SSIM score across all frames.

    Args:
        video1_path: Path to the first video
        video2_path: Path to the second video

    Returns:
        Average SSIM score (0.0 to 1.0, where 1.0 is identical)

    Raises:
        subprocess.CalledProcessError: If FFmpeg command fails
        ValueError: If SSIM output cannot be parsed
    """
    # Create a temporary file for SSIM statistics
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp_file:
        stats_file = Path(tmp_file.name)

    try:
        # FFmpeg command to compute SSIM
        # -filter_complex compares the two inputs using the SSIM filter
        # The SSIM filter outputs statistics to the specified file
        cmd = [
            "ffmpeg",
            "-i",
            str(video1_path),
            "-i",
            str(video2_path),
            "-filter_complex",
            f"ssim=stats_file={stats_file}",
            "-f",
            "null",
            "-",
        ]

        # Run FFmpeg (output goes to null, we only care about the stats file)
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Parse the SSIM statistics file
        # Each line contains: n:<frame> Y:<Y_ssim> U:<U_ssim> V:<V_ssim> All:<overall_ssim> (R:G:B)
        ssim_scores = []
        with open(stats_file) as f:
            for line in f:
                # Extract the overall SSIM score (All: field)
                if "All:" in line:
                    all_part = line.split("All:")[1].split()[0]
                    ssim_scores.append(float(all_part))

        if not ssim_scores:
            raise ValueError("No SSIM scores found in FFmpeg output")

        # Return the average SSIM score across all frames
        avg_ssim = sum(ssim_scores) / len(ssim_scores)
        return avg_ssim

    finally:
        # Clean up temporary stats file
        if stats_file.exists():
            stats_file.unlink()


def get_video_frame_count(video_path: Path) -> int:
    """
    Get the frame count of a video using ffprobe.

    Args:
        video_path: Path to the video file

    Returns:
        Number of frames in the video

    Raises:
        subprocess.CalledProcessError: If ffprobe command fails
        ValueError: If frame count cannot be determined
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-count_packets",
        "-show_entries",
        "stream=nb_read_packets",
        "-of",
        "csv=p=0",
        str(video_path),
    ]

    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    frame_count = int(result.stdout.strip())
    return frame_count


def verify_video_digest(
    video_path: Path,
    package_path: Path,
    compression_width: int = 240,
    ssim_threshold: float = 0.99,
) -> VerificationResult:
    """
    Verify that a video digest package is authentic and matches the original video.

    This function recreates the video digest from the original video using the same
    compression pipeline, then compares it with the digest in the package.

    Verification steps:
    1. Validate package structure (manifest, signature, digest video exist)
    2. Verify manifest signature integrity
    3. Compress the original video using the same parameters
    4. Compare digest hashes (SHA-256)
    5. If hashes differ, compute SSIM score and check against threshold
    6. Validate frame counts are identical

    Args:
        video_path: Path to the original video file
        package_path: Path to the verification package directory
        compression_width: Width for compression (default: 240px)
        ssim_threshold: Minimum SSIM score for validation (default: 0.99)

    Returns:
        VerificationResult object containing validation status and details

    Example:
        >>> result = verify_video_digest(
        ...     Path("original.mp4"), Path("original_package"), width=240
        ... )
        >>> if result.is_valid:
        ...     print("Video digest is valid!")
    """
    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}
    errors: list[str] = []

    # Step 1: Validate package structure
    manifest_path = package_path / "manifest.json"
    signature_path = package_path / "signature.json"
    digest_path = package_path / "digest_video.mp4"

    if not package_path.exists() or not package_path.is_dir():
        errors.append(f"Package directory does not exist: {package_path}")
        return VerificationResult(False, checks, details, errors)

    missing_files = []
    if not manifest_path.exists():
        missing_files.append("manifest.json")
    if not signature_path.exists():
        missing_files.append("signature.json")
    if not digest_path.exists():
        missing_files.append("digest_video.mp4")

    if missing_files:
        errors.append(f"Missing required files: {', '.join(missing_files)}")
        checks["package_structure"] = False
        return VerificationResult(False, checks, details, errors)

    checks["package_structure"] = True

    # Step 2: Verify manifest signature integrity
    try:
        manifest = load_manifest(manifest_path)
        signature = load_signature(signature_path)

        # Recalculate manifest hash and compare with signature
        calculated_hash = calculate_manifest_hash(manifest)
        stored_hash = signature.get("manifest_hash", "")

        if calculated_hash == stored_hash:
            checks["manifest_integrity"] = True
        else:
            checks["manifest_integrity"] = False
            errors.append(
                f"Manifest integrity check failed. "
                f"Expected: {stored_hash}, Got: {calculated_hash}"
            )
    except Exception as e:
        checks["manifest_integrity"] = False
        errors.append(f"Failed to verify manifest: {e!s}")
        return VerificationResult(False, checks, details, errors)

    # Step 3: Verify original video hash matches manifest
    try:
        original_hash = hash_file(video_path)
        manifest_original_hash = manifest.get("original_video", {}).get("sha256", "")

        if original_hash == manifest_original_hash:
            checks["original_video_hash"] = True
        else:
            checks["original_video_hash"] = False
            errors.append(
                f"Original video hash mismatch. This video does not match the package. "
                f"Expected: {manifest_original_hash}, Got: {original_hash}"
            )
            # This is a critical failure - no point continuing
            return VerificationResult(False, checks, details, errors)
    except Exception as e:
        checks["original_video_hash"] = False
        errors.append(f"Failed to hash original video: {e!s}")
        return VerificationResult(False, checks, details, errors)

    # Step 4: Recreate the digest video
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            recreated_digest_path = Path(tmp_dir) / "recreated_digest.mp4"
            compress_video(video_path, recreated_digest_path, width=compression_width)

            # Step 5: Compare digest hashes
            recreated_hash = hash_file(recreated_digest_path)
            stored_digest_hash = (
                manifest.get("files", {}).get("digest_video.mp4", {}).get("sha256", "")
            )

            details["recreated_digest_hash"] = recreated_hash
            details["stored_digest_hash"] = stored_digest_hash

            if recreated_hash == stored_digest_hash:
                checks["digest_hash_match"] = True
                checks["ssim_score"] = True  # Hash match means perfect similarity
                details["ssim_score"] = 1.0
            else:
                checks["digest_hash_match"] = False

                # Step 6: If hashes differ, compute SSIM
                try:
                    ssim_score = compute_ssim(recreated_digest_path, digest_path)
                    details["ssim_score"] = ssim_score

                    if ssim_score >= ssim_threshold:
                        checks["ssim_score"] = True
                        details["ssim_note"] = (
                            f"Hashes differ but SSIM score {ssim_score:.4f} "
                            f"meets threshold {ssim_threshold}"
                        )
                    else:
                        checks["ssim_score"] = False
                        errors.append(
                            f"SSIM score {ssim_score:.4f} below threshold {ssim_threshold}. "
                            f"Video digest may have been tampered with."
                        )
                except Exception as e:
                    checks["ssim_score"] = False
                    errors.append(f"Failed to compute SSIM: {e!s}")

            # Step 7: Validate frame counts
            try:
                recreated_frames = get_video_frame_count(recreated_digest_path)
                stored_frames = get_video_frame_count(digest_path)

                details["recreated_frame_count"] = recreated_frames
                details["stored_frame_count"] = stored_frames

                if recreated_frames == stored_frames:
                    checks["frame_count_match"] = True
                else:
                    checks["frame_count_match"] = False
                    errors.append(
                        f"Frame count mismatch. Expected: {stored_frames}, "
                        f"Got: {recreated_frames}"
                    )
            except Exception as e:
                checks["frame_count_match"] = False
                errors.append(f"Failed to verify frame counts: {e!s}")

    except Exception as e:
        checks["digest_recreation"] = False
        errors.append(f"Failed to recreate digest video: {e!s}")
        return VerificationResult(False, checks, details, errors)

    # Overall validation: all checks must pass
    is_valid = all(checks.values())

    return VerificationResult(is_valid, checks, details, errors)
