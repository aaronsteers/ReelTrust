"""Command-line interface for ReelTrust."""

import shutil
import sys
from pathlib import Path

import click

from ulid import ULID

from .signer import sign_video
from .verifier import (
    create_side_by_side_clip,
    extract_video_clip,
    merge_overlapping_windows,
    verify_video_digest,
)

# Global report file handle for the current verification job
_report_file = None


def print_output(message: str = ""):
    """Print to console and append to verification report file.

    Args:
        message: The message to print (plain text or markdown)
    """
    # Print to console
    click.echo(message)

    # Append to report file
    if _report_file and not _report_file.closed:
        _report_file.write(message + "\n")
        _report_file.flush()


@click.group()
@click.version_option()
def cli():
    """ReelTrust - Content authenticity verification for video and audio media."""
    pass


@cli.command(name="create-package")
@click.argument(
    "video_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "-u",
    "--user",
    type=str,
    help="User identity (username, email, etc.).",
)
@click.option(
    "-g",
    "--gps",
    type=str,
    help="GPS coordinates as 'latitude,longitude' (e.g., '37.7749,-122.4194').",
)
def create_package(
    video_path: Path,
    user: str | None,
    gps: str | None,
):
    """Create a signed verification package for a video file."""
    try:
        # Parse GPS coordinates if provided
        gps_coords = None
        if gps:
            try:
                lat_str, lon_str = gps.split(",")
                gps_coords = (float(lat_str.strip()), float(lon_str.strip()))
            except (ValueError, TypeError):
                click.echo(
                    click.style(
                        "Error: Invalid GPS coordinates format. Use 'latitude,longitude'",
                        fg="red",
                    ),
                    err=True,
                )
                sys.exit(1)

        # Use default output directory
        output_dir = Path(".data/outputs/reel-trust-packages")

        # Create the signed package with default compression width
        package_dir = sign_video(
            video_path=video_path,
            output_dir=output_dir,
            user_identity=user,
            gps_coords=gps_coords,
            compression_width=240,
        )

        click.echo(f"\n✓ Success! Package created at: {package_dir}")

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.argument(
    "video_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.argument(
    "package_path",
    type=click.Path(exists=True, path_type=Path),
)
def verify(
    video_path: Path,
    package_path: Path,
):
    """Verify a video against its verification package."""
    global _report_file

    try:
        # Generate ULID for this verification job
        job_ulid = ULID()
        ulid_str = str(job_ulid)[-8:]  # Use last 8 characters
        video_basename = video_path.stem

        # Create verification output directory: .data/outputs/verification/{ulid}-{basename}/
        verification_dir = Path(".data/outputs/verification") / f"{ulid_str}-{video_basename}"
        verification_dir.mkdir(parents=True, exist_ok=True)

        # Open report file for this verification job
        report_path = verification_dir / "verification_report.md"
        _report_file = open(report_path, "w", encoding="utf-8")

        try:
            print_output(f"# Verification Report\n")
            print_output(f"**Job ID:** {ulid_str}")
            print_output(f"**Video:** {video_path}")
            print_output(f"**Package:** {package_path}")
            print_output(f"**Output Directory:** {verification_dir}")
            print_output(f"\n---\n")

            print_output(f"Verifying video: {video_path}")
            print_output(f"Against package: {package_path}")
            print_output(f"Verification output: {verification_dir}")
            print_output("This may take a moment...\n")

            # Perform verification with default compression width and threshold
            # Note: Threshold of 0.92 allows re-encoding (typically 0.93+) while catching tampering (typically <0.92)
            result = verify_video_digest(
                video_path=video_path,
                package_path=package_path,
                compression_width=240,
                ssim_threshold=0.92,
            )

            # Display results
            print_output("\n## Verification Result\n")
            if result.is_valid:
                print_output("**✓ VERIFICATION PASSED**")
                print_output("The video digest is authentic and matches the original video.\n")
            else:
                print_output("**✗ VERIFICATION FAILED**")
                print_output("The video digest does not match or has been tampered with.\n")

            # Display detailed checks
            print_output("### Verification Checks\n")
            for check_name, passed in result.checks.items():
                status = "✓" if passed else "✗"
                formatted_name = check_name.replace("_", " ").title()
                print_output(f"  {status} {formatted_name}")

            # Display details if available
            print_output("\n### Details\n")
            if result.details:
                for key, value in result.details.items():
                    # Skip worst_windows and fingerprints - we'll display them separately
                    if key in ("worst_windows", "fingerprints"):
                        continue
                    formatted_key = key.replace("_", " ").title()
                    if isinstance(value, float):
                        print_output(f"  {formatted_key}: {value:.4f}")
                    else:
                        print_output(f"  {formatted_key}: {value}")

            # Display fingerprint comparison results if available
            if "fingerprints" in result.details:
                fingerprint_data = result.details["fingerprints"]
                comparisons = fingerprint_data.get("comparisons", {})

                if comparisons:
                    print_output("\n### Fingerprint Analysis\n")

                    # dHash results
                    if "dhash" in comparisons:
                        dhash = comparisons["dhash"]
                        if "error" in dhash:
                            print_output(f"  **dHash:** ✗ {dhash['error']}")
                        else:
                            status = "✓" if dhash.get("is_valid", False) else "✗"
                            print_output(f"  **dHash:** {status}")
                            print_output(f"    - Worst Window Mean: {dhash.get('worst_window_mean_distance', 'N/A')} bits "
                                       f"(threshold: <{dhash.get('threshold_bits', 'N/A')})")
                            print_output(f"    - Overall Mean: {dhash.get('overall_mean_distance', 'N/A')} bits")
                            print_output(f"    - Perfect Matches: {dhash.get('perfect_match_pct', 'N/A')}%")

                    # pHash results
                    if "phash" in comparisons:
                        phash = comparisons["phash"]
                        if "error" in phash:
                            print_output(f"  **pHash:** ✗ {phash['error']}")
                        else:
                            status = "✓" if phash.get("is_valid", False) else "✗"
                            print_output(f"  **pHash:** {status}")
                            print_output(f"    - Worst Window Mean: {phash.get('worst_window_mean_distance', 'N/A')} bits "
                                       f"(threshold: <{phash.get('threshold_bits', 'N/A')})")
                            print_output(f"    - Overall Mean: {phash.get('overall_mean_distance', 'N/A')} bits")
                            print_output(f"    - Perfect Matches: {phash.get('perfect_match_pct', 'N/A')}%")

                    # Frame statistics results
                    if "frame_stats" in comparisons:
                        stats = comparisons["frame_stats"]
                        if "error" in stats:
                            print_output(f"  **Frame Statistics:** ✗ {stats['error']}")
                        else:
                            status = "✓" if stats.get("is_valid", False) else "✗"
                            print_output(f"  **Frame Statistics:** {status}")
                            print_output(f"    - Worst Window Correlation: {stats.get('worst_window_correlation', 'N/A')} "
                                       f"(threshold: ≥{stats.get('correlation_threshold', 'N/A')})")
                            print_output(f"    - Worst Window MAD: {stats.get('worst_window_mad', 'N/A')} "
                                       f"(threshold: <{stats.get('mad_threshold', 'N/A')})")
                            print_output(f"    - Overall Correlation: {stats.get('overall_correlation', 'N/A')}")

                    # Display worst windows for each fingerprint type
                    if "dhash" in comparisons and "worst_windows" in comparisons["dhash"]:
                        dhash_windows = comparisons["dhash"]["worst_windows"]
                        if dhash_windows:
                            print_output("\n#### dHash Worst Windows (highest Hamming distance)\n")
                            for i, window in enumerate(dhash_windows, 1):
                                print_output(
                                    f"  {i}. Frames {window['start_frame']}-{window['end_frame']} "
                                    f"({window['start_time']} - {window['end_time']}): "
                                    f"Avg: {window['mean_distance']} bits, "
                                    f"Max: {window['max_distance']} bits at {window['max_distance_time']}"
                                )

                    if "phash" in comparisons and "worst_windows" in comparisons["phash"]:
                        phash_windows = comparisons["phash"]["worst_windows"]
                        if phash_windows:
                            print_output("\n#### pHash Worst Windows (highest Hamming distance)\n")
                            for i, window in enumerate(phash_windows, 1):
                                print_output(
                                    f"  {i}. Frames {window['start_frame']}-{window['end_frame']} "
                                    f"({window['start_time']} - {window['end_time']}): "
                                    f"Avg: {window['mean_distance']} bits, "
                                    f"Max: {window['max_distance']} bits at {window['max_distance_time']}"
                                )

                    if "frame_stats" in comparisons and "worst_windows" in comparisons["frame_stats"]:
                        stats_windows = comparisons["frame_stats"]["worst_windows"]
                        if stats_windows:
                            print_output("\n#### Frame Statistics Worst Windows (lowest correlation)\n")
                            for i, window in enumerate(stats_windows, 1):
                                print_output(
                                    f"  {i}. Frames {window['start_frame']}-{window['end_frame']} "
                                    f"({window['start_time']} - {window['end_time']}): "
                                    f"Correlation: {window['correlation']}, "
                                    f"MAD: {window['mad']}, "
                                    f"Max MAD: {window['max_mad_value']} at {window['max_mad_time']}"
                                )

            # Display worst windows if SSIM was computed
            if "worst_windows" in result.details:
                worst_windows = result.details["worst_windows"]
                if worst_windows:
                    print_output("\n### Worst Quality Windows (lowest SSIM scores)\n")
                    for i, window in enumerate(worst_windows, 1):
                        if 'min_ssim' in window and 'min_ssim_time' in window:
                            min_ssim_str = f", Min: {window['min_ssim']:.4f} at {window['min_ssim_time']}"
                        else:
                            min_ssim_str = ""
                        print_output(
                            f"  {i}. Frames {window['start_frame']}-{window['end_frame']} "
                            f"({window['start_time']} - {window['end_time']}): "
                            f"Avg: {window['ssim']:.4f}{min_ssim_str}"
                        )

                    # Always extract clips for inspection
                    print_output("\n### Extracting Audit Clips\n")

                    # Use verification directory for audit clips
                    clips_dir = verification_dir / "audit-clips"
                    clips_dir.mkdir(parents=True, exist_ok=True)

                    # Merge overlapping windows into consolidated clips
                    merged_clips = merge_overlapping_windows(worst_windows)

                    # Get the stored digest video from the package for comparison
                    stored_digest_path = package_path / "digest_video.mp4"

                    # Extract each clip
                    for i, clip in enumerate(merged_clips, 1):
                        start_time = clip["start_time"]
                        duration = clip["end_time"] - clip["start_time"]

                        # Format filename with timestamp
                        start_str = clip["windows"][0]["start_time"].replace(":", "-")
                        clip_filename = f"clip_{i:02d}_at_{start_str}.mp4"
                        comparison_filename = f"comparison_{i:02d}_at_{start_str}.mp4"
                        clip_path = clips_dir / clip_filename
                        comparison_path = clips_dir / comparison_filename

                        try:
                            # Extract individual clip from provided video
                            extract_video_clip(
                                video_path, clip_path, start_time, duration
                            )
                            print_output(
                                f"  ✓ Saved clip {i}/{len(merged_clips)}: {clip_path}"
                            )

                            # Create side-by-side comparison
                            # Left: Full-res provided video (what user is verifying)
                            # Right: Stored digest scaled up to match (shows original quality)
                            # This gives best visual comparison - full quality vs scaled-up low-res
                            if stored_digest_path.exists():
                                print_output("  Creating side-by-side comparison...")
                                create_side_by_side_clip(
                                    video_path,  # Left: full resolution provided video
                                    stored_digest_path,  # Right: 240px digest (will be scaled up)
                                    comparison_path,
                                    start_time,
                                    duration,
                                    label1="Provided Video (Full Resolution)",
                                    label2="Original Digest (Scaled from 240px)",
                                    scale_video2_to_video1=True,  # Scale digest to match full-res
                                )
                                print_output(
                                    f"  ✓ Saved comparison {i}/{len(merged_clips)}: {comparison_path}"
                                )
                        except Exception as e:
                            print_output(
                                f"  ✗ Failed to extract clip {i}: {e}"
                            )

                    print_output(f"\nAll clips saved to: `{clips_dir}`")

            # Display errors if any
            if result.errors:
                print_output("\n### Errors\n")
                for error in result.errors:
                    print_output(f"  - {error}")

            # Display verification output directory
            print_output(f"\n---\n")
            print_output(f"📁 Verification artifacts saved to: {verification_dir}")

            # Exit with appropriate code
            sys.exit(0 if result.is_valid else 1)

        finally:
            # Close report file
            if _report_file and not _report_file.closed:
                _report_file.close()

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        if _report_file and not _report_file.closed:
            _report_file.close()
        sys.exit(1)
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        if _report_file and not _report_file.closed:
            _report_file.close()
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        if _report_file and not _report_file.closed:
            _report_file.close()
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
