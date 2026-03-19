"""Unit tests for ArcOS EVPN parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_evpn import ShowEvpn

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_evpn_state():
    """Validate EVPN global state fields are parsed."""
    output = (SAMPLES_DIR / "evpn.json").read_text()
    parser = ShowEvpn(device="dummy")
    result = parser.cli(output=output)

    assert result["anycast-gateway-mac"] == "aa:bb:cc:dd:ee:ff"
    assert result["df-election-time"] == 3
    assert result["router-ip-selected"] == "1.0.0.0"


def test_show_evpn_esi_info():
    """Validate ESI info counters are flattened."""
    output = (SAMPLES_DIR / "evpn.json").read_text()
    parser = ShowEvpn(device="dummy")
    result = parser.cli(output=output)

    esi = result["esi-info"]
    assert esi["esi-pruned-pkts"] == "0"
    assert esi["esi-pruned-octets"] == "0"


def test_show_evpn_duplicate_mac_detection():
    """Validate duplicate MAC detection state."""
    output = (SAMPLES_DIR / "evpn.json").read_text()
    parser = ShowEvpn(device="dummy")
    result = parser.cli(output=output)

    dmd = result["duplicate-mac-detection"]
    assert dmd["window"] == 180
    assert dmd["threshold"] == 5
    assert dmd["auto-recovery-time"] == 1


def test_show_evpn_arp_nd_suppression():
    """Validate ARP/ND suppression counters with typo normalization."""
    output = (SAMPLES_DIR / "evpn.json").read_text()
    parser = ShowEvpn(device="dummy")
    result = parser.cli(output=output)

    arp_nd = result["arp-nd-suppression-counters"]
    # Keys normalized from "supression" to "suppression"
    assert arp_nd["arp-suppression-counters"] == "0"
    assert arp_nd["nd-suppression-counters"] == "0"
