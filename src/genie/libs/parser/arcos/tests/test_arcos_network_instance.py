"""Unit tests for ArcOS network-instance parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_network_instance import ShowNetworkInstance

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def _parse_sample():
    """Helper to parse the L2VPN network-instance sample."""
    sample_file = SAMPLES_DIR / "network_instance_l2vpn.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowNetworkInstance(device="dummy")
    return parser.cli(output=output)


def test_show_network_instance_name():
    """Validate NI name is parsed correctly."""
    result = _parse_sample()

    assert "network-instance" in result
    ni = result["network-instance"]
    assert "Leaf1-Leaf2-EPLAN(M2M)-1" in ni
    assert ni["Leaf1-Leaf2-EPLAN(M2M)-1"]["name"] == "Leaf1-Leaf2-EPLAN(M2M)-1"


def test_show_network_instance_interfaces():
    """Validate interface list is parsed correctly."""
    result = _parse_sample()

    ni = result["network-instance"]["Leaf1-Leaf2-EPLAN(M2M)-1"]
    interfaces = ni.get("interfaces", {})

    assert len(interfaces) == 2
    assert "swp5.6001" in interfaces
    assert "swp6.6001" in interfaces

    swp5 = interfaces["swp5.6001"]
    assert swp5["interface"] == "swp5"
    assert swp5["subinterface"] == 6001

    swp6 = interfaces["swp6.6001"]
    assert swp6["interface"] == "swp6"
    assert swp6["subinterface"] == 6001


def test_show_network_instance_fdb():
    """Validate MAC table entries are parsed correctly."""
    result = _parse_sample()

    ni = result["network-instance"]["Leaf1-Leaf2-EPLAN(M2M)-1"]
    fdb = ni.get("fdb", {})
    mac_entries = fdb.get("mac-entries", {})

    assert len(mac_entries) == 2
    assert "5c:07:58:74:62:03" in mac_entries
    assert "48:0f:cf:af:67:37" in mac_entries

    entry = mac_entries["5c:07:58:74:62:03"]
    assert entry["vlan"] == 6001
    assert entry["entry-type"] == "DYNAMIC"


def test_show_network_instance_l2rib():
    """Validate L2RIB state fields are parsed correctly."""
    result = _parse_sample()

    ni = result["network-instance"]["Leaf1-Leaf2-EPLAN(M2M)-1"]
    l2rib = ni.get("l2rib", {})

    assert l2rib["id"] == 2001
    assert l2rib["name"] == "Leaf1-Leaf2-EPLAN(M2M)-1"
    assert l2rib["type"] == "TABLE_TYPE_VLAN"
    assert l2rib["vni"] == 2001
    assert l2rib["advertise-mac-routes"] is True
    assert l2rib["maximum-mac-entries"] == 2048
    assert l2rib["pkt-action"] == "FLOOD_ACTION"
    assert l2rib["local-label"] == 2001
    assert l2rib["is-irb"] is False
    assert l2rib["mac-count"] == 1
    assert l2rib["mac-ipv4-count"] == 2


def test_show_network_instance_bgp():
    """Validate BGP state fields are parsed correctly."""
    result = _parse_sample()

    ni = result["network-instance"]["Leaf1-Leaf2-EPLAN(M2M)-1"]
    bgp = ni.get("bgp", {})

    assert bgp["as"] == 65002
    assert bgp["router-id"] == "1.0.0.0"
    assert bgp["route-distinguisher"] == "1.0.0.0:2001"
    assert bgp["label-allocation-mode"] == "INSTANCE_LABEL"
    assert bgp["control-word"] is True
    assert bgp["flow-label"] is True
    assert bgp["vni-evi"] == 2001
    assert bgp["tunnel-type"] == "MPLS"
    assert bgp["total-paths"] == 0
    assert bgp["total-prefixes"] == 0

    # afi-safis
    assert "afi-safis" in bgp
    assert bgp["afi-safis"] == ["L2VPN_EVPN"]


def test_show_network_instance_route_targets():
    """Validate route-targets are parsed correctly."""
    result = _parse_sample()

    ni = result["network-instance"]["Leaf1-Leaf2-EPLAN(M2M)-1"]
    bgp = ni.get("bgp", {})
    route_targets = bgp.get("route-targets", [])

    assert len(route_targets) == 2

    rt_both = route_targets[0]
    assert rt_both["route-target"] == "2001:2001"
    assert rt_both["route-target-type"] == "both"

    rt_import = route_targets[1]
    assert rt_import["route-target"] == "3001:3001"
    assert rt_import["route-target-type"] == "import"


# ---- L3VPN tests ----


def _parse_l3vpn_sample():
    """Helper to parse the L3VPN network-instance sample."""
    sample_file = SAMPLES_DIR / "network_instance_l3vpn.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowNetworkInstance(device="dummy")
    return parser.cli(output=output)


def test_l3vpn_name():
    """Validate L3VPN NI name is parsed."""
    result = _parse_l3vpn_sample()
    ni = result["network-instance"]
    assert "ECMP-Leaf1-Leaf2-Leaf3-L3VPN-01" in ni


def test_l3vpn_table_connections():
    """Validate table-connections are parsed with namespace stripping."""
    result = _parse_l3vpn_sample()
    ni = result["network-instance"]["ECMP-Leaf1-Leaf2-Leaf3-L3VPN-01"]
    tc = ni.get("table-connections", [])

    assert len(tc) == 4

    # First entry: DIRECTLY_CONNECTED -> BGP IPv6 with src-dst-instances
    assert tc[0]["src-protocol"] == "DIRECTLY_CONNECTED"
    assert tc[0]["dst-protocol"] == "BGP"
    assert tc[0]["address-family"] == "IPV6"
    assert len(tc[0]["src-dst-instances"]) == 1
    assert tc[0]["src-dst-instances"][0]["src-instance"] == "directly_connected"

    # Third entry: STATIC -> BGP IPv6 without src-dst-instances
    assert tc[2]["src-protocol"] == "STATIC"
    assert tc[2]["dst-protocol"] == "BGP"
    assert "src-dst-instances" not in tc[2]


def test_l3vpn_rib_options():
    """Validate rib-options are parsed."""
    result = _parse_l3vpn_sample()
    ni = result["network-instance"]["ECMP-Leaf1-Leaf2-Leaf3-L3VPN-01"]
    rib = ni.get("rib-options", {})

    assert rib["ipv4"]["max-prefix-limit"] == 1000
    assert rib["ipv4"]["threshold"] == 90
    assert rib["ipv6"]["max-prefix-limit"] == 100
    assert rib["ipv6"]["threshold"] == 90


def test_l3vpn_l3vrf():
    """Validate l3vrf state is parsed."""
    result = _parse_l3vpn_sample()
    ni = result["network-instance"]["ECMP-Leaf1-Leaf2-Leaf3-L3VPN-01"]
    l3vrf = ni.get("l3vrf", {})

    assert l3vrf["vrf-interface"] == "vrf10001"
    assert l3vrf["table-id"] == 1073741826


def test_l3vpn_bgp_route_targets():
    """Validate L3VPN route-targets from rt-afi-safis path."""
    result = _parse_l3vpn_sample()
    ni = result["network-instance"]["ECMP-Leaf1-Leaf2-Leaf3-L3VPN-01"]
    bgp = ni.get("bgp", {})

    assert bgp["as"] == 65002
    assert bgp["route-distinguisher"] == "1.0.0.0:50002"
    assert bgp["total-paths"] == 3

    rt = bgp.get("route-targets", [])
    assert len(rt) == 1
    assert rt[0]["route-target"] == "123:123"
    assert rt[0]["route-target-type"] == "both"

    assert bgp["afi-safis"] == ["IPV4_UNICAST"]
