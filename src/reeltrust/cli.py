"""Command-line interface for ReelTrust."""

import shutil
import sys
from pathlib import Path

import click

from .signer import sign_video
from .verifier import (
    create_side_by_side_clip,
    extract_video_clip,
    merge_overlapping_windows,
    verify_video_digest,
)


@click.group()
@click.version_option()
def cli():
    """ReelTrust - Content authenticity verification for video and audio media."""
    pass


@cli.command()
@click.argument(
    "video_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for the verification package (default: .data/outputs/reel-trust-packages/{video_name}).",
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
@click.option(
    "-w",
    "--width",
    type=int,
    default=240,
    help="Width for compressed video digest.",
    show_default=True,
)
def sign(
    video_path: Path,
    output: Path,
    user: str | None,
    gps: str | None,
    width: int,
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

        # Determine output directory with deterministic naming
        # Note: sign_video creates a subdirectory named {video}_package inside output_dir
        if output is None:
            # Default: .data/outputs/reel-trust-packages/
            # This will create .data/outputs/reel-trust-packages/{video}_package/
            output_dir = Path(".data/outputs/reel-trust-packages")
        else:
            output_dir = output

        # Create the signed package
        package_dir = sign_video(
            video_path=video_path,
            output_dir=output_dir,
            user_identity=user,
            gps_coords=gps_coords,
            compression_width=width,
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
@click.option(
    "-w",
    "--width",
    type=int,
    default=240,
    help="Width for compressed video digest.",
    show_default=True,
)
@click.option(
    "-t",
    "--threshold",
    type=float,
    default=0.99,
    help="Minimum SSIM threshold for validation.",
    show_default=True,
)
@click.option(
    "--clips-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory to save clips (default: .data/outputs/audit-clips).",
)
def verify(
    video_path: Path,
    package_path: Path,
    width: int,
    threshold: float,
    clips_dir: Path | None,
):
    """Verify a video against its verification package."""
    try:
        click.echo(f"Verifying video: {video_path}")
        click.echo(f"Against package: {package_path}")
        click.echo("This may take a moment...\n")

        # Perform verification
        result = verify_video_digest(
            video_path=video_path,
            package_path=package_path,
            compression_width=width,
            ssim_threshold=threshold,
        )

        # Display results
        if result.is_valid:
            click.echo(click.style("\n✓ VERIFICATION PASSED", fg="green", bold=True))
            click.echo(
                "The video digest is authentic and matches the original video.\n"
            )
        else:
            click.echo(click.style("\n✗ VERIFICATION FAILED", fg="red", bold=True))
            click.echo("The video digest does not match or has been tampered with.\n")

        # Display detailed checks
        click.echo("Verification Checks:")
        for check_name, passed in result.checks.items():
            status_symbol = (
                click.style("✓", fg="green") if passed else click.style("✗", fg="red")
            )
            formatted_name = check_name.replace("_", " ").title()
            click.echo(f"  {status_symbol} {formatted_name}")

        # Display details if available
        if result.details:
            click.echo("\nDetails:")
            for key, value in result.details.items():
                # Skip worst_windows - we'll display it separately
                if key == "worst_windows":
                    continue
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, float):
                    click.echo(f"  {formatted_key}: {value:.4f}")
                else:
                    click.echo(f"  {formatted_key}: {value}")

        # Display worst windows if SSIM was computed
        if "worst_windows" in result.details:
            worst_windows = result.details["worst_windows"]
            if worst_windows:
                click.echo("\nWorst Quality Windows (lowest SSIM scores):")
                for i, window in enumerate(worst_windows, 1):
                    if 'min_ssim' in window and 'min_ssim_time' in window:
                        min_ssim_str = f", Min: {window['min_ssim']:.4f} at {window['min_ssim_time']}"
                    else:
                        min_ssim_str = ""
                    click.echo(
                        f"  {i}. Frames {window['start_frame']}-{window['end_frame']} "
                        f"({window['start_time']} - {window['end_time']}): "
                        f"Avg: {window['ssim']:.4f}{min_ssim_str}"
                    )

                # Always extract clips for inspection
                click.echo("\nExtracting video clips for inspection...")

                # Determine clips directory and include video basename
                base_clips_dir = clips_dir if clips_dir else Path(".data/outputs/audit-clips")
                video_basename = video_path.stem  # Filename without extension
                output_dir = base_clips_dir / video_basename

                # Clear existing clips for this video to avoid confusion
                if output_dir.exists():
                    shutil.rmtree(output_dir)

                output_dir.mkdir(parents=True, exist_ok=True)

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
                    clip_path = output_dir / clip_filename
                    comparison_path = output_dir / comparison_filename

                    try:
                        # Extract individual clip from provided video
                        extract_video_clip(
                            video_path, clip_path, start_time, duration
                        )
                        click.echo(
                            f"  ✓ Saved clip {i}/{len(merged_clips)}: {clip_path}"
                        )

                        # Create side-by-side comparison
                        # Left: Full-res provided video (what user is verifying)
                        # Right: Stored digest scaled up to match (shows original quality)
                        # This gives best visual comparison - full quality vs scaled-up low-res
                        if stored_digest_path.exists():
                            click.echo("  Creating side-by-side comparison...")
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
                            click.echo(
                                f"  ✓ Saved comparison {i}/{len(merged_clips)}: {comparison_path}"
                            )
                    except Exception as e:
                        click.echo(
                            click.style(
                                f"  ✗ Failed to extract clip {i}: {e}", fg="red"
                            )
                        )

                click.echo(f"\nAll clips saved to: {output_dir}")

        # Display errors if any
        if result.errors:
            click.echo(click.style("\nErrors:", fg="red"))
            for error in result.errors:
                click.echo(click.style(f"  - {error}", fg="red"))

        # Exit with appropriate code
        sys.exit(0 if result.is_valid else 1)

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except RuntimeError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
