"""Unit tests for ArcOS BGP neighbor parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_bgp import ShowBgpNeighbor

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def _parse_sample():
    """Helper: parse the bgp_neighbor.json sample and return result."""
    sample_file = SAMPLES_DIR / "bgp_neighbor.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")
    output = sample_file.read_text()
    parser = ShowBgpNeighbor(device="dummy")
    return parser.cli(output=output)


def test_bgp_neighbor_count():
    """Validate that all 3 neighbors are parsed."""
    result = _parse_sample()

    assert "neighbors" in result
    neighbors = result["neighbors"]
    assert len(neighbors) == 3
    expected_addrs = {"3.0.0.0", "4.0.0.0", "181.1.1.2"}
    assert set(neighbors.keys()) == expected_addrs


def test_bgp_neighbor_shutdown():
    """Validate 3.0.0.0 is SHUTDOWN with shutdown=True."""
    result = _parse_sample()

    nbr = result["neighbors"]["3.0.0.0"]
    assert nbr["session-state"] == "SHUTDOWN"
    assert nbr["shutdown"] is True
    assert nbr["shutdown-reason"] == "admin"
    assert nbr["peer-type"] == "INTERNAL"
    assert nbr["enabled"] is False
    assert nbr["peer-as"] == 65000
    assert nbr["local-as"] == 65000


def test_bgp_neighbor_established():
    """Validate 4.0.0.0 is ESTABLISHED with peer-group and transport."""
    result = _parse_sample()

    nbr = result["neighbors"]["4.0.0.0"]
    assert nbr["session-state"] == "ESTABLISHED"
    assert nbr["peer-group"] == "IBGP-PEERS"
    assert nbr["peer-type"] == "INTERNAL"
    assert nbr["enabled"] is True
    assert nbr["description"] == "spine-4"
    assert nbr["remote-router-id"] == "4.0.0.0"
    assert nbr["established-transitions"] == "1"
    assert nbr["session-elapsed-time"] == "2d 05:30:12"

    # Transport
    transport = nbr["transport"]
    assert transport["local-address"] == "1.0.0.0"
    assert transport["local-port"] == 179
    assert transport["remote-address"] == "4.0.0.0"
    assert transport["remote-port"] == 43250


def test_bgp_neighbor_external():
    """Validate 181.1.1.2 is EXTERNAL with peer-as=10000."""
    result = _parse_sample()

    nbr = result["neighbors"]["181.1.1.2"]
    assert nbr["session-state"] == "ESTABLISHED"
    assert nbr["peer-type"] == "EXTERNAL"
    assert nbr["peer-as"] == 10000
    assert nbr["local-as"] == 65000
    assert nbr["peer-group"] == "EBGP-PEERS"
    assert nbr["last-reset-reason"] == "Hold timer expired"

    # Transport
    transport = nbr["transport"]
    assert transport["local-address"] == "181.1.1.1"
    assert transport["remote-port"] == 179


def test_bgp_neighbor_messages():
    """Verify sent/received message counts for 4.0.0.0."""
    result = _parse_sample()

    nbr = result["neighbors"]["4.0.0.0"]

    sent = nbr["messages-sent"]
    assert sent["UPDATE"] == "120"
    assert sent["NOTIFICATION"] == "0"
    assert sent["KEEPALIVE"] == "5400"
    assert sent["total"] == "5520"

    received = nbr["messages-received"]
    assert received["UPDATE"] == "85"
    assert received["NOTIFICATION"] == "0"
    assert received["KEEPALIVE"] == "5400"
    assert received["total"] == "5485"


def test_bgp_neighbor_afi_safis():
    """Verify AFI list for 3.0.0.0 (has afi-safis)."""
    result = _parse_sample()

    nbr = result["neighbors"]["3.0.0.0"]
    assert "afi-safis" in nbr
    afi_list = nbr["afi-safis"]
    assert len(afi_list) == 2
    assert "IPV4_UNICAST" in afi_list
    assert "L2VPN_EVPN" in afi_list

    # Neighbors without afi-safis should not have the key
    assert "afi-safis" not in result["neighbors"]["4.0.0.0"]
    assert "afi-safis" not in result["neighbors"]["181.1.1.2"]


# ---------------------------------------------------------------------------
# ShowBgpRibRoute tests
# ---------------------------------------------------------------------------

from genie.libs.parser.arcos.show_bgp import ShowBgpRibRoute


def _parse_rib_sample():
    """Helper: parse the bgp_rib_route.json sample and return result."""
    sample_file = SAMPLES_DIR / "bgp_rib_route.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")
    output = sample_file.read_text()
    parser = ShowBgpRibRoute(device="dummy")
    return parser.cli(output=output)


def test_bgp_rib_route_prefix():
    """Validate that exactly 1 prefix is parsed."""
    result = _parse_rib_sample()

    assert "routes" in result
    routes = result["routes"]
    assert len(routes) == 1
    assert "121.121.121.121/32" in routes


def test_bgp_rib_route_path_count():
    """Validate 3 paths for the single prefix."""
    result = _parse_rib_sample()

    prefix_data = result["routes"]["121.121.121.121/32"]
    assert "paths" in prefix_data
    assert len(prefix_data["paths"]) == 3


def test_bgp_rib_route_best_path():
    """Path with origin 5.0.0.0, path-id 527 is valid with BEST_PATH."""
    result = _parse_rib_sample()

    paths = result["routes"]["121.121.121.121/32"]["paths"]
    best = [p for p in paths if p["origin"] == "5.0.0.0" and p["path-id"] == "527"]
    assert len(best) == 1

    bp = best[0]
    assert bp["valid-route"] is True
    assert bp["path-types"] == ["BEST_PATH"]
    assert bp["stale-route"] is False
    assert "invalid-reason" not in bp


def test_bgp_rib_route_invalid():
    """Path with origin 4.0.0.0, path-id 23 is invalid with NEXT_HOP_UNREACHABLE."""
    result = _parse_rib_sample()

    paths = result["routes"]["121.121.121.121/32"]["paths"]
    invalid = [p for p in paths if p["origin"] == "4.0.0.0" and p["path-id"] == "23"]
    assert len(invalid) == 1

    ip = invalid[0]
    assert ip["valid-route"] is False
    assert ip["invalid-reason"] == "NEXT_HOP_UNREACHABLE"
    assert ip["stale-route"] is False
    assert ip["next-hop"] == "91.1.1.1"


def test_bgp_rib_route_attributes():
    """Verify attributes for the best path (origin 5.0.0.0, path-id 527)."""
    result = _parse_rib_sample()

    paths = result["routes"]["121.121.121.121/32"]["paths"]
    best = [p for p in paths if p["origin"] == "5.0.0.0" and p["path-id"] == "527"][0]

    assert best["as-path-string"] == "123456"
    assert best["origin-attr"] == "IGP"
    assert best["local-pref"] == 100
    assert best["originator-id"] == "121.121.121.121"
    assert best["cluster-list"] == ["5.0.0.0", "3.0.0.0", "4.0.0.0"]
    assert best["weight"] == 0
    assert best["next-hop"] == "4.0.0.0"


# ---- BGP Global State tests ----


def _parse_global_state_sample():
    """Helper to parse the BGP global state sample."""
    from genie.libs.parser.arcos.show_bgp import ShowBgpGlobalState

    sample_file = SAMPLES_DIR / "bgp_global_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowBgpGlobalState(device="dummy")
    return parser.cli(output=output)


def test_bgp_global_state_basic():
    """Validate core BGP global state fields."""
    result = _parse_global_state_sample()

    assert result["as"] == 65002
    assert result["router-id"] == "1.0.0.0"
    assert result["total-paths"] == 3001342
    assert result["total-prefixes"] == 3000643


def test_bgp_global_state_neighbors():
    """Validate neighbor counts."""
    result = _parse_global_state_sample()

    assert result["total-configured-neighbors"] == 7
    assert result["total-established-neighbors"] == 6
    assert result["established-configured-neighbors"] == 6
    assert result["shutdown-configured-neighbors"] == 1


def test_bgp_global_state_augmented():
    """Validate augmented fields."""
    result = _parse_global_state_sample()

    assert result["route-distinguisher"] == "1.0.0.0:50001"
    assert result["network-instances-present"] == 109
    assert result["cluster-id"] == "0.0.0.0"
    assert result["segment-routing-enabled"] is False
    assert result["shutdown-protocol"] is False


# ---------------------------------------------------------------------------
# ShowBgpGlobalAfiSafi tests
# ---------------------------------------------------------------------------

from genie.libs.parser.arcos.show_bgp import ShowBgpGlobalAfiSafi


def _parse_afi_safi_sample():
    """Helper: parse the bgp_global_afi_safi.json sample and return result."""
    sample_file = SAMPLES_DIR / "bgp_global_afi_safi.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")
    output = sample_file.read_text()
    parser = ShowBgpGlobalAfiSafi(device="dummy")
    return parser.cli(output=output)


def test_bgp_afi_safi_count():
    """Validate that exactly 2 AFI-SAFIs are parsed."""
    result = _parse_afi_safi_sample()

    assert "afi-safis" in result
    afi_safis = result["afi-safis"]
    assert len(afi_safis) == 2
    assert set(afi_safis.keys()) == {"IPV4_UNICAST", "L2VPN_EVPN"}


def test_bgp_afi_safi_ipv4():
    """Validate IPV4_UNICAST has 3000006 paths, 3000004 prefixes, enabled."""
    result = _parse_afi_safi_sample()

    ipv4 = result["afi-safis"]["IPV4_UNICAST"]
    assert ipv4["enabled"] is True
    assert ipv4["total-paths"] == 3000006
    assert ipv4["total-prefixes"] == 3000004
    assert ipv4["paths-received"] == 3000006
    assert ipv4["paths-sent"] == 0
    assert ipv4["total-paths-received"] == 6000012
    assert ipv4["total-paths-sent"] == 0
    assert ipv4["total-paths-withdrawn"] == 0
    assert ipv4["rib-install-prefixes"] == 3000004
    assert ipv4["total-next-hops"] == 2


def test_bgp_afi_safi_evpn():
    """Validate L2VPN_EVPN has 301 paths, 267 prefixes."""
    result = _parse_afi_safi_sample()

    evpn = result["afi-safis"]["L2VPN_EVPN"]
    assert evpn["enabled"] is True
    assert evpn["total-paths"] == 301
    assert evpn["total-prefixes"] == 267
    assert evpn["paths-received"] == 301
    assert evpn["paths-sent"] == 200
    assert evpn["total-paths-received"] == 602
    assert evpn["total-paths-sent"] == 400
    assert evpn["rib-install-prefixes"] == 267
    assert evpn["total-next-hops"] == 3
