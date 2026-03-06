import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_static_routing import ShowStaticRoutingConfig


SAMPLES_DIR = Path(
    os.environ.get("ARCOS_PARSER_SAMPLES_DIR")
    or (Path(__file__).parent / "test_samples")
)

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS golden samples directory not available",
)


def test_show_static_routing_basic():
    """Validate parsing of basic static route with single next-hop."""

    sample_file = SAMPLES_DIR / "static_basic.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    assert isinstance(result, dict)
    assert "network-instances" in result
    assert "default" in result["network-instances"]
    
    protocols = result["network-instances"]["default"]["protocols"]
    assert "static-routes" in protocols
    
    protocol = protocols["static-routes"]
    assert protocol["identifier"] == "openconfig-policy-types:STATIC"
    assert protocol["name"] == "static-routes"
    
    routes = protocol["static-routes"]
    assert "192.168.100.0/24" in routes
    
    route = routes["192.168.100.0/24"]
    assert route["prefix"] == "192.168.100.0/24"
    assert route["description"] == "Basic static route test"
    
    next_hops = route["next-hops"]
    assert "1" in next_hops
    nh = next_hops["1"]
    assert nh["index"] == "1"
    assert nh["next-hop"] == "10.9.201.1"
    assert nh["interface"] == "swp1"


def test_show_static_routing_ecmp():
    """Validate parsing of static route with multiple next-hops (ECMP)."""

    sample_file = SAMPLES_DIR / "static_ecmp.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    route = routes["192.168.200.0/24"]
    
    assert route["prefix"] == "192.168.200.0/24"
    assert route["description"] == "ECMP static route"
    assert route["preference"] == 10
    
    next_hops = route["next-hops"]
    assert len(next_hops) == 3
    assert "nh1" in next_hops
    assert "nh2" in next_hops
    assert "nh3" in next_hops
    
    assert next_hops["nh1"]["next-hop"] == "10.9.201.1"
    assert next_hops["nh1"]["interface"] == "swp1"
    assert next_hops["nh2"]["next-hop"] == "10.9.202.1"
    assert next_hops["nh2"]["interface"] == "swp2"
    assert next_hops["nh3"]["next-hop"] == "10.9.203.1"
    assert next_hops["nh3"]["interface"] == "swp3"


def test_show_static_routing_drop():
    """Validate parsing of static route with DROP next-hop."""

    sample_file = SAMPLES_DIR / "static_drop.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "192.168.250.0/24" in routes
    route = routes["192.168.250.0/24"]
    assert route["description"] == "Static route with DROP"
    
    next_hops = route["next-hops"]
    assert "1" in next_hops
    nh = next_hops["1"]
    assert nh["next-hop"] == "openconfig-local-routing:DROP"
    assert "interface" not in nh


def test_show_static_routing_ipv6():
    """Validate parsing of IPv6 static route."""

    sample_file = SAMPLES_DIR / "static_ipv6.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "2001:db8:100::/64" in routes
    route = routes["2001:db8:100::/64"]
    assert route["prefix"] == "2001:db8:100::/64"
    assert route["description"] == "IPv6 static route"
    
    next_hops = route["next-hops"]
    assert "1" in next_hops
    nh = next_hops["1"]
    assert nh["next-hop"] == "2001:db8:1::1"
    assert nh["interface"] == "swp1"


def test_show_static_routing_mpls():
    """Validate parsing of static route with MPLS labels."""

    sample_file = SAMPLES_DIR / "static_mpls.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "192.168.250.1/32" in routes
    route = routes["192.168.250.1/32"]
    assert route["description"] == "Route with MPLS labels"
    assert route["local-label-index"] == 100
    
    next_hops = route["next-hops"]
    assert "NH" in next_hops
    nh = next_hops["NH"]
    assert nh["next-hop"] == "10.9.250.1"
    assert nh["interface"] == "swp3"
    assert nh["remote-label-stack"] == [1000, 2000, 3000]


def test_show_static_routing_bfd():
    """Validate parsing of static route with BFD configuration."""

    sample_file = SAMPLES_DIR / "static_bfd.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "192.168.100.1/32" in routes
    route = routes["192.168.100.1/32"]
    assert route["description"] == "Static route with BFD"
    
    assert "bfd" in route
    assert route["bfd"]["profile"] == "GLOBAL"
    
    next_hops = route["next-hops"]
    assert "next-hop1" in next_hops
    nh = next_hops["next-hop1"]
    assert nh["interface"] == "swp3"
    assert "bfd" in nh
    assert nh["bfd"]["destination-address"] == "10.0.0.2"


def test_show_static_routing_vrf_leaking():
    """Validate parsing of static route with next-network-instance (VRF leaking)."""

    sample_file = SAMPLES_DIR / "static_vrf_leaking.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "11.1.1.1/32" in routes
    route = routes["11.1.1.1/32"]
    
    next_hops = route["next-hops"]
    assert "1" in next_hops
    nh = next_hops["1"]
    assert nh["next-network-instance"] == "vrfA"


def test_show_static_routing_linklocal_ipv6():
    """Validate parsing of link-local IPv6 next-hop with subinterface."""

    sample_file = SAMPLES_DIR / "static_linklocal_ipv6.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "192:168:100::/64" in routes
    route = routes["192:168:100::/64"]
    
    next_hops = route["next-hops"]
    assert "next-hop1" in next_hops
    nh = next_hops["next-hop1"]
    assert nh["next-hop"] == "fe80::5054:ff:fef7:8d0e"
    assert nh["interface"] == "swp3"
    assert nh["subinterface"] == 0


def test_show_static_routing_multiple_vrfs():
    """Validate parsing of static routes in multiple VRFs."""

    sample_file = SAMPLES_DIR / "static_multiple_vrfs.txt"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)

    routes = result["network-instances"]["default"]["protocols"]["static-routes"]["static-routes"]
    
    assert "10.0.0.0/8" in routes
    route = routes["10.0.0.0/8"]
    
    next_hops = route["next-hops"]
    assert "1" in next_hops
    nh = next_hops["1"]
    assert nh["next-hop"] == "192.168.1.1"


def test_show_static_routing_empty():
    """Validate parser with empty JSON output."""

    output = '{"data": {}}'
    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)
    
    assert result == {"network-instances": {}}


def test_show_static_routing_invalid_json():
    """Validate parser with invalid JSON output."""

    output = "invalid json"
    parser = ShowStaticRoutingConfig(device="dummy")
    result = parser.cli(network_instance="default", protocol_instance="static-routes", output=output)
    
    assert result == {"network-instances": {}}
