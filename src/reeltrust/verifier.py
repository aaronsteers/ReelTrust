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


def _format_timestamp(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string (HH:MM:SS)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def compute_ssim(
    video1_path: Path, video2_path: Path, window_size: int = 60, fps: float = 30.0
) -> tuple[float, float, list[dict[str, Any]]]:
    """
    Compute SSIM (Structural Similarity Index) between two videos using FFmpeg.

    Uses FFmpeg's SSIM filter to compare two videos frame by frame, then applies
    non-overlapping fixed windows to detect localized tampering. Returns the MINIMUM
    average SSIM across all windows, ensuring that brief tampering cannot be hidden by
    high overall similarity.

    For example, a 1-second deepfake edit should be detected equally well in
    a 5-second video or a 5-minute video.

    Args:
        video1_path: Path to the first video
        video2_path: Path to the second video
        window_size: Number of frames per window (default: 60 = ~2 seconds at 30fps)
        fps: Frames per second for timestamp calculation (default: 30.0)

    Returns:
        Tuple of (min_window_ssim, min_frame_ssim, worst_windows) where:
        - min_window_ssim: Minimum window average SSIM score (0.0 to 1.0)
        - min_frame_ssim: Worst individual frame SSIM score (0.0 to 1.0)
        - worst_windows: List of worst 3 windows with timestamps and scores

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

        # Calculate the worst individual frame score
        min_frame_ssim = min(ssim_scores)

        # Apply sliding window to detect localized tampering
        # Instead of averaging over the entire video (which would hide brief edits),
        # we compute the average SSIM for each window and return the MINIMUM.
        # This ensures that tampering in any window is detected.

        num_frames = len(ssim_scores)

        # If video is shorter than one window, just average all frames
        if num_frames <= window_size:
            avg_ssim = sum(ssim_scores) / num_frames
            worst_windows = [
                {
                    "start_frame": 0,
                    "end_frame": num_frames - 1,
                    "start_time": "00:00:00",
                    "end_time": _format_timestamp((num_frames - 1) / fps),
                    "ssim": avg_ssim,
                }
            ]
            return avg_ssim, min_frame_ssim, worst_windows

        # Compute average SSIM for non-overlapping fixed windows
        # This ensures we get distinct regions when finding worst windows
        window_data = []
        i = 0
        while i < num_frames:
            # Calculate window boundaries
            start_frame = i
            end_frame = min(i + window_size - 1, num_frames - 1)
            window = ssim_scores[start_frame : end_frame + 1]

            if not window:  # Safety check
                break

            window_avg = sum(window) / len(window)
            window_min = min(window)  # Worst frame within this window

            # Find the index of the worst frame within this window
            min_frame_index = window.index(window_min)
            absolute_min_frame = start_frame + min_frame_index
            min_frame_time = _format_timestamp(absolute_min_frame / fps)

            start_time = _format_timestamp(start_frame / fps)
            end_time = _format_timestamp(end_frame / fps)

            window_data.append(
                {
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_time": start_time,
                    "end_time": end_time,
                    "ssim": window_avg,
                    "min_ssim": window_min,
                    "min_ssim_frame": absolute_min_frame,
                    "min_ssim_time": min_frame_time,
                }
            )

            # Move to next non-overlapping window
            i += window_size

        # Sort windows by SSIM (worst first) and take top 3
        sorted_windows = sorted(window_data, key=lambda x: x["ssim"])
        worst_windows = sorted_windows[:3]

        # Return the MINIMUM window average, worst frame, and worst windows
        min_window_ssim = worst_windows[0]["ssim"]
        return min_window_ssim, min_frame_ssim, worst_windows

    finally:
        # Clean up temporary stats file
        if stats_file.exists():
            stats_file.unlink()


def _merge_overlapping_worst_windows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Merge overlapping worst windows into consolidated regions.

    When multiple worst windows overlap (e.g., frames 4500-4649, 4501-4650, 4502-4651),
    they should be merged into a single window covering the full range with the
    worst metrics from any of the overlapping windows.

    Args:
        windows: List of window dictionaries sorted by SSIM score (worst first)

    Returns:
        List of merged windows with min/max ranges and worst metrics
    """
    if not windows:
        return []

    # Sort by start frame to detect overlaps
    sorted_by_position = sorted(windows, key=lambda x: x["start_frame"])

    merged = []
    current = sorted_by_position[0].copy()

    for next_window in sorted_by_position[1:]:
        # Check if windows overlap (next starts before or at current's end)
        if next_window["start_frame"] <= current["end_frame"]:
            # Merge: extend range and keep worst metrics
            current["end_frame"] = max(current["end_frame"], next_window["end_frame"])
            current["end_time"] = next_window["end_time"]  # Later time

            # Keep the worse average SSIM
            current["ssim"] = min(current["ssim"], next_window["ssim"])

            # Keep the worse minimum frame SSIM and its timestamp
            if next_window.get("min_ssim", 1.0) < current.get("min_ssim", 1.0):
                current["min_ssim"] = next_window["min_ssim"]
                current["min_ssim_frame"] = next_window["min_ssim_frame"]
                current["min_ssim_time"] = next_window["min_ssim_time"]
        else:
            # No overlap: save current and start new
            merged.append(current)
            current = next_window.copy()

    # Don't forget the last window
    merged.append(current)

    return merged


def extract_video_clip(
    video_path: Path,
    output_path: Path,
    start_time: float,
    duration: float = 5.0,
) -> None:
    """
    Extract a short clip from a video using FFmpeg.

    Args:
        video_path: Path to the source video
        output_path: Path for the output clip
        start_time: Start time in seconds (can be negative, will be clamped to 0)
        duration: Clip duration in seconds (default: 5.0)

    Raises:
        subprocess.CalledProcessError: If FFmpeg command fails
    """
    # Ensure start time is not negative
    start_time = max(0.0, start_time)

    cmd = [
        "ffmpeg",
        "-ss",
        str(start_time),
        "-i",
        str(video_path),
        "-t",
        str(duration),
        "-c",
        "copy",  # Copy codec for speed (no re-encoding)
        "-y",  # Overwrite output file
        str(output_path),
    ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)


def create_side_by_side_clip(
    video1_path: Path,
    video2_path: Path,
    output_path: Path,
    start_time: float,
    duration: float = 5.0,
    label1: str = "Provided",
    label2: str = "Expected",
    scale_video2_to_video1: bool = False,
) -> None:
    """
    Create a side-by-side comparison clip from two videos.

    Extracts clips from both videos at the same timestamp and creates a
    horizontally stacked comparison with labels, making visual differences
    immediately obvious.

    Args:
        video1_path: Path to the first video (left side)
        video2_path: Path to the second video (right side)
        output_path: Path for the output comparison clip
        start_time: Start time in seconds (will be clamped to 0)
        duration: Clip duration in seconds (default: 5.0)
        label1: Label for first video (default: "Provided")
        label2: Label for second video (default: "Expected")
        scale_video2_to_video1: If True, scale video2 to match video1's dimensions

    Raises:
        subprocess.CalledProcessError: If FFmpeg command fails
    """
    # Ensure start time is not negative
    start_time = max(0.0, start_time)

    # FFmpeg filter for side-by-side with labels
    # [0:v] = first input video stream (left - full resolution)
    # [1:v] = second input video stream (right - will be scaled up if needed)
    # drawtext adds labels at the top of each video
    # hstack horizontally stacks them side by side

    if scale_video2_to_video1:
        # Scale video2 (right side) to match video1's dimensions
        # Scale first, then stack, then add labels to the merged result
        filter_complex = (
            f"[1:v][0:v]scale2ref[right_scaled][left];"
            f"[left][right_scaled]hstack[merged];"
            f"[merged]drawtext=text='{label1}':fontcolor=white:fontsize=24:"
            f"box=1:boxcolor=black@0.5:boxborderw=5:x=(w/4-text_w/2):y=10,"
            f"drawtext=text='{label2}':fontcolor=white:fontsize=24:"
            f"box=1:boxcolor=black@0.5:boxborderw=5:x=(3*w/4-text_w/2):y=10"
        )
    else:
        # Simple case: both videos same dimensions
        filter_complex = (
            f"[0:v]drawtext=text='{label1}':fontcolor=white:fontsize=24:"
            f"box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=10[left];"
            f"[1:v]drawtext=text='{label2}':fontcolor=white:fontsize=24:"
            f"box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=10[right];"
            f"[left][right]hstack"
        )

    cmd = [
        "ffmpeg",
        "-ss",
        str(start_time),
        "-i",
        str(video1_path),
        "-ss",
        str(start_time),
        "-i",
        str(video2_path),
        "-t",
        str(duration),
        "-filter_complex",
        filter_complex,
        "-c:v",
        "libx264",  # Need to re-encode for the side-by-side
        "-preset",
        "fast",
        "-crf",
        "18",  # High quality
        "-y",  # Overwrite output file
        str(output_path),
    ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)


def merge_overlapping_windows(
    windows: list[dict[str, Any]], fps: float = 30.0, context_seconds: float = 1.5
) -> list[dict[str, Any]]:
    """
    Merge overlapping worst windows into consolidated clips.

    Takes the worst windows and merges any that overlap within a 5-second span
    (with 1.5s context padding). Returns consolidated clips with adjusted timestamps.

    Args:
        windows: List of worst window dictionaries with timestamps
        fps: Frames per second (default: 30.0)
        context_seconds: Seconds to add before the window for context (default: 1.5)

    Returns:
        List of merged clip dictionaries with start_time, end_time, and windows
    """
    if not windows:
        return []

    # Convert windows to clips with context padding
    clips = []
    for window in windows:
        # Start 1.5 seconds before the window (but not before 0)
        start_seconds = window["start_frame"] / fps
        padded_start = max(0.0, start_seconds - context_seconds)

        # End at the end of the window
        end_seconds = window["end_frame"] / fps

        clips.append(
            {
                "start_time": padded_start,
                "end_time": end_seconds,
                "windows": [window],
            }
        )

    # Sort by start time
    clips.sort(key=lambda x: x["start_time"])

    # Merge overlapping clips
    merged = []
    current = clips[0]

    for next_clip in clips[1:]:
        # Check if clips overlap or are within 5 seconds of each other
        if next_clip["start_time"] <= current["end_time"] + 5.0:
            # Merge: extend current clip and combine windows
            current["end_time"] = max(current["end_time"], next_clip["end_time"])
            current["windows"].extend(next_clip["windows"])
        else:
            # No overlap: save current and start new
            merged.append(current)
            current = next_clip

    # Don't forget the last clip
    merged.append(current)

    return merged


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


def get_video_properties(video_path: Path) -> dict[str, Any]:
    """
    Get video properties including frame count, FPS, and duration using ffprobe.

    Args:
        video_path: Path to the video file

    Returns:
        Dictionary with frame_count, fps, and duration

    Raises:
        subprocess.CalledProcessError: If ffprobe command fails
        ValueError: If properties cannot be determined
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-count_packets",
        "-show_entries",
        "stream=nb_read_packets,r_frame_rate,duration",
        "-of",
        "json",
        str(video_path),
    ]

    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    import json
    data = json.loads(result.stdout)

    stream = data.get("streams", [{}])[0]
    frame_count = int(stream.get("nb_read_packets", 0))

    # Parse frame rate (format: "30/1" or "30000/1001")
    fps_str = stream.get("r_frame_rate", "30/1")
    num, denom = map(int, fps_str.split("/"))
    fps = round(num / denom, 2)

    duration = float(stream.get("duration", 0))

    return {
        "frame_count": frame_count,
        "fps": fps,
        "duration": round(duration, 2),
    }


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
    3. Compress the provided video using the same parameters
    4. Compare digest hashes (SHA-256) - if identical, validation passes immediately
    5. If hashes differ, compute SSIM score and check against threshold
    6. Validate frame counts are identical

    Args:
        video_path: Path to the video file to verify
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

    # Step 3: Recreate the digest video from the provided video
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            recreated_digest_path = Path(tmp_dir) / "recreated_digest.mp4"
            compress_video(video_path, recreated_digest_path, width=compression_width)

            # Step 4: Compare digest hashes
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

                # Step 5: If hashes differ, compute SSIM
                try:
                    ssim_score, min_frame_ssim, worst_windows = compute_ssim(
                        recreated_digest_path, digest_path
                    )
                    details["ssim_score"] = ssim_score
                    details["min_frame_ssim"] = min_frame_ssim
                    details["worst_windows"] = worst_windows

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

            # Step 6: Validate frame counts
            try:
                recreated_frames = get_video_frame_count(recreated_digest_path)

                # Try to get stored frame count from manifest (optimization)
                # Fall back to computing it if not present
                stored_frames = manifest.get("files", {}).get("digest_video.mp4", {}).get("frame_count")
                if stored_frames is None:
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

    # Overall validation: determine if video is valid
    # We accept either:
    # - Exact digest hash match, OR
    # - SSIM score meets threshold
    # All other checks (package structure, manifest integrity, frame count) must pass

    required_checks = ["package_structure", "manifest_integrity", "frame_count_match"]
    required_pass = all(checks.get(check, False) for check in required_checks)

    # Content verification: either hash match OR SSIM pass
    content_match = checks.get("digest_hash_match", False) or checks.get(
        "ssim_score", False
    )

    is_valid = required_pass and content_match

    return VerificationResult(is_valid, checks, details, errors)
