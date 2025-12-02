import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_isis import (
    ShowIsisAdjacency,
    ShowIsisConfig,
    ShowIsisFlexAlgoFastReroute,
    ShowIsisFlexAlgoRoute,
    ShowIsisFastReroute,
    ShowIsisInterface,
    ShowIsisLsp,
    ShowIsisMplsLabelDb,
    ShowIsisRedistributeRoute,
    ShowIsisRoute,
)


# Default location of ArcOS golden samples: local relative test_samples directory.
# Can be overridden by setting ARCOS_PARSER_SAMPLES_DIR to an alternate path.
SAMPLES_DIR = Path(
    os.environ.get("ARCOS_PARSER_SAMPLES_DIR")
    or (Path(__file__).parent / "test_samples")
)

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS golden samples directory not available",
)


def test_show_isis_adjacency_sample():
    """Validate parsing of a basic ISIS adjacency sample."""

    sample_file = SAMPLES_DIR / "isis_adjacency.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisAdjacency(device="dummy")
    result = parser.cli(adj_router=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    neighbors = isis.get("neighbors", {})
    assert "rtr1" in neighbors

    adj = neighbors["rtr1"]
    assert adj["interface"] == "swp1"
    assert adj["state"] == "UP"
    assert adj["neighbor-ipv4-address"] == "10.20.0.10"
    assert adj["neighbor-circuit-type"] == "LEVEL_2"
    assert adj["adjacency-type"] == "LEVEL_2"
    assert adj.get("usable") is True


def test_show_isis_config_sample():
    """Validate parsing of an ISIS configuration sample."""

    sample_file = SAMPLES_DIR / "isis_config.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisConfig(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    cfg = isis.get("config", {})

    # Global settings
    glb = cfg.get("global", {})
    assert glb.get("net") == ["49.0001.1111.1111.1111.00"]
    assert glb.get("level_capability") == "LEVEL_2"
    # Advanced global knobs
    assert glb.get("max_ecmp_paths") == 16
    assert glb.get("graceful_restart_enabled") is True
    assert glb.get("lsp_mtu_size") == 8000
    assert glb.get("segment_routing_enabled") is False

    # SRv6
    srv6 = glb.get("srv6", {})
    assert srv6.get("enabled") is True
    assert srv6.get("locators") == [
        "base_slice0",
        "base_slice131",
        "base_slice132",
    ]

    # Traffic engineering
    te = glb.get("traffic_engineering", {})
    assert te.get("ipv6_router_id") == "2400:2020:0:905::1"

    # Micro-loop avoidance
    mla = glb.get("micro_loop_avoidance", {})
    assert mla.get("srv6_enabled") is True
    assert mla.get("rib_update_delay") == 60000

    # Flexible algorithms
    flex_algos = glb.get("flexible_algorithms", {})
    assert "131" in flex_algos and "132" in flex_algos
    algo_131 = flex_algos["131"]
    assert algo_131["id"] == 131
    assert algo_131.get("advertise_definition_enabled") is True
    assert algo_131.get("metric_type") == "arcos-openconfig-isis-augments:LINK_DELAY"

    algo_132 = flex_algos["132"]
    assert algo_132["id"] == 132
    assert algo_132.get("advertise_definition_enabled") is True
    assert algo_132.get("metric_type") == "arcos-openconfig-isis-augments:IGP_METRIC"

    # Dynamic delay measurement
    ddm = glb.get("dynamic_delay_measurement", {})
    assert ddm.get("probe_interval") == 20
    assert ddm.get("advertisement_interval") == 60

    # LSP-bit settings
    lsp = glb.get("lsp_bit", {})
    ov = lsp.get("overload_bit", {})
    assert ov.get("set_bit_on_boot") is True
    assert ov.get("advertise_high_metric") is True

    resets = ov.get("reset_triggers")
    assert isinstance(resets, list) and len(resets) == 1
    r0 = resets[0]
    assert r0.get("reset_trigger") == "arcos-isis-types:WAIT_DELAY"
    assert r0.get("delay") == 500

    att = lsp.get("attached_bit", {})
    assert att.get("ignore_bit") is True
    assert att.get("suppress_bit") is True

    # Global levels
    levels = cfg.get("levels", {})
    assert "2" in levels
    lvl2 = levels["2"]
    assert lvl2["level_number"] == 2
    assert lvl2.get("enabled") is True

    # Per-level authentication (level 2)
    lvl2_auth = lvl2.get("authentication", {})
    assert lvl2_auth.get("lsp_authentication") is False
    assert (
        lvl2_auth.get("auth_password")
        == "$8$P116vHF0+EDlx1jNJecNY+oosPeqDFOS82XLteuqzMI="
    )
    assert (
        lvl2_auth.get("crypto_algorithm")
        == "arcos-openconfig-isis-augments:MD5"
    )

    # AFI/SAFI
    afs = cfg.get("afi_safi", {})
    assert "IPV6-UNICAST" in afs and "IPV4-UNICAST" in afs
    v6 = afs["IPV6-UNICAST"]
    assert v6["afi_name"] == "IPV6"
    assert v6["safi_name"] == "UNICAST"
    assert v6["enabled"] is True
    assert v6.get("multi_topology_enabled") is True

    v4 = afs["IPV4-UNICAST"]
    assert v4["afi_name"] == "IPV4"
    assert v4["safi_name"] == "UNICAST"
    assert v4["enabled"] is True

    # IPv6 AF summary-prefixes and prefix-unreachable
    summaries = v6.get("summary_prefixes", {})
    assert "2400:2020:0:100::/56" in summaries
    assert "2400:2020:0:900::/56" in summaries

    sum1 = summaries["2400:2020:0:100::/56"]
    assert sum1["prefix"] == "2400:2020:0:100::/56"
    assert sum1.get("level") == "LEVEL_2"
    assert sum1.get("algorithm") == 0
    assert sum1.get("adv_unreachable") is True

    sum2 = summaries["2400:2020:0:900::/56"]
    assert sum2["prefix"] == "2400:2020:0:900::/56"
    assert sum2.get("level") == "LEVEL_1"
    assert sum2.get("algorithm") == 0
    assert sum2.get("tag") == 100

    pref_unreach = v6.get("prefix_unreachable", {})
    assert pref_unreach.get("adv_lifetime") == 65535
    assert pref_unreach.get("adv_metric") == 4294967294
    assert pref_unreach.get("adv_maximum") == 65535
    assert pref_unreach.get("rx_process") is True

    # Interfaces
    interfaces = cfg.get("interfaces", {})
    assert "swp1" in interfaces and "loopback0" in interfaces

    swp1 = interfaces["swp1"]
    assert swp1["interface_id"] == "swp1"
    assert swp1["enabled"] is True
    assert swp1.get("network_type") == "POINT_TO_POINT"

    # swp1 authentication
    swp1_auth = swp1.get("authentication", {})
    assert swp1_auth.get("hello_authentication") is True
    assert swp1_auth.get("auth_password") == (
        "$8$ob8IZ1eMMUhk0tZVHJ933X4+F7xnbfJdC4jAQch+oBs="
    )
    assert (
        swp1_auth.get("crypto_algorithm")
        == "arcos-openconfig-isis-augments:MD5"
    )

    # swp1 timers
    swp1_timers = swp1.get("timers", {})
    assert swp1_timers.get("hello_interval") == 15
    assert swp1_timers.get("hello_multiplier") == 5

    swp1_afs = swp1.get("afi_safi", {})
    assert "IPV6-UNICAST" in swp1_afs and "IPV4-UNICAST" in swp1_afs

    # swp1 per-AF fast-reroute
    swp1_v6_af = swp1_afs["IPV6-UNICAST"]
    fr = swp1_v6_af.get("fast_reroute", {})
    assert fr.get("ti_lfa_srv6_enabled") is True

    swp1_lvls = swp1.get("levels", {})
    # Level 1 metric only
    assert "1" in swp1_lvls
    lvl1 = swp1_lvls["1"]
    assert lvl1["level_number"] == 1
    assert lvl1.get("metric") == 100

    # Level 2 enabled + metric + flexible-algorithm TE/delay metrics
    assert "2" in swp1_lvls
    lvl2_intf = swp1_lvls["2"]
    assert lvl2_intf["level_number"] == 2
    assert lvl2_intf.get("enabled") is True
    assert lvl2_intf.get("metric") == 200
    flex_lvl2 = lvl2_intf.get("flexible_algorithm", {})
    assert flex_lvl2.get("delay_metric") == 1000000
    assert flex_lvl2.get("te_metric") == 1000000

    # swp1 interface-ref
    swp1_ref = swp1.get("interface_ref", {})
    assert swp1_ref.get("interface") == "swp1"
    assert swp1_ref.get("subinterface") == 0

    # Other interfaces: swp3
    swp3 = interfaces["swp3"]
    assert swp3["interface_id"] == "swp3"
    assert swp3["enabled"] is True
    swp3_ref = swp3.get("interface_ref", {})
    assert swp3_ref.get("interface") == "swp3"
    assert swp3_ref.get("subinterface") == 0
    swp3_afs = swp3.get("afi_safi", {})
    swp3_v6_af = swp3_afs["IPV6-UNICAST"]
    fr3 = swp3_v6_af.get("fast_reroute", {})
    assert fr3.get("ti_lfa_srv6_enabled") is True

    # swp4
    swp4 = interfaces["swp4"]
    assert swp4["interface_id"] == "swp4"
    assert swp4["enabled"] is True
    swp4_ref = swp4.get("interface_ref", {})
    assert swp4_ref.get("interface") == "swp4"
    assert swp4_ref.get("subinterface") == 0
    swp4_afs = swp4.get("afi_safi", {})
    swp4_v6_af = swp4_afs["IPV6-UNICAST"]
    fr4 = swp4_v6_af.get("fast_reroute", {})
    assert fr4.get("ti_lfa_srv6_enabled") is True

    # loopback0
    loop0 = interfaces["loopback0"]
    assert loop0["interface_id"] == "loopback0"
    assert loop0["enabled"] is True
    assert loop0.get("tag") == [1]
    loop0_ref = loop0.get("interface_ref", {})
    assert loop0_ref.get("interface") == "loopback0"
    assert loop0_ref.get("subinterface") == 0
    loop0_afs = loop0.get("afi_safi", {})
    assert "IPV6-UNICAST" in loop0_afs and "IPV4-UNICAST" in loop0_afs
    loop0_lvls = loop0.get("levels", {})
    assert "2" in loop0_lvls
    assert loop0_lvls["2"]["level_number"] == 2
    assert loop0_lvls["2"].get("enabled") is True

    # loopback1
    loop1 = interfaces["loopback1"]
    assert loop1["interface_id"] == "loopback1"
    assert loop1["enabled"] is True
    loop1_ref = loop1.get("interface_ref", {})
    assert loop1_ref.get("interface") == "loopback1"
    assert loop1_ref.get("subinterface") == 0
    loop1_afs = loop1.get("afi_safi", {})
    assert "IPV6-UNICAST" in loop1_afs
    loop1_lvls = loop1.get("levels", {})
    assert "2" in loop1_lvls
    assert loop1_lvls["2"]["level_number"] == 2
    assert loop1_lvls["2"].get("enabled") is True


def test_show_isis_lsp_sample():
    """Validate parsing of an ISIS LSP database sample."""

    sample_file = SAMPLES_DIR / "isis_lsp.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(lsp_id=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    database = isis.get("database", {})
    assert "rtr1.00-00" in database
    assert "rtr2.00-00" in database

    lsp = database["rtr1.00-00"]
    assert lsp["lsp-id"] == "rtr1.00-00"
    assert lsp["sequence"] == 151
    assert lsp["checksum"] == 12778

    # TLV-derived information
    tlvs = lsp.get("tlvs", {})
    # For LSP rtr1.00-00 the hostname in the sample is 'rtr1'
    assert tlvs.get("hostname") == "rtr1"

    # Extended IPv4 reachability for 1.1.1.1/32 on rtr1.00-00
    ext4 = lsp.get("extended_ipv4_reachability", {})
    assert "1.1.1.1/32" in ext4
    pfx4 = ext4["1.1.1.1/32"]
    assert pfx4["ip_prefix"] == "1.1.1.1"
    assert pfx4["prefix_len"] == 32
    assert pfx4["metric"] == 10

    # MT IPv6 reachability for 2400:2020:0:1191::91/128 on rtr1.00-00
    mt6 = lsp.get("mt_ipv6_reachability", {})
    assert "2400:2020:0:1191::91/128" in mt6
    pfx6 = mt6["2400:2020:0:1191::91/128"]
    assert pfx6["ip_prefix"] == "2400:2020:0:1191::91"
    assert pfx6["prefix_len"] == 128
    assert pfx6["metric"] == 10
    assert pfx6["mt-id"] == 2

    # Also verify that LSP rtr2.00-00 contains prefix 2.2.2.2/32 in its
    # extended IPv4 reachability, and MT IPv6 2400:2020:0:2291::91/128,
    # as per the golden sample.
    lsp2 = database["rtr2.00-00"]
    ext4_lsp2 = lsp2.get("extended_ipv4_reachability", {})
    assert "2.2.2.2/32" in ext4_lsp2
    pfx4_lsp2 = ext4_lsp2["2.2.2.2/32"]
    assert pfx4_lsp2["ip_prefix"] == "2.2.2.2"
    assert pfx4_lsp2["prefix_len"] == 32
    assert pfx4_lsp2["metric"] == 10

    mt6_lsp2 = lsp2.get("mt_ipv6_reachability", {})
    assert "2400:2020:0:2291::91/128" in mt6_lsp2
    pfx6_lsp2 = mt6_lsp2["2400:2020:0:2291::91/128"]
    assert pfx6_lsp2["ip_prefix"] == "2400:2020:0:2291::91"
    assert pfx6_lsp2["prefix_len"] == 128
    assert pfx6_lsp2["metric"] == 10
    assert pfx6_lsp2["mt-id"] == 2


def test_show_isis_interface_sample():
    """Validate parsing of an ISIS interface sample."""

    sample_file = SAMPLES_DIR / "isis_interface.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisInterface(device="dummy")
    result = parser.cli(interface=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    interfaces = isis.get("interfaces", {})
    assert "swp1" in interfaces and "loopback0" in interfaces

    swp1 = interfaces["swp1"]
    assert swp1["interface-id"] == "swp1"
    assert swp1["enabled"] is True
    assert swp1.get("network-type") == "POINT_TO_POINT"

    levels = swp1.get("levels", {})
    assert "2" in levels
    level2 = levels["2"]
    assert level2.get("enabled") is True

    adjacencies = swp1.get("adjacencies", {})
    assert "rtr1" in adjacencies
    adj = adjacencies["rtr1"]
    assert adj["neighbor-ipv4-address"] == "10.20.0.10"
    assert adj["adjacency-state"] == "UP"
    assert adj.get("usable") is True


def test_show_isis_route_sample():
    """Validate parsing of an ISIS route sample."""

    sample_file = SAMPLES_DIR / "isis_route.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisRoute(device="dummy")
    result = parser.cli(prefix=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    routes_afs = isis.get("routes", {})
    assert "IPV4-UNICAST" in routes_afs and "IPV6-UNICAST" in routes_afs

    v4 = routes_afs["IPV4-UNICAST"]
    assert v4["afi_name"] == "IPV4"
    assert v4["safi_name"] == "UNICAST"

    v4_routes = v4["routes"]
    assert "1.1.1.1/32" in v4_routes and "2.2.2.2/32" in v4_routes

    r1 = v4_routes["1.1.1.1/32"]
    assert r1["prefix"] == "1.1.1.1/32"
    assert r1["best_level_number"] == 2
    lvl2_r1 = r1["levels"]["2"]
    assert lvl2_r1["metric"] == 10
    assert "connected" in lvl2_r1["flags"] and "best" in lvl2_r1["flags"]

    r2 = v4_routes["2.2.2.2/32"]
    lvl2_r2 = r2["levels"]["2"]
    assert lvl2_r2["metric"] == 20
    assert "remote" in lvl2_r2["flags"] and "best" in lvl2_r2["flags"]
    assert lvl2_r2["next_hop_id"] == "2147483649"

    v6 = routes_afs["IPV6-UNICAST"]
    assert v6["afi_name"] == "IPV6"
    assert v6["safi_name"] == "UNICAST"

    v6_routes = v6["routes"]
    assert "1:1:1::1/128" in v6_routes and "2:2:2::2/128" in v6_routes

    r6_1 = v6_routes["1:1:1::1/128"]
    lvl2_r6_1 = r6_1["levels"]["2"]
    assert lvl2_r6_1["metric"] == 10
    assert "connected" in lvl2_r6_1["flags"] and "best" in lvl2_r6_1["flags"]

    r6_2 = v6_routes["2:2:2::2/128"]
    lvl2_r6_2 = r6_2["levels"]["2"]
    assert lvl2_r6_2["metric"] == 20
    assert "remote" in lvl2_r6_2["flags"] and "best" in lvl2_r6_2["flags"]


def test_show_isis_redistribute_route_sample():
    """Validate parsing of an ISIS redistribute-route sample."""

    sample_file = SAMPLES_DIR / "isis_redistribute_route.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisRedistributeRoute(device="dummy")
    result = parser.cli(prefix=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    redist_afs = isis.get("redistribute_routes", {})
    assert "IPV6-UNICAST" in redist_afs and "IPV4-UNICAST" in redist_afs

    v6 = redist_afs["IPV6-UNICAST"]
    routes_v6 = v6["routes"]
    assert "1:1:1::1/128" in routes_v6 and "10:20::/120" in routes_v6

    r6_1 = routes_v6["1:1:1::1/128"]
    lvl2_r6_1 = r6_1["levels"]["2"]
    assert lvl2_r6_1["metric"] == 10
    assert lvl2_r6_1["route_tag"] == 0
    assert "connected" in lvl2_r6_1["flags"]
    assert lvl2_r6_1["source_identifier"] == "ISIS"
    assert lvl2_r6_1["source_name"] == "default@default"

    v4 = redist_afs["IPV4-UNICAST"]
    routes_v4 = v4["routes"]
    assert "1.1.1.1/32" in routes_v4 and "10.20.0.0/24" in routes_v4

    r4_1 = routes_v4["1.1.1.1/32"]
    lvl2_r4_1 = r4_1["levels"]["2"]
    assert lvl2_r4_1["metric"] == 10
    assert lvl2_r4_1["route_tag"] == 0
    assert "connected" in lvl2_r4_1["flags"]
    assert lvl2_r4_1["source_identifier"] == "ISIS"
    assert lvl2_r4_1["source_name"] == "default@default"


def test_show_isis_fast_reroute_minimal():
    """Validate parsing of a minimal ISIS fast-reroute sample."""

    sample_file = SAMPLES_DIR / "isis_fast_reroute.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisFastReroute(device="dummy")
    result = parser.cli(prefix=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    frr = isis.get("fast_reroute", {})
    assert "IPV6-UNICAST" in frr

    af = frr["IPV6-UNICAST"]
    assert af["afi_name"] == "IPV6"
    assert af["safi_name"] == "UNICAST"

    prefixes = af["prefixes"]
    # The sample contains multiple prefixes; validate a representative one.
    assert "2::2/128" in prefixes
    pfx = prefixes["2::2/128"]
    lvl2 = pfx["levels"]["2"]
    assert lvl2["metric"] == 20
    assert lvl2["nexthop_interface"] == "swp4"
    assert lvl2["nexthop_address"] == "::"
    assert lvl2["origin_system_id"] == "rtr2.00"


def test_show_isis_flex_algo_fast_reroute_minimal():
    """Validate parsing of a minimal ISIS flex-algo fast-reroute sample."""

    sample_file = SAMPLES_DIR / "isis_flexalgo_fast_reroute.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisFlexAlgoFastReroute(device="dummy")
    result = parser.cli(prefix=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    flex = isis.get("flex_algo_fast_reroute", {})
    assert "IPV6-UNICAST" in flex

    af = flex["IPV6-UNICAST"]
    algos = af["algorithms"]
    assert "132" in algos

    algo = algos["132"]
    assert algo["id"] == 132
    prefixes = algo["prefixes"]
    assert "2400:2020:32:2291::/64" in prefixes
    pfx = prefixes["2400:2020:32:2291::/64"]
    lvl2 = pfx["levels"]["2"]
    assert lvl2["metric"] == 20
    assert lvl2["nexthop_interface"] == "swp4"
    assert lvl2["nexthop_address"] == "::"


def test_show_isis_flex_algo_route_minimal():
    """Validate parsing of a minimal ISIS flex-algo route sample."""

    sample_file = SAMPLES_DIR / "isis_flexalgo_route.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisFlexAlgoRoute(device="dummy")
    result = parser.cli(prefix=None, output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    flex = isis.get("flex_algo_routes", {})
    assert "IPV6-UNICAST" in flex

    af = flex["IPV6-UNICAST"]
    algos = af["algorithms"]
    # The sample contains algorithms 131 and 132; validate algorithm 132.
    assert "132" in algos

    algo = algos["132"]
    assert algo["id"] == 132
    routes = algo["routes"]
    assert "2400:2020:32:2291::/64" in routes
    r = routes["2400:2020:32:2291::/64"]
    assert r["best_level_number"] == 2
    lvl2 = r["levels"]["2"]
    assert lvl2["metric"] == 20
    assert "best" in lvl2["flags"]


def test_show_isis_mpls_label_db_sample():
    """Validate parsing of an ISIS MPLS label database sample."""

    sample_file = SAMPLES_DIR / "isis_mpls_label_db.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisMplsLabelDb(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})

    mpls = isis.get("mpls", {})
    assert mpls.get("igp_ldp_sync_enabled") is False

    label_db = mpls.get("label_db", {})
    state = label_db.get("state", {})
    assert state.get("protocol_identifier") == "ISIS"
    assert state.get("protocol_name") == "default"
    assert state.get("configured_blocks") == 2
    assert state.get("active_blocks") == 2
    assert state.get("active_usages") == 2

    # Statistics
    stats = label_db.get("statistics", {})
    assert stats.get("label_space") == 20000
    assert stats.get("labels") == 6
    assert stats.get("allocs") == "7"
    assert stats.get("frees") == "5"

    # Usages
    usages = label_db.get("usages", {})
    assert "ISIS_SRGB" in usages
    assert "ISIS_SRLB" in usages

    # SRGB usage
    srgb = usages["ISIS_SRGB"]
    assert srgb["usage"] == "ISIS_SRGB"
    assert srgb.get("blocks_count") == 1
    assert srgb.get("opaque_flags") == "0c"

    srgb_stats = srgb.get("statistics", {})
    assert srgb_stats.get("label_space") == 10000
    assert srgb_stats.get("labels") == 3

    # SRGB blocks
    srgb_blocks = srgb.get("blocks", {})
    assert "10000" in srgb_blocks
    block_10000 = srgb_blocks["10000"]
    assert block_10000["lower_bound"] == 10000
    assert block_10000["upper_bound"] == 19999
    assert block_10000.get("block_name") == "rb1"

    # SRGB labels
    srgb_labels = srgb.get("labels", {})
    assert "10111" in srgb_labels
    label_10111 = srgb_labels["10111"]
    assert label_10111["label"] == 10111
    assert label_10111.get("block_name") == "rb1"
    key_10111 = label_10111.get("label_key", {})
    assert key_10111.get("type") == "KEY_IPV4_PREFIX"
    assert key_10111.get("ip_prefix") == "1.1.1.1/32"

    # SRLB usage
    srlb = usages["ISIS_SRLB"]
    assert srlb["usage"] == "ISIS_SRLB"

    # SRLB labels (adjacency labels)
    srlb_labels = srlb.get("labels", {})
    assert "20012" in srlb_labels
    label_20012 = srlb_labels["20012"]
    assert label_20012["label"] == 20012
    key_20012 = label_20012.get("label_key", {})
    assert key_20012.get("type") == "KEY_IPV4_ADJ"
    assert key_20012.get("nh_address") == "10.20.0.20"
    assert key_20012.get("ifindex") == "802"


def test_show_isis_lsp_extended_is_neighbor():
    """Validate parsing of Extended IS Reachability (neighbors/links) with SR-MPLS data."""

    sample_file = SAMPLES_DIR / "isis_lsp_large.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    # Skip the first line (command prompt)
    if output.startswith("root@"):
        output = "\n".join(output.split("\n")[1:])

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    ni = result["network-instance"].get("default", {})
    assert "isis" in ni
    isis = ni["isis"].get("default", {})
    database = isis.get("database", {})

    # Check rtr1.00-00 LSP
    assert "rtr1.00-00" in database
    lsp = database["rtr1.00-00"]

    # Verify Extended IS Neighbor parsing
    ext_is = lsp.get("extended_is_neighbor", {})
    assert len(ext_is) >= 2  # At least rtr2 and rtr3 neighbors

    # Check neighbor rtr2.00 with instance 802
    nbr_key = "rtr2.00:802"
    assert nbr_key in ext_is
    nbr = ext_is[nbr_key]

    assert nbr["system_id"] == "rtr2.00"
    assert nbr["instance_id"] == "802"
    assert nbr["metric"] == 10
    assert nbr.get("two_way") is True

    # Link ID
    assert "link_id" in nbr
    assert nbr["link_id"]["local"] == 802
    assert nbr["link_id"]["remote"] == 801

    # IPv4 addresses
    assert nbr.get("ipv4_interface_address") == ["10.20.0.10"]
    assert nbr.get("ipv4_neighbor_address") == ["10.20.0.20"]

    # IPv6 address
    assert nbr.get("ipv6_interface_address") == ["10:20::10"]

    # Adjacency SID (SR-MPLS)
    adj_sids = nbr.get("adjacency_sids", [])
    assert len(adj_sids) >= 1
    adj_sid = adj_sids[0]
    assert adj_sid["sid"] == 20012
    assert "VALUE" in adj_sid.get("flags", [])
    assert "LOCAL" in adj_sid.get("flags", [])
    assert adj_sid.get("weight") == 0

    # ASLA (Application-Specific Link Attributes)
    asla = nbr.get("asla", {})
    assert asla.get("application") == "flexible-algorithm"
    assert "admin_groups" in asla
    assert "red" in asla["admin_groups"]
    assert asla.get("te_metric") == 10
    assert asla.get("min_delay") == 5
    assert asla.get("max_delay") == 5


def test_show_isis_lsp_srv6_end_x_sid():
    """Validate parsing of SRv6 End.X SID in Extended IS Reachability."""

    sample_file = SAMPLES_DIR / "isis_lsp_large_2.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    # Skip the first line (command prompt)
    if output.startswith("root@"):
        output = "\n".join(output.split("\n")[1:])

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    database = result["network-instance"]["default"]["isis"]["default"].get("database", {})

    # Check rtr1.00-00 LSP
    assert "rtr1.00-00" in database
    lsp = database["rtr1.00-00"]

    # Verify Extended IS Neighbor parsing
    ext_is = lsp.get("extended_is_neighbor", {})
    assert len(ext_is) >= 1

    # Check neighbor rtr2.00:802
    nbr_key = "rtr2.00:802"
    assert nbr_key in ext_is
    nbr = ext_is[nbr_key]

    # Adjacency SID should be present
    adj_sids = nbr.get("adjacency_sids", [])
    assert len(adj_sids) >= 1
    assert adj_sids[0]["sid"] == 20012


def test_show_isis_lsp_mt_is_neighbor():
    """Validate parsing of MT IS Neighbors (MT_ISN TLV) with SRv6 End.X SID."""

    sample_file = SAMPLES_DIR / "isis_lsp_large_2.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    # Skip the first line (command prompt)
    if output.startswith("root@"):
        output = "\n".join(output.split("\n")[1:])

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    database = result["network-instance"]["default"]["isis"]["default"].get("database", {})

    # Check rtr1.00-00 LSP
    assert "rtr1.00-00" in database
    lsp = database["rtr1.00-00"]

    # Verify MT IS Neighbor parsing
    mt_is = lsp.get("mt_is_neighbor", {})
    assert len(mt_is) >= 1

    # Check neighbor rtr2.00 with mt-id 2, instance 802
    nbr_key = "rtr2.00:mt2:802"
    assert nbr_key in mt_is
    nbr = mt_is[nbr_key]

    assert nbr["system_id"] == "rtr2.00"
    assert nbr["mt_id"] == 2
    assert nbr["instance_id"] == "802"
    assert nbr["metric"] == 10
    assert nbr.get("two_way") is True

    # Link ID
    assert "link_id" in nbr
    assert nbr["link_id"]["local"] == 802

    # IPv4/IPv6 addresses
    assert nbr.get("ipv4_interface_address") == ["10.20.0.10"]
    assert nbr.get("ipv6_interface_address") == ["10:20::10"]

    # ASLA (FlexAlgo attributes)
    asla = nbr.get("asla", {})
    assert asla.get("application") == "flexible-algorithm"
    assert "admin_groups" in asla
    assert asla.get("min_delay") == 109  # Different delay value in MT_ISN

    # SRv6 End.X SID (should be present in MT_ISN)
    end_x_sids = nbr.get("end_x_sids", [])
    assert len(end_x_sids) >= 1
    end_x = end_x_sids[0]
    assert end_x["sid"] == "2400:2020:0:1191:8004::"
    assert end_x.get("algorithm") == "SPF"
    assert end_x.get("endpoint_func") == "END_X_PSP_USD"
    assert end_x.get("weight") == 0

    # SID structure
    sid_struct = end_x.get("sid_structure", {})
    assert sid_struct.get("lb") == 40
    assert sid_struct.get("ln") == 24
    assert sid_struct.get("fun") == 16
    assert sid_struct.get("arg") == 0


def test_show_isis_lsp_prefix_sid():
    """Validate parsing of Prefix SID in Extended IPv4 Reachability."""

    sample_file = SAMPLES_DIR / "isis_lsp_large_2.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    # Skip the first line (command prompt)
    if output.startswith("root@"):
        output = "\n".join(output.split("\n")[1:])

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    database = result["network-instance"]["default"]["isis"]["default"].get("database", {})

    # Check rtr1.00-00 LSP
    assert "rtr1.00-00" in database
    lsp = database["rtr1.00-00"]

    # Verify Extended IPv4 Reachability
    ext4 = lsp.get("extended_ipv4_reachability", {})
    assert "1.1.1.1/32" in ext4

    pfx = ext4["1.1.1.1/32"]
    assert pfx["ip_prefix"] == "1.1.1.1"
    assert pfx["prefix_len"] == 32
    assert pfx["metric"] == 10

    # Prefix Tag
    assert pfx.get("tag") == [1]

    # Prefix SID (SR-MPLS)
    prefix_sids = pfx.get("prefix_sids", [])
    assert len(prefix_sids) >= 1

    psid = prefix_sids[0]
    assert psid.get("algorithm") == "SPF"
    assert psid.get("sid") == 111
    assert "NODE" in psid.get("flags", [])
    assert "NO_PHP" in psid.get("flags", [])
    assert "EXPLICIT_NULL" in psid.get("flags", [])


def test_show_isis_lsp_router_capability():
    """Validate parsing of Router Capability SubTLVs (SRGB, SRLB, FAD, Node MSD)."""

    sample_file = SAMPLES_DIR / "isis_lsp_large_2.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    # Skip the first line (command prompt)
    if output.startswith("root@"):
        output = "\n".join(output.split("\n")[1:])

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    database = result["network-instance"]["default"]["isis"]["default"].get("database", {})

    # Check rtr1.00-00 LSP
    assert "rtr1.00-00" in database
    lsp = database["rtr1.00-00"]

    # Router Capabilities
    tlvs = lsp.get("tlvs", {})
    router_cap = tlvs.get("router-capabilities", {})
    assert router_cap

    # Basic info
    assert router_cap.get("instance_number") == 1
    assert router_cap.get("router_id") == "1.1.1.1"

    # IPv6 TE Router ID
    assert router_cap.get("ipv6_te_router_id") == "1::1"

    # SR Algorithms
    sr_algos = router_cap.get("sr_algorithms", [])
    assert "SPF" in sr_algos
    assert 131 in sr_algos
    assert 132 in sr_algos

    # SR Capability (SRGB)
    sr_cap = router_cap.get("sr_capability", {})
    assert "IPV4_MPLS" in sr_cap.get("flags", [])
    assert "IPV6_MPLS" in sr_cap.get("flags", [])
    assert sr_cap.get("range") == 10000
    assert sr_cap.get("label") == 10000

    # SRLB
    srlb = router_cap.get("srlb", {})
    assert srlb.get("range") == 10000
    assert srlb.get("label") == 20000

    # Node MSD
    node_msd = router_cap.get("node_msd", {})
    assert node_msd.get("srv6_max_segments_left") == 10
    assert node_msd.get("srv6_max_end_pop") == 5
    assert node_msd.get("srv6_max_h_encaps") == 3
    assert node_msd.get("srv6_max_end_d") == 10

    # Flex-Algo Definitions
    fads = router_cap.get("flex_algo_definitions", {})
    assert "131" in fads
    assert fads["131"].get("priority") == 128
    assert fads["131"].get("metric_type") == "LINK_DELAY"
    assert "132" in fads
    assert fads["132"].get("metric_type") == "IGP_METRIC"


def test_show_isis_lsp_srv6_locator():
    """Validate parsing of SRv6 Locators with End SID and SID structure."""

    sample_file = SAMPLES_DIR / "isis_lsp_large_2.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    # Skip the first line (command prompt)
    if output.startswith("root@"):
        output = "\n".join(output.split("\n")[1:])

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    database = result["network-instance"]["default"]["isis"]["default"].get("database", {})

    # Check rtr1.00-00 LSP
    assert "rtr1.00-00" in database
    lsp = database["rtr1.00-00"]

    # SRv6 Locators
    tlvs = lsp.get("tlvs", {})
    locators = tlvs.get("srv6-locators", [])
    assert len(locators) >= 3  # SPF, algo 131, algo 132

    # Find the SPF locator
    spf_loc = next((loc for loc in locators if loc.get("algorithm") == "SPF"), None)
    assert spf_loc is not None
    assert spf_loc["locator"] == "2400:2020:0:1191::/64"
    assert spf_loc["mt_id"] == 2
    assert spf_loc["metric"] == 10

    # Verify End SID parsing
    end_sids = spf_loc.get("end_sids", [])
    assert len(end_sids) >= 1

    end_sid = end_sids[0]
    assert end_sid["sid"] == "2400:2020:0:1191:1::"
    assert end_sid.get("endpoint_func") == "END_PSP_USD"

    # Verify SID structure
    sid_struct = end_sid.get("sid_structure", {})
    assert sid_struct.get("lb") == 40
    assert sid_struct.get("ln") == 24
    assert sid_struct.get("fun") == 16
    assert sid_struct.get("arg") == 0

    # Find FlexAlgo 131 locator
    algo131_loc = next((loc for loc in locators if loc.get("algorithm") == 131), None)
    assert algo131_loc is not None
    assert algo131_loc["locator"] == "2400:2020:31:1191::/64"

    # Find FlexAlgo 132 locator
    algo132_loc = next((loc for loc in locators if loc.get("algorithm") == 132), None)
    assert algo132_loc is not None
    assert algo132_loc["locator"] == "2400:2020:32:1191::/64"
