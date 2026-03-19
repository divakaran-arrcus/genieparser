"""Unit tests for ArcOS VLAN parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_vlan import ShowVlan

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_vlan_count():
    """Validate all 13 VLANs are parsed."""
    output = (SAMPLES_DIR / "vlan.json").read_text()
    parser = ShowVlan(device="dummy")
    result = parser.cli(output=output)

    assert "vlans" in result
    vlans = result["vlans"]
    assert len(vlans) == 13


def test_show_vlan_ids():
    """Validate expected VLAN IDs are present."""
    output = (SAMPLES_DIR / "vlan.json").read_text()
    parser = ShowVlan(device="dummy")
    result = parser.cli(output=output)

    expected_ids = {
        "9", "2001", "2002", "2501", "3500", "3502", "3503",
        "3700", "3701", "3702", "3703", "3704", "3963",
    }
    assert set(result["vlans"].keys()) == expected_ids


def test_show_vlan_state_fields():
    """Validate VLAN state fields are flattened."""
    output = (SAMPLES_DIR / "vlan.json").read_text()
    parser = ShowVlan(device="dummy")
    result = parser.cli(output=output)

    vlan = result["vlans"]["2001"]
    assert vlan["vlan-id"] == 2001
    assert vlan["name"] == ""
    assert vlan["status"] == "ACTIVE"


def test_show_vlan_with_members():
    """Validate VLANs with members have interface list."""
    output = (SAMPLES_DIR / "vlan.json").read_text()
    parser = ShowVlan(device="dummy")
    result = parser.cli(output=output)

    assert result["vlans"]["2001"]["members"] == ["swp5.6001"]
    assert result["vlans"]["2002"]["members"] == ["swp5.6002"]
    assert result["vlans"]["2501"]["members"] == ["swp7"]
    assert result["vlans"]["3502"]["members"] == ["swp5.8001"]
    assert result["vlans"]["3700"]["members"] == ["swp29.6001"]


def test_show_vlan_without_members():
    """Validate VLANs without members have no members key."""
    output = (SAMPLES_DIR / "vlan.json").read_text()
    parser = ShowVlan(device="dummy")
    result = parser.cli(output=output)

    assert "members" not in result["vlans"]["9"]
    assert "members" not in result["vlans"]["3500"]
    assert "members" not in result["vlans"]["3503"]
    assert "members" not in result["vlans"]["3963"]


def test_show_vlan_all_active():
    """Validate all VLANs have ACTIVE status."""
    output = (SAMPLES_DIR / "vlan.json").read_text()
    parser = ShowVlan(device="dummy")
    result = parser.cli(output=output)

    for vlan_id, vlan_data in result["vlans"].items():
        assert vlan_data["status"] == "ACTIVE", (
            f"VLAN {vlan_id} status is {vlan_data['status']}, expected ACTIVE"
        )
