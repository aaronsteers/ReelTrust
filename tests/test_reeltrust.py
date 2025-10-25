"""Unit tests for the reeltrust module."""

import pytest

import reeltrust


class TestReelTrust:
    """Test cases for the main module."""

    @pytest.mark.unit
    def test_hello(self):
        """Test the hello function."""
        result = reeltrust.hello()
        assert result == "Hello from ReelTrust!"
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_get_version(self):
        """Test the get_version function."""
        version = reeltrust.get_version()
        assert version == "0.1.0"
        assert isinstance(version, str)

    @pytest.mark.unit
    def test_version_attribute(self):
        """Test the __version__ attribute."""
        assert hasattr(reeltrust, "__version__")
        assert reeltrust.__version__ == "0.1.0"

    @pytest.mark.unit
    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        expected_exports = ["hello", "get_version", "__version__"]
        assert hasattr(reeltrust, "__all__")
        assert all(item in reeltrust.__all__ for item in expected_exports)
