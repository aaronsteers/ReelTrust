"""Command-line interface for ReelTrust."""

import sys
from pathlib import Path

import click

from .signer import sign_video
from .verifier import verify_video_digest


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
    default=Path(".data/outputs"),
    help="Output directory for the verification package.",
    show_default=True,
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

        # Create the signed package
        package_dir = sign_video(
            video_path=video_path,
            output_dir=output,
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
def verify(
    video_path: Path,
    package_path: Path,
    width: int,
    threshold: float,
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
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, float):
                    click.echo(f"  {formatted_key}: {value:.4f}")
                else:
                    click.echo(f"  {formatted_key}: {value}")

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
