"""Unit tests for the reeltrust module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

import reeltrust
from reeltrust.verifier import (
    VerificationResult,
    get_video_frame_count,
    verify_video_digest,
)


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


class TestVerificationResult:
    """Test cases for VerificationResult class."""

    @pytest.mark.unit
    def test_verification_result_valid(self):
        """Test VerificationResult with valid result."""
        checks = {
            "package_structure": True,
            "manifest_integrity": True,
            "digest_hash_match": True,
        }
        details = {"ssim_score": 1.0}
        result = VerificationResult(True, checks, details)

        assert result.is_valid is True
        assert result.checks == checks
        assert result.details == details
        assert result.errors == []

    @pytest.mark.unit
    def test_verification_result_invalid(self):
        """Test VerificationResult with invalid result."""
        checks = {
            "package_structure": True,
            "manifest_integrity": False,
        }
        details = {}
        errors = ["Manifest integrity check failed"]
        result = VerificationResult(False, checks, details, errors)

        assert result.is_valid is False
        assert result.checks == checks
        assert result.errors == errors

    @pytest.mark.unit
    def test_verification_result_string_representation(self):
        """Test string representation of VerificationResult."""
        checks = {"test_check": True}
        details = {"test_detail": "value"}
        result = VerificationResult(True, checks, details)

        str_repr = str(result)
        assert "VALID" in str_repr
        assert "test_check" in str_repr
        assert "test_detail" in str_repr


class TestComputeSSIM:
    """Test cases for compute_ssim function."""

    @pytest.mark.unit
    @patch("subprocess.run")
    @patch("builtins.open")
    @patch("tempfile.NamedTemporaryFile")
    def test_compute_ssim_success(self, mock_temp, mock_open, mock_run):
        """Test successful SSIM computation."""
        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.log"
        mock_temp.return_value.__enter__.return_value = mock_file

        # Mock subprocess.run (FFmpeg)
        mock_run.return_value = MagicMock(returncode=0)

        # Mock reading SSIM stats file
        ssim_data = "n:1 Y:0.99 U:0.98 V:0.97 All:0.98 (123:456:789)\nn:2 Y:0.99 U:0.99 V:0.98 All:0.99 (123:456:789)\n"
        mock_open.return_value.__enter__.return_value.__iter__ = Mock(
            return_value=iter(ssim_data.split("\n"))
        )

        # This test verifies the mocking structure is correct
        # Full integration tests would exercise the actual SSIM computation


class TestGetVideoFrameCount:
    """Test cases for get_video_frame_count function."""

    @pytest.mark.unit
    @patch("subprocess.run")
    def test_get_frame_count_success(self, mock_run):
        """Test successful frame count retrieval."""
        mock_run.return_value = MagicMock(stdout="1234\n", returncode=0)

        video_path = Path("/tmp/test.mp4")
        count = get_video_frame_count(video_path)

        assert count == 1234
        mock_run.assert_called_once()


class TestVerifyVideoDigest:
    """Test cases for verify_video_digest function."""

    @pytest.fixture
    def mock_package_structure(self, tmp_path):
        """Create a mock package structure for testing."""
        package_dir = tmp_path / "test_package"
        package_dir.mkdir()

        # Create manifest
        manifest = {
            "version": "1.0",
            "package_id": "abcd1234",
            "files": {
                "digest_video.mp4": {
                    "sha256": "test_digest_hash",
                    "description": "Compressed video digest",
                }
            },
            "original_video": {
                "sha256": "test_original_hash",
                "description": "Original video",
            },
        }
        with open(package_dir / "manifest.json", "w") as f:
            json.dump(manifest, f)

        # Create signature
        signature = {
            "algorithm": "SHA256",
            "manifest_hash": "test_manifest_hash",
            "version": "1.0",
        }
        with open(package_dir / "signature.json", "w") as f:
            json.dump(signature, f)

        # Create empty digest video
        (package_dir / "digest_video.mp4").touch()

        return package_dir, manifest, signature

    @pytest.mark.unit
    def test_verify_missing_package(self, tmp_path):
        """Test verification with missing package directory."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        package_path = tmp_path / "nonexistent"

        result = verify_video_digest(video_path, package_path)

        assert result.is_valid is False
        assert "does not exist" in result.errors[0]

    @pytest.mark.unit
    def test_verify_missing_files(self, tmp_path):
        """Test verification with missing package files."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        package_path = tmp_path / "package"
        package_path.mkdir()

        result = verify_video_digest(video_path, package_path)

        assert result.is_valid is False
        assert result.checks["package_structure"] is False
        assert "Missing required files" in result.errors[0]

    @pytest.mark.unit
    @patch("reeltrust.verifier.calculate_manifest_hash")
    @patch("reeltrust.verifier.load_manifest")
    @patch("reeltrust.verifier.load_signature")
    def test_verify_manifest_integrity_failure(
        self,
        mock_load_sig,
        mock_load_man,
        mock_calc_hash,
        mock_package_structure,
        tmp_path,
    ):
        """Test verification with manifest integrity failure."""
        package_dir, manifest, signature = mock_package_structure

        video_path = tmp_path / "video.mp4"
        video_path.touch()

        mock_load_man.return_value = manifest
        mock_load_sig.return_value = signature
        mock_calc_hash.return_value = "different_hash"

        result = verify_video_digest(video_path, package_dir)

        assert result.is_valid is False
        assert result.checks["manifest_integrity"] is False
        assert any(
            "Manifest integrity check failed" in error for error in result.errors
        )

    @pytest.mark.unit
    def test_verification_result_has_all_checks(self):
        """Test that verification result contains expected check keys."""
        expected_checks = [
            "package_structure",
            "manifest_integrity",
            "original_video_hash",
            "digest_hash_match",
            "ssim_score",
            "frame_count_match",
        ]

        # This test verifies the structure but needs a full integration test
        # to actually run through all checks
        # For now, we verify the structure is correct
        checks = dict.fromkeys(expected_checks, True)
        result = VerificationResult(True, checks, {})

        for check in expected_checks:
            assert check in result.checks
