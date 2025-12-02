"""Unit tests for ArcOS MPLS parsers."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_mpls import (
    ShowMplsReservedLabelBlockConfig,
    ShowMplsReservedLabelBlock,
)

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


class TestShowMplsReservedLabelBlockConfig:
    """Tests for ShowMplsReservedLabelBlockConfig parser."""

    def test_parse_sample(self):
        """Validate parsing of MPLS reserved-label-block running config."""
        sample_file = SAMPLES_DIR / "mpls_reserved_label_block_config.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()

        parser = ShowMplsReservedLabelBlockConfig(device="dummy")
        result = parser.cli(output=output)

        assert isinstance(result, dict)
        assert "network-instance" in result
        assert "default" in result["network-instance"]

        mpls = result["network-instance"]["default"]["mpls"]
        blocks = mpls["reserved-label-blocks"]

        # Verify rb1 (SRGB)
        assert "rb1" in blocks
        rb1 = blocks["rb1"]
        assert rb1["local-id"] == "rb1"
        assert rb1["lower-bound"] == 10000
        assert rb1["upper-bound"] == 19999
        assert rb1["usage"] == "ISIS_SRGB"
        assert rb1["protocol-identifier"] == "ISIS"
        assert rb1["protocol-name"] == "default"

        # Verify rb2 (SRLB)
        assert "rb2" in blocks
        rb2 = blocks["rb2"]
        assert rb2["local-id"] == "rb2"
        assert rb2["lower-bound"] == 20000
        assert rb2["upper-bound"] == 29999
        assert rb2["usage"] == "ISIS_SRLB"
        assert rb2["protocol-identifier"] == "ISIS"
        assert rb2["protocol-name"] == "default"

    def test_parameter_validation(self):
        """Test that invalid parameters raise ValueError."""
        from genie.libs.parser.arcos.utils import validate_input

        # Test validate_input directly since CLI validation only runs when output is None
        with pytest.raises(ValueError):
            validate_input("invalid;command", "network_instance")

        with pytest.raises(ValueError):
            validate_input("rb1;drop", "local_id")

    def test_valid_parameters_accepted(self):
        """Test that valid parameters are accepted."""
        parser = ShowMplsReservedLabelBlockConfig(device="dummy")

        # These should not raise
        result = parser.cli(network_instance="default", output="{}")
        assert isinstance(result, dict)

        result = parser.cli(network_instance="*", local_id="rb1", output="{}")
        assert isinstance(result, dict)


class TestShowMplsReservedLabelBlock:
    """Tests for ShowMplsReservedLabelBlock parser (operational state)."""

    def test_parse_sample(self):
        """Validate parsing of MPLS reserved-label-block operational state."""
        sample_file = SAMPLES_DIR / "mpls_reserved_label_block_state.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()

        parser = ShowMplsReservedLabelBlock(device="dummy")
        result = parser.cli(output=output)

        assert isinstance(result, dict)
        assert "network-instance" in result
        assert "default" in result["network-instance"]

        mpls = result["network-instance"]["default"]["mpls"]
        blocks = mpls["reserved-label-blocks"]

        # Verify rb1 (SRGB)
        assert "rb1" in blocks
        rb1 = blocks["rb1"]
        assert rb1["local-id"] == "rb1"
        assert rb1["lower-bound"] == 10000
        assert rb1["upper-bound"] == 19999
        assert rb1["usage"] == "ISIS_SRGB"
        assert rb1["protocol-identifier"] == "ISIS"
        assert rb1["protocol-name"] == "default"

        # Verify rb2 (SRLB)
        assert "rb2" in blocks
        rb2 = blocks["rb2"]
        assert rb2["local-id"] == "rb2"
        assert rb2["lower-bound"] == 20000
        assert rb2["upper-bound"] == 29999
        assert rb2["usage"] == "ISIS_SRLB"
        assert rb2["protocol-identifier"] == "ISIS"
        assert rb2["protocol-name"] == "default"

    def test_valid_parameters_accepted(self):
        """Test that valid parameters are accepted."""
        parser = ShowMplsReservedLabelBlock(device="dummy")

        # These should not raise
        result = parser.cli(network_instance="default", output="{}")
        assert isinstance(result, dict)

        result = parser.cli(network_instance="*", local_id="rb1", output="{}")
        assert isinstance(result, dict)
