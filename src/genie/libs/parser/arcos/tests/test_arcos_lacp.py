"""Unit tests for ArcOS LACP parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_lacp import ShowLacpInterface
from genie.metaparser.util.exceptions import SchemaEmptyParserError

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_lacp_interface_basic():
    """Validate LACP bond interface is parsed correctly."""
    sample_file = SAMPLES_DIR / "lacp_interface.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowLacpInterface(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "interfaces" in result

    interfaces = result["interfaces"]
    assert len(interfaces) == 1
    assert "bond111" in interfaces

    bond = interfaces["bond111"]
    assert bond["name"] == "bond111"
    assert bond["interval"] == "FAST"


def test_show_lacp_interface_members():
    """Validate LACP member state fields are parsed."""
    output = (SAMPLES_DIR / "lacp_interface.json").read_text()
    parser = ShowLacpInterface(device="dummy")
    result = parser.cli(output=output)

    bond = result["interfaces"]["bond111"]
    assert "members" in bond

    members = bond["members"]
    assert len(members) == 1
    assert "swp30" in members

    member = members["swp30"]
    assert member["interface"] == "swp30"
    assert member["timeout"] == "LONG"
    assert member["synchronization"] == "OUT_SYNC"
    assert member["aggregatable"] is False
    assert member["collecting"] is False
    assert member["distributing"] is False


def test_show_lacp_interface_empty():
    """Empty LACP data should raise SchemaEmptyParserError."""
    parser = ShowLacpInterface(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')
