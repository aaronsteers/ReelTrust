"""Command-line interface for ReelTrust."""

import sys
from pathlib import Path

import click

from .signer import sign_video


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


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
