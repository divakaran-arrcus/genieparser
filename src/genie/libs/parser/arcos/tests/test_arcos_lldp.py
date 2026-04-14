"""Unit tests for ArcOS LLDP parsers."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_lldp import ShowLldpState
from genie.metaparser.util.exceptions import SchemaEmptyParserError

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_lldp_state_basic():
    """Validate LLDP global state fields are parsed."""
    sample_file = SAMPLES_DIR / "lldp_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowLldpState(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert result["hello-timer"] == "30"
    assert result["system-name"] == "Metro2-L1-46DX-203-11"
    assert result["system-description"] == "Arrcus Operating System (ArcOS)"


def test_show_lldp_state_counters():
    """Validate LLDP counter values are parsed correctly."""
    output = (SAMPLES_DIR / "lldp_state.json").read_text()
    parser = ShowLldpState(device="dummy")
    result = parser.cli(output=output)

    assert "counters" in result
    counters = result["counters"]
    assert counters["frame-in"] == "519586"
    assert counters["frame-out"] == "519591"
    assert counters["frame-error-in"] == "0"
    assert counters["frame-discard"] == "0"
    assert counters["tlv-discard"] == "0"
    assert counters["tlv-unknown"] == "0"


def test_show_lldp_state_empty():
    """Empty LLDP data should raise SchemaEmptyParserError."""
    parser = ShowLldpState(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')
