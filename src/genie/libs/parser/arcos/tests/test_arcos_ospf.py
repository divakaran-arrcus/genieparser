"""Unit tests for ArcOS OSPF parsers."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_ospf import (
    ShowOspfGlobal,
    ShowOspfNeighbor,
    ShowOspfArea,
    ShowOspfInterface,
    ShowOspfSpfThrottle,
    ShowOspfLsdb,
    ShowOspfRunningConfig,
)
from genie.metaparser.util.exceptions import SchemaEmptyParserError

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


# =====================================================================
# ShowOspfGlobal tests
# =====================================================================

def test_show_ospf_global_basic():
    """Validate basic OSPF global state fields are parsed."""
    sample_file = SAMPLES_DIR / "ospf_global_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfGlobal(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert result["router-id"] == "2.2.2.2"
    assert result["log-adjacency-changes"] == "LOG_ADJ_ENABLE_LIMITED"
    assert result["max-ecmp-paths"] == 128
    assert result["abr-router"] is True
    assert result["asbr-router"] is False


def test_show_ospf_global_counters():
    """Validate OSPF global counter fields."""
    output = (SAMPLES_DIR / "ospf_global_state.json").read_text()
    parser = ShowOspfGlobal(device="dummy")
    result = parser.cli(output=output)

    assert result["area-count"] == 2
    assert result["neighbor-count"] == 2
    assert result["full-neighbor-count"] == 2
    assert result["up-interface-count"] == 4


def test_show_ospf_global_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfGlobal(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfArea tests
# =====================================================================

def test_show_ospf_area_basic():
    """Validate OSPF area state — 2 areas from rtr2."""
    sample_file = SAMPLES_DIR / "ospf_area_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfArea(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    areas = result["areas"]
    assert "0" in areas
    assert "1" in areas

    # Area 0 — NORMAL
    a0 = areas["0"]
    assert a0["identifier"] == 0
    assert a0["area-type"] == "AREA_TYPE_NORMAL"
    assert a0["advertise-summary-lsas"] is True
    assert a0["stub-default-cost"] == 1
    assert a0["up-interface-count"] == 2
    assert a0["full-neighbor-count"] == 1

    # Area 1 — STUB
    a1 = areas["1"]
    assert a1["identifier"] == 1
    assert a1["area-type"] == "AREA_TYPE_STUB"
    assert a1["stub-default-cost"] == 10


def test_show_ospf_area_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfArea(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfInterface tests
# =====================================================================

def test_show_ospf_interface_area0():
    """Validate OSPF interface state for area 0 — loopback0 + swp1."""
    sample_file = SAMPLES_DIR / "ospf_area0_interface_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfInterface(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    areas = result["areas"]
    assert "0" in areas

    intfs = areas["0"]["interfaces"]
    assert "loopback0" in intfs
    assert "swp1" in intfs

    # loopback0 — passive loopback
    lo0 = intfs["loopback0"]
    assert lo0["id"] == "loopback0"
    assert lo0["network-type"] == "POINT_TO_POINT_NETWORK"
    assert lo0["passive"] is True
    assert lo0["interface-state"] == "INTERFACE_LOOPBACK"
    assert lo0["local-ip-address"] == "2.2.2.2"
    assert lo0["metric"] == 10
    assert lo0["neighbor-count"] == 0

    # swp1 — active P2P interface
    swp1 = intfs["swp1"]
    assert swp1["id"] == "swp1"
    assert swp1["passive"] is False
    assert swp1["interface-up"] is True
    assert swp1["interface-state"] == "INTERFACE_POINT_TO_POINT"
    assert swp1["local-ip-address"] == "10.12.1.2"
    assert swp1["metric"] == 320
    assert swp1["full-neighbor-count"] == 1
    assert swp1["mtu"] == 8974


def test_show_ospf_interface_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfInterface(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfSpfThrottle tests
# =====================================================================

def test_show_ospf_spf_throttle_basic():
    """Validate OSPF SPF throttle timers from rtr2."""
    sample_file = SAMPLES_DIR / "ospf_spf_throttle.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfSpfThrottle(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert result["spf-initial-delay"] == 50
    assert result["spf-short-delay"] == 200
    assert result["spf-long-delay"] == 5000
    assert result["time-to-learn-interval"] == 500
    assert result["holddown-interval"] == 10000


def test_show_ospf_spf_throttle_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfSpfThrottle(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfNeighbor tests (enhanced with extra fields)
# =====================================================================

def test_show_ospf_neighbor_enhanced():
    """Validate OSPF neighbor parsing with extra state fields."""
    sample_file = SAMPLES_DIR / "ospf_area0_neighbor.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfNeighbor(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    nbrs = result["neighbors"]
    assert len(nbrs) >= 1

    # Find the neighbor on swp1
    key = "0:swp1:1.1.1.1"
    assert key in nbrs
    nbr = nbrs[key]

    assert nbr["neighbor-router-id"] == "1.1.1.1"
    assert nbr["neighbor-ip-address"] == "10.12.1.1"
    assert nbr["adjacency-state"] == "NEIGHBOR_FULL"
    assert nbr["priority"] == 1

    # Enhanced fields
    assert nbr["database-exchange-mtu"] == 8974
    assert "last-established-full-timestamp" in nbr
    assert "next-dead-timer-expiry-remaining-time" in nbr


def test_show_ospf_neighbor_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfNeighbor(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfLsdb tests
# =====================================================================

def test_show_ospf_lsdb_basic():
    """Validate OSPF LSDB parsing — router and summary LSAs."""
    sample_file = SAMPLES_DIR / "ospf_lsdb.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfLsdb(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    areas = result["areas"]
    assert "0" in areas
    assert "1" in areas

    # Area 0 LSDB
    a0_types = areas["0"]["lsa-types"]
    assert "ROUTER_LSA" in a0_types
    assert "SUMMARY_IP_NETWORK_LSA" in a0_types

    # Router LSA from rtr1 (1.1.1.1)
    router_lsas = a0_types["ROUTER_LSA"]["lsas"]
    rtr1_key = "1.1.1.1:1.1.1.1"
    assert rtr1_key in router_lsas
    rtr1_lsa = router_lsas[rtr1_key]
    assert rtr1_lsa["link-state-id"] == "1.1.1.1"
    assert rtr1_lsa["advertising-router"] == "1.1.1.1"
    assert rtr1_lsa["sequence-number"] == "80:00:00:03"
    assert rtr1_lsa["age"] == 77

    # Router LSA body
    rlsa = rtr1_lsa["router-lsa"]
    assert rlsa["num-links"] == 3
    links = rlsa["links"]
    assert len(links) == 3
    # First link — P2P to rtr2
    assert links["0"]["type"] == "ROUTER_LSA_P2P"
    assert links["0"]["link-id"] == "2.2.2.2"
    assert links["0"]["metric"] == 320

    # Router LSA from rtr2 (ABR, b-bit set)
    rtr2_key = "2.2.2.2:2.2.2.2"
    rtr2_lsa = router_lsas[rtr2_key]
    assert "B" in rtr2_lsa["router-lsa"]["flags"]

    # Summary LSA
    summary_lsas = a0_types["SUMMARY_IP_NETWORK_LSA"]["lsas"]
    assert len(summary_lsas) >= 2

    # Area 1 LSDB
    a1_types = areas["1"]["lsa-types"]
    assert "ROUTER_LSA" in a1_types


def test_show_ospf_lsdb_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfLsdb(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfRunningConfig tests
# =====================================================================

def test_show_ospf_running_config_basic():
    """Validate OSPF running config from rtr2."""
    sample_file = SAMPLES_DIR / "ospf_running_config.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfRunningConfig(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)

    # Global
    g = result["global"]
    assert g["router-id"] == "2.2.2.2"
    rp = g["route-preference"]
    assert rp["intra-area"] == 110
    assert rp["inter-area"] == 115
    assert rp["external"] == 120

    # Areas
    areas = result["areas"]
    assert "0" in areas
    assert "1" in areas

    # Area 0 — normal, 2 interfaces
    a0 = areas["0"]
    intfs = a0["interfaces"]
    assert "loopback0" in intfs
    assert "swp1" in intfs
    swp1 = intfs["swp1"]
    assert swp1["network-type"] == "POINT_TO_POINT_NETWORK"
    assert swp1["hello-interval"] == 10
    assert swp1["dead-interval"] == 40

    # Area 1 — stub
    a1 = areas["1"]
    assert a1["area-type"] == "AREA_TYPE_STUB"
    assert a1["stub-default-cost"] == 10


def test_show_ospf_running_config_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfRunningConfig(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')
