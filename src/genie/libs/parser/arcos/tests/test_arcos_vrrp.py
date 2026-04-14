"""Unit tests for ArcOS VRRP parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_vrrp import ShowVrrp
from genie.metaparser.util.exceptions import SchemaEmptyParserError

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_vrrp_basic():
    """Validate VRRP group is parsed with correct key and fields."""
    sample_file = SAMPLES_DIR / "vrrp.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowVrrp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "vrrp-groups" in result

    groups = result["vrrp-groups"]
    assert len(groups) == 1

    # Key format: "interface:sub:af:address:vrid"
    expected_key = "swp1:0:ipv4:10.12.1.1:10"
    assert expected_key in groups

    grp = groups[expected_key]
    assert grp["interface"] == "swp1"
    assert grp["sub-id"] == 0
    assert grp["af"] == "ipv4"
    assert grp["address"] == "10.12.1.1"
    assert grp["virtual-router-id"] == 10


def test_show_vrrp_state_fields():
    """Validate VRRP state details including augmented fields."""
    output = (SAMPLES_DIR / "vrrp.json").read_text()
    parser = ShowVrrp(device="dummy")
    result = parser.cli(output=output)

    grp = result["vrrp-groups"]["swp1:0:ipv4:10.12.1.1:10"]

    # Standard fields
    assert grp["virtual-address"] == ["10.12.1.100"]
    assert grp["priority"] == 200
    assert grp["current-priority"] == 200
    assert grp["preempt"] is True
    assert grp["accept-mode"] is True
    assert grp["advertisement-interval"] == 300

    # Augmented fields (arcos-openconfig-if-ip-augments:*)
    assert grp["vrrp-version"] == "VRRP_V3"
    assert grp["virtual-router-mode"] == "MASTER"
    assert grp["virtual-mac-address"] == "00:00:5e:00:01:0a"
    assert grp["advertisement-sent"] == "12"
    assert grp["advertisement-received"] == "0"
    assert grp["advertisement-dropped"] == "0"


def test_show_vrrp_empty():
    """Empty interface data should raise SchemaEmptyParserError."""
    parser = ShowVrrp(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')
