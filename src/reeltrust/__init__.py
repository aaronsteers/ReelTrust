"""ReelTrust - A fully open source implementation for video/audio certification and verification."""

__version__ = "0.1.0"


def hello() -> str:
    """Return a friendly greeting."""
    return "Hello from ReelTrust!"


def get_version() -> str:
    """Return the current version."""
    return __version__


__all__ = ["__version__", "get_version", "hello"]
