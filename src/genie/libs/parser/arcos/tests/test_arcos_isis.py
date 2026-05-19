import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_isis import (
    ShowIsisAdjacency,
    ShowIsisConfig,
    ShowIsisFlexAlgoFastReroute,
    ShowIsisFlexAlgoRoute,
    ShowIsisFastReroute,
    ShowIsisGlobalTunnel,
    ShowIsisInterface,
    ShowIsisLevelCounters,
    ShowIsisLevelState,
    ShowIsisLsp,
    ShowIsisMplsLabelDb,
    ShowIsisProtectionTracker,
    ShowIsisRedistributeRoute,
    ShowIsisRoute,
    ShowIsisSpfLog,
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

    # Parser output is hierarchical: interface → level → adjacency
    interfaces = isis.get("interface", {})
    assert "swp1" in interfaces

    adj = interfaces["swp1"]["level"][2]["adjacency"]["rtr1"]
    assert adj["state"] == "UP"
    assert adj["neighbor-ipv4-address"] == "10.20.0.10"
    assert adj["neighbor-circuit-type"] == "LEVEL_2"
    assert adj["adjacency-type"] == "LEVEL_2"
    assert adj.get("usable") is True

    # Verify new state change tracking fields
    assert adj["up-time"] == "4d 23:18:45"  # Human-readable format preferred
    assert adj["num-state-changes"] == 3
    assert adj["last-state-change-timestamp"] == "2025-12-02T22:31:07.311688+00:00"
    assert adj["last-down-reason"] == "NONE"


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
    assert glb.get("level-capability") == "LEVEL_2"
    # Advanced global knobs
    assert glb.get("max-ecmp-paths") == 16
    assert glb.get("graceful-restart-enabled") is True
    assert glb.get("lsp-mtu-size") == 8000
    assert glb.get("segment-routing-enabled") is False

    # SRv6
    srv6 = glb.get("srv6", {})
    assert srv6.get("enabled") is True
    assert srv6.get("locators") == [
        "base_slice0",
        "base_slice131",
        "base_slice132",
    ]

    # Traffic engineering
    te = glb.get("traffic-engineering", {})
    assert te.get("ipv6-router-id") == "2400:2020:0:905::1"

    # Micro-loop avoidance
    mla = glb.get("micro-loop-avoidance", {})
    assert mla.get("srv6-enabled") is True
    assert mla.get("rib-update-delay") == 60000

    # Flexible algorithms
    flex_algos = glb.get("flexible-algorithms", {})
    assert "131" in flex_algos and "132" in flex_algos
    algo_131 = flex_algos["131"]
    assert algo_131["id"] == 131
    assert algo_131.get("advertise-definition-enabled") is True
    assert algo_131.get("metric-type") == "arcos-openconfig-isis-augments:LINK_DELAY"

    algo_132 = flex_algos["132"]
    assert algo_132["id"] == 132
    assert algo_132.get("advertise-definition-enabled") is True
    assert algo_132.get("metric-type") == "arcos-openconfig-isis-augments:IGP_METRIC"

    # Dynamic delay measurement
    ddm = glb.get("dynamic-delay-measurement", {})
    assert ddm.get("probe-interval") == 20
    assert ddm.get("advertisement-interval") == 60

    # LSP-bit settings
    lsp = glb.get("lsp-bit", {})
    ov = lsp.get("overload-bit", {})
    assert ov.get("set-bit-on-boot") is True
    assert ov.get("advertise-high-metric") is True

    resets = ov.get("reset-triggers")
    assert isinstance(resets, list) and len(resets) == 1
    r0 = resets[0]
    assert r0.get("reset-trigger") == "arcos-isis-types:WAIT_DELAY"
    assert r0.get("delay") == 500

    att = lsp.get("attached-bit", {})
    assert att.get("ignore-bit") is True
    assert att.get("suppress-bit") is True

    # Global levels
    levels = cfg.get("levels", {})
    assert "2" in levels
    lvl2 = levels["2"]
    assert lvl2["level-number"] == 2
    assert lvl2.get("enabled") is True

    # Per-level authentication (level 2)
    lvl2_auth = lvl2.get("authentication", {})
    assert lvl2_auth.get("lsp-authentication") is False
    assert (
        lvl2_auth.get("auth-password")
        == "$8$P116vHF0+EDlx1jNJecNY+oosPeqDFOS82XLteuqzMI="
    )
    assert (
        lvl2_auth.get("crypto-algorithm")
        == "arcos-openconfig-isis-augments:MD5"
    )

    # AFI/SAFI
    afs = cfg.get("afi-safi", {})
    assert "IPV6-UNICAST" in afs and "IPV4-UNICAST" in afs
    v6 = afs["IPV6-UNICAST"]
    assert v6["afi-name"] == "IPV6"
    assert v6["safi-name"] == "UNICAST"
    assert v6["enabled"] is True
    assert v6.get("multi-topology-enabled") is True

    v4 = afs["IPV4-UNICAST"]
    assert v4["afi-name"] == "IPV4"
    assert v4["safi-name"] == "UNICAST"
    assert v4["enabled"] is True

    # IPv6 AF summary-prefixes and prefix-unreachable
    summaries = v6.get("summary-prefixes", {})
    assert "2400:2020:0:100::/56" in summaries
    assert "2400:2020:0:900::/56" in summaries

    sum1 = summaries["2400:2020:0:100::/56"]
    assert sum1["prefix"] == "2400:2020:0:100::/56"
    assert sum1.get("level") == "LEVEL_2"
    assert sum1.get("algorithm") == 0
    assert sum1.get("adv-unreachable") is True

    sum2 = summaries["2400:2020:0:900::/56"]
    assert sum2["prefix"] == "2400:2020:0:900::/56"
    assert sum2.get("level") == "LEVEL_1"
    assert sum2.get("algorithm") == 0
    assert sum2.get("tag") == 100

    pref_unreach = v6.get("prefix-unreachable", {})
    assert pref_unreach.get("adv-lifetime") == 65535
    assert pref_unreach.get("adv-metric") == 4294967294
    assert pref_unreach.get("adv-maximum") == 65535
    assert pref_unreach.get("rx-process") is True

    # Interfaces
    interfaces = cfg.get("interfaces", {})
    assert "swp1" in interfaces and "loopback0" in interfaces

    swp1 = interfaces["swp1"]
    assert swp1["interface-id"] == "swp1"
    assert swp1["enabled"] is True
    assert swp1.get("network-type") == "POINT_TO_POINT"

    # swp1 authentication
    swp1_auth = swp1.get("authentication", {})
    assert swp1_auth.get("hello-authentication") is True
    assert swp1_auth.get("auth-password") == (
        "$8$ob8IZ1eMMUhk0tZVHJ933X4+F7xnbfJdC4jAQch+oBs="
    )
    assert (
        swp1_auth.get("crypto-algorithm")
        == "arcos-openconfig-isis-augments:MD5"
    )

    # swp1 timers
    swp1_timers = swp1.get("timers", {})
    assert swp1_timers.get("hello-interval") == 15
    assert swp1_timers.get("hello-multiplier") == 5

    swp1_afs = swp1.get("afi-safi", {})
    assert "IPV6-UNICAST" in swp1_afs and "IPV4-UNICAST" in swp1_afs

    # swp1 per-AF fast-reroute
    swp1_v6_af = swp1_afs["IPV6-UNICAST"]
    fr = swp1_v6_af.get("fast-reroute", {})
    assert fr.get("ti-lfa-srv6-enabled") is True

    swp1_lvls = swp1.get("levels", {})
    # Level 1 metric only
    assert "1" in swp1_lvls
    lvl1 = swp1_lvls["1"]
    assert lvl1["level-number"] == 1
    assert lvl1.get("metric") == 100

    # Level 2 enabled + metric + flexible-algorithm TE/delay metrics
    assert "2" in swp1_lvls
    lvl2_intf = swp1_lvls["2"]
    assert lvl2_intf["level-number"] == 2
    assert lvl2_intf.get("enabled") is True
    assert lvl2_intf.get("metric") == 200
    flex_lvl2 = lvl2_intf.get("flexible-algorithm", {})
    assert flex_lvl2.get("delay-metric") == 1000000
    assert flex_lvl2.get("te-metric") == 1000000

    # swp1 interface-ref
    swp1_ref = swp1.get("interface-ref", {})
    assert swp1_ref.get("interface") == "swp1"
    assert swp1_ref.get("subinterface") == 0

    # Other interfaces: swp3
    swp3 = interfaces["swp3"]
    assert swp3["interface-id"] == "swp3"
    assert swp3["enabled"] is True
    swp3_ref = swp3.get("interface-ref", {})
    assert swp3_ref.get("interface") == "swp3"
    assert swp3_ref.get("subinterface") == 0
    swp3_afs = swp3.get("afi-safi", {})
    swp3_v6_af = swp3_afs["IPV6-UNICAST"]
    fr3 = swp3_v6_af.get("fast-reroute", {})
    assert fr3.get("ti-lfa-srv6-enabled") is True

    # swp4
    swp4 = interfaces["swp4"]
    assert swp4["interface-id"] == "swp4"
    assert swp4["enabled"] is True
    swp4_ref = swp4.get("interface-ref", {})
    assert swp4_ref.get("interface") == "swp4"
    assert swp4_ref.get("subinterface") == 0
    swp4_afs = swp4.get("afi-safi", {})
    swp4_v6_af = swp4_afs["IPV6-UNICAST"]
    fr4 = swp4_v6_af.get("fast-reroute", {})
    assert fr4.get("ti-lfa-srv6-enabled") is True

    # loopback0
    loop0 = interfaces["loopback0"]
    assert loop0["interface-id"] == "loopback0"
    assert loop0["enabled"] is True
    assert loop0.get("tag") == [1]
    loop0_ref = loop0.get("interface-ref", {})
    assert loop0_ref.get("interface") == "loopback0"
    assert loop0_ref.get("subinterface") == 0
    loop0_afs = loop0.get("afi-safi", {})
    assert "IPV6-UNICAST" in loop0_afs and "IPV4-UNICAST" in loop0_afs
    loop0_lvls = loop0.get("levels", {})
    assert "2" in loop0_lvls
    assert loop0_lvls["2"]["level-number"] == 2
    assert loop0_lvls["2"].get("enabled") is True

    # loopback1
    loop1 = interfaces["loopback1"]
    assert loop1["interface-id"] == "loopback1"
    assert loop1["enabled"] is True
    loop1_ref = loop1.get("interface-ref", {})
    assert loop1_ref.get("interface") == "loopback1"
    assert loop1_ref.get("subinterface") == 0
    loop1_afs = loop1.get("afi-safi", {})
    assert "IPV6-UNICAST" in loop1_afs
    loop1_lvls = loop1.get("levels", {})
    assert "2" in loop1_lvls
    assert loop1_lvls["2"]["level-number"] == 2
    assert loop1_lvls["2"].get("enabled") is True


def test_show_isis_config_sr_mpls_sample():
    """Validate parsing of ISIS config with SR-MPLS features (adjacency-sids, prefix-sids, ti-lfa-sr-mpls)."""

    sample_file = SAMPLES_DIR / "isis_config_sr_mpls.json"
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

    # Global settings - segment routing enabled
    glb = cfg.get("global", {})
    assert glb.get("segment-routing-enabled") is True

    # Interfaces
    interfaces = cfg.get("interfaces", {})
    assert "swp1" in interfaces
    assert "loopback0" in interfaces

    # swp1 - should have adjacency-sid and ti-lfa-sr-mpls
    swp1 = interfaces["swp1"]
    assert swp1["interface-id"] == "swp1"
    assert swp1["enabled"] is True
    assert swp1.get("network-type") == "POINT_TO_POINT"

    swp1_afs = swp1.get("afi-safi", {})
    assert "IPV4-UNICAST" in swp1_afs

    swp1_v4_af = swp1_afs["IPV4-UNICAST"]
    assert swp1_v4_af["enabled"] is True

    # Adjacency SIDs
    adj_sids = swp1_v4_af.get("adjacency-sids", [])
    assert len(adj_sids) == 1
    adj_sid = adj_sids[0]
    assert adj_sid["neighbor"] == "POINT_TO_POINT"
    assert adj_sid["sid-type"] == "INDEX"
    assert adj_sid["value"] == 12

    # Fast reroute - TI-LFA SR-MPLS
    fr = swp1_v4_af.get("fast-reroute", {})
    assert fr.get("ti-lfa-sr-mpls-enabled") is True

    # loopback0 - should have prefix-sid
    loop0 = interfaces["loopback0"]
    assert loop0["interface-id"] == "loopback0"
    assert loop0["enabled"] is True

    loop0_afs = loop0.get("afi-safi", {})
    assert "IPV4-UNICAST" in loop0_afs

    loop0_v4_af = loop0_afs["IPV4-UNICAST"]
    assert loop0_v4_af["enabled"] is True

    # Prefix SIDs
    prefix_sids = loop0_v4_af.get("prefix-sids", [])
    assert len(prefix_sids) == 1
    prefix_sid = prefix_sids[0]
    assert prefix_sid["algorithm"] == "SPF"
    assert prefix_sid["sid-type"] == "INDEX"
    assert prefix_sid["value"] == 111


def test_show_isis_config_new_knobs_sample():
    """Validate parsing of ISIS config with new knobs (auto-cost, hello-auth keychain/auth-type,
    global/interface MPLS IGP-LDP sync, AF default-information originate, interface auth keychain/auth-type,
    and per-AF IP fast-reroute)."""

    sample_file = SAMPLES_DIR / "isis_config_new_knobs.json"
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

    # Global
    glb = cfg.get("global", {})
    assert glb.get("auto-cost-reference-bandwidth") == 12345
    assert glb.get("mpls-igp-ldp-sync-enabled") is True

    hello = glb.get("hello-authentication", {})
    assert hello.get("enabled") is True
    assert hello.get("keychain") == "abc"
    assert hello.get("auth-type") == "openconfig-keychain-types:KEYCHAIN"

    # Levels (global level-mode auth and TE)
    levels = cfg.get("levels", {})
    assert "1" in levels and "2" in levels

    lvl1 = levels["1"]
    assert lvl1["level-number"] == 1
    lvl1_auth = lvl1.get("authentication", {})
    assert lvl1_auth.get("lsp-authentication") is True
    assert lvl1_auth.get("csnp-authentication") is True
    assert lvl1_auth.get("psnp-authentication") is True
    assert lvl1_auth.get("keychain") == "abc"
    assert lvl1_auth.get("auth-type") == "openconfig-keychain-types:KEYCHAIN"
    assert lvl1.get("traffic-engineering-enabled") is True

    lvl2 = levels["2"]
    assert lvl2["level-number"] == 2
    assert lvl2.get("enabled") is True
    lvl2_auth = lvl2.get("authentication", {})
    assert lvl2_auth.get("lsp-authentication") is True
    assert lvl2_auth.get("csnp-authentication") is True
    assert lvl2_auth.get("psnp-authentication") is True
    assert lvl2_auth.get("keychain") == "abc"
    assert lvl2_auth.get("auth-type") == "openconfig-keychain-types:KEYCHAIN"
    assert lvl2.get("traffic-engineering-enabled") is True

    # AF default-information originate
    afs = cfg.get("afi-safi", {})
    assert "IPV6-UNICAST" in afs
    v6 = afs["IPV6-UNICAST"]
    default_info = v6.get("default-information", {})
    assert default_info.get("enabled") is True
    assert default_info.get("export-policy") == ["pass"]

    # Interface
    interfaces = cfg.get("interfaces", {})
    assert "swp1" in interfaces
    swp1 = interfaces["swp1"]
    assert swp1["interface-id"] == "swp1"
    assert swp1["enabled"] is True

    swp1_auth = swp1.get("authentication", {})
    assert swp1_auth.get("keychain") == "abc"
    assert swp1_auth.get("auth-type") == "openconfig-keychain-types:KEYCHAIN"

    assert swp1.get("mpls-igp-ldp-sync-enabled") is True

    swp1_afs = swp1.get("afi-safi", {})
    assert "IPV6-UNICAST" in swp1_afs
    swp1_v6_af = swp1_afs["IPV6-UNICAST"]
    fr = swp1_v6_af.get("fast-reroute", {})
    assert fr.get("ip-enabled") is True


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
    ext4 = lsp.get("extended-ipv4-reachability", {})
    assert "1.1.1.1/32" in ext4
    pfx4 = ext4["1.1.1.1/32"]
    assert pfx4["ip-prefix"] == "1.1.1.1"
    assert pfx4["prefix-len"] == 32
    assert pfx4["metric"] == 10

    # MT IPv6 reachability for 2400:2020:0:1191::91/128 on rtr1.00-00
    mt6 = lsp.get("mt-ipv6-reachability", {})
    assert "2400:2020:0:1191::91/128" in mt6
    pfx6 = mt6["2400:2020:0:1191::91/128"]
    assert pfx6["ip-prefix"] == "2400:2020:0:1191::91"
    assert pfx6["prefix-len"] == 128
    assert pfx6["metric"] == 10
    assert pfx6["mt-id"] == 2

    # Also verify that LSP rtr2.00-00 contains prefix 2.2.2.2/32 in its
    # extended IPv4 reachability, and MT IPv6 2400:2020:0:2291::91/128,
    # as per the golden sample.
    lsp2 = database["rtr2.00-00"]
    ext4_lsp2 = lsp2.get("extended-ipv4-reachability", {})
    assert "2.2.2.2/32" in ext4_lsp2
    pfx4_lsp2 = ext4_lsp2["2.2.2.2/32"]
    assert pfx4_lsp2["ip-prefix"] == "2.2.2.2"
    assert pfx4_lsp2["prefix-len"] == 32
    assert pfx4_lsp2["metric"] == 10

    mt6_lsp2 = lsp2.get("mt-ipv6-reachability", {})
    assert "2400:2020:0:2291::91/128" in mt6_lsp2
    pfx6_lsp2 = mt6_lsp2["2400:2020:0:2291::91/128"]
    assert pfx6_lsp2["ip-prefix"] == "2400:2020:0:2291::91"
    assert pfx6_lsp2["prefix-len"] == 128
    assert pfx6_lsp2["metric"] == 10
    assert pfx6_lsp2["mt-id"] == 2


def test_show_isis_interface_sample():
    """Validate parsing of an ISIS interface sample (convention-compliant).

    Uses the enhanced golden sample with 4 interfaces.
    All assertions use underscored field names and stripped prefix values
    per the 4 mandatory parser conventions.
    """

    sample_file = SAMPLES_DIR / "isis_interface_enhanced.json"
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
    # All 4 interfaces present
    assert set(interfaces.keys()) == {"swp1", "swp2", "swp3", "loopback0"}

    # ---- swp1: full-featured physical interface ----
    swp1 = interfaces["swp1"]

    # Interface state (flattened, underscored, prefixes stripped)
    assert swp1["interface_id"] == "swp1"
    assert swp1["enabled"] is True
    assert swp1["circuit_type"] == "LEVEL_2"  # stripped: arcos-isis-types:LEVEL_2
    assert swp1["network_type"] == "POINT_TO_POINT"
    assert swp1["protocol_up"] is True
    assert swp1["snpa"] == "f2:d2:c6:b5:9e:a6"
    assert swp1["mtu"] == 8974

    # Augmented interface-level fields (underscored)
    assert swp1["csnp_enabled"] is True
    assert swp1["mpls_ldp_sync_enabled"] is False

    # Authentication (flattened from state{} and key.state{})
    auth = swp1.get("authentication", {})
    assert auth["hello_authentication"] is True
    assert auth["auth_type"] == "SIMPLE_KEY"  # stripped: openconfig-keychain-types:SIMPLE_KEY
    assert auth["crypto_algorithm"] == "MD5"  # stripped: arcos-openconfig-isis-augments:MD5

    # AFI-SAFI (underscored key, stripped values)
    afi_safi = swp1.get("afi_safi", {})
    assert "IPV6_UNICAST" in afi_safi

    ipv6_af = afi_safi["IPV6_UNICAST"]
    assert ipv6_af["afi_name"] == "IPV6"
    assert ipv6_af["safi_name"] == "UNICAST"
    assert ipv6_af["enabled"] is True
    assert ipv6_af.get("fast_reroute", {}).get("ti_lfa_srv6_enabled") is True
    assert ipv6_af.get("fast_reroute", {}).get("ti_lfa_sr_mpls_enabled") is False
    assert ipv6_af.get("fast_reroute", {}).get("ip_enabled") is False

    # Timers (flattened from state{}, lsp_pacing_interval forced to int)
    timers = swp1.get("timers", {})
    assert timers["csnp_interval"] == 10
    assert timers["lsp_pacing_interval"] == 33
    assert isinstance(timers["lsp_pacing_interval"], int)
    assert timers["hello_interval"] == 10
    assert timers["hello_multiplier"] == 3

    # BFD (interface level)
    bfd = swp1.get("bfd", {})
    assert bfd.get("bfd_tlv") is False

    # Circuit counters
    cc = swp1.get("circuit_counters", {})
    assert cc["adj_changes"] == 1
    assert cc["adj_number"] == 1

    # Levels (key as string "2")
    levels = swp1.get("levels", {})
    assert "2" in levels
    level2 = levels["2"]
    assert level2["enabled"] is True
    assert level2["priority"] == 64
    assert level2["metric"] == 1000000

    # Level packet counters (underscored keys)
    pkt = level2.get("packet_counters", {})
    assert "iih" in pkt
    assert pkt["iih"]["sent"] > 0

    # Level hello_authentication (reuses _parse_authentication)
    level_auth = level2.get("hello_authentication", {})
    assert level_auth["hello_authentication"] is True
    assert level_auth["auth_type"] == "SIMPLE_KEY"
    assert level_auth["crypto_algorithm"] == "MD5"

    # Adjacency (underscored keys)
    adjacencies = level2.get("adjacencies", {})
    assert "zr11" in adjacencies
    adj = adjacencies["zr11"]
    assert adj["system_id"] == "zr11"
    assert adj["adjacency_state"] == "UP"
    assert adj.get("usable") is True
    assert adj["up_time"] == 27988988

    # Adjacency BFD with topologies (mt_id as int key)
    adj_bfd = adj.get("bfd", {})
    assert adj_bfd["bfd_required"] is False
    topos = adj_bfd.get("topologies", {})
    assert 0 in topos
    assert 2 in topos
    # mt_id 0: ipv4 fields
    topo0 = topos[0]
    assert topo0["mt_id"] == 0
    assert topo0["ipv4_bfd_up"] is False
    assert topo0["ipv4_up"] is False
    assert topo0["usable"] is False
    # mt_id 2: ipv6 fields
    topo2 = topos[2]
    assert topo2["mt_id"] == 2
    assert topo2["ipv6_bfd_up"] is False
    assert topo2["ipv6_up"] is True
    assert topo2["usable"] is True

    # Dynamic delay measurement (underscored)
    ddm = adj.get("dynamic_delay_measurement", {})
    assert ddm["enabled"] is False
    assert ddm["num_advertisements_sent"] == 0
    assert ddm["last_sampled_avg_delay_value"] == 0

    # ---- loopback0: special interface ----
    lo0 = interfaces["loopback0"]
    assert lo0["interface_id"] == "loopback0"
    assert lo0["enabled"] is True
    assert lo0["circuit_type"] == "LEVEL_1_2"  # stripped prefix
    assert lo0["passive"] is False

    # loopback0 has 2 levels (1 and 2)
    lo_levels = lo0.get("levels", {})
    assert "1" in lo_levels
    assert "2" in lo_levels

    # loopback0 has no adjacencies
    for lvl_key in ("1", "2"):
        assert "adjacencies" not in lo_levels[lvl_key]

    # loopback0 should not have circuit_counters (all zeros, empty state{})
    assert "circuit_counters" not in lo0


def test_show_isis_interface_convention_compliance():
    """Verify all 4 mandatory parser conventions are met in output."""

    sample_file = SAMPLES_DIR / "isis_interface_enhanced.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowIsisInterface(device="dummy")
    result = parser.cli(interface=None, output=output)

    def check_keys(obj, path=""):
        """Recursively verify all keys use underscore convention (no hyphens in field names)."""
        if isinstance(obj, dict):
            for key, val in obj.items():
                full_path = f"{path}.{key}" if path else key

                # Conv 1: Multi-word keys must use underscores, not hyphens.
                # Exception: top-level "network-instance" key (pyATS convention).
                if "-" in str(key) and key != "network-instance":
                    assert False, (
                        f"Hyphenated key at {full_path}: {key} (should use underscores)"
                    )

                # Conv 2: no state/config wrapper keys
                assert key not in ("state", "config"), (
                    f"state/config wrapper at {full_path}"
                )

                # Conv 4: check value prefixes are stripped
                if isinstance(val, str):
                    for prefix in (
                        "arcos-isis-types:",
                        "openconfig-isis-types:",
                        "oc-isis-types:",
                        "arcos-openconfig-isis-augments:",
                        "openconfig-keychain-types:",
                        "oc-pol-types:",
                    ):
                        assert not val.startswith(prefix), (
                            f"Prefixed value at {full_path}: {val}"
                        )
                check_keys(val, full_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_keys(item, f"{path}[{i}]")

    check_keys(result)


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
    assert v4["afi-name"] == "IPV4"
    assert v4["safi-name"] == "UNICAST"

    v4_routes = v4["routes"]
    assert "1.1.1.1/32" in v4_routes and "2.2.2.2/32" in v4_routes

    r1 = v4_routes["1.1.1.1/32"]
    assert r1["prefix"] == "1.1.1.1/32"
    assert r1["best-level-number"] == 2
    lvl2_r1 = r1["levels"]["2"]
    assert lvl2_r1["metric"] == 10
    assert "connected" in lvl2_r1["flags"] and "best" in lvl2_r1["flags"]

    r2 = v4_routes["2.2.2.2/32"]
    lvl2_r2 = r2["levels"]["2"]
    assert lvl2_r2["metric"] == 20
    assert "remote" in lvl2_r2["flags"] and "best" in lvl2_r2["flags"]
    assert lvl2_r2["next-hop-id"] == "2147483649"

    v6 = routes_afs["IPV6-UNICAST"]
    assert v6["afi-name"] == "IPV6"
    assert v6["safi-name"] == "UNICAST"

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

    redist_afs = isis.get("redistribute-routes", {})
    assert "IPV6-UNICAST" in redist_afs and "IPV4-UNICAST" in redist_afs

    v6 = redist_afs["IPV6-UNICAST"]
    routes_v6 = v6["routes"]
    assert "1:1:1::1/128" in routes_v6 and "10:20::/120" in routes_v6

    r6_1 = routes_v6["1:1:1::1/128"]
    lvl2_r6_1 = r6_1["levels"]["2"]
    assert lvl2_r6_1["metric"] == 10
    assert lvl2_r6_1["route-tag"] == 0
    assert "connected" in lvl2_r6_1["flags"]
    assert lvl2_r6_1["source-identifier"] == "ISIS"
    assert lvl2_r6_1["source-name"] == "default@default"

    v4 = redist_afs["IPV4-UNICAST"]
    routes_v4 = v4["routes"]
    assert "1.1.1.1/32" in routes_v4 and "10.20.0.0/24" in routes_v4

    r4_1 = routes_v4["1.1.1.1/32"]
    lvl2_r4_1 = r4_1["levels"]["2"]
    assert lvl2_r4_1["metric"] == 10
    assert lvl2_r4_1["route-tag"] == 0
    assert "connected" in lvl2_r4_1["flags"]
    assert lvl2_r4_1["source-identifier"] == "ISIS"
    assert lvl2_r4_1["source-name"] == "default@default"


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

    frr = isis.get("fast-reroute", {})
    assert "IPV6-UNICAST" in frr

    af = frr["IPV6-UNICAST"]
    assert af["afi-name"] == "IPV6"
    assert af["safi-name"] == "UNICAST"

    prefixes = af["prefixes"]
    # The sample contains multiple prefixes; validate a representative one.
    assert "2::2/128" in prefixes
    pfx = prefixes["2::2/128"]
    lvl2 = pfx["levels"]["2"]
    assert lvl2["metric"] == 20
    assert lvl2["nexthop-interface"] == "swp4"
    assert lvl2["nexthop-address"] == "::"
    assert lvl2["origin-system-id"] == "rtr2.00"


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

    flex = isis.get("flex-algo-fast-reroute", {})
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
    assert lvl2["nexthop-interface"] == "swp4"
    assert lvl2["nexthop-address"] == "::"


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

    flex = isis.get("flex-algo-routes", {})
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
    assert r["best-level-number"] == 2
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
    assert mpls.get("igp-ldp-sync-enabled") is False

    label_db = mpls.get("label-db", {})
    state = label_db.get("state", {})
    assert state.get("protocol-identifier") == "ISIS"
    assert state.get("protocol-name") == "default"
    assert state.get("configured-blocks") == 2
    assert state.get("active-blocks") == 2
    assert state.get("active-usages") == 2

    # Statistics
    stats = label_db.get("statistics", {})
    assert stats.get("label-space") == 20000
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
    assert srgb.get("blocks-count") == 1
    assert srgb.get("opaque-flags") == "0c"

    srgb_stats = srgb.get("statistics", {})
    assert srgb_stats.get("label-space") == 10000
    assert srgb_stats.get("labels") == 3

    # SRGB blocks
    srgb_blocks = srgb.get("blocks", {})
    assert "10000" in srgb_blocks
    block_10000 = srgb_blocks["10000"]
    assert block_10000["lower-bound"] == 10000
    assert block_10000["upper-bound"] == 19999
    assert block_10000.get("block-name") == "rb1"

    # SRGB labels
    srgb_labels = srgb.get("labels", {})
    assert "10111" in srgb_labels
    label_10111 = srgb_labels["10111"]
    assert label_10111["label"] == 10111
    assert label_10111.get("block-name") == "rb1"
    key_10111 = label_10111.get("label-key", {})
    assert key_10111.get("type") == "KEY_IPV4_PREFIX"
    assert key_10111.get("ip-prefix") == "1.1.1.1/32"

    # SRLB usage
    srlb = usages["ISIS_SRLB"]
    assert srlb["usage"] == "ISIS_SRLB"

    # SRLB labels (adjacency labels)
    srlb_labels = srlb.get("labels", {})
    assert "20012" in srlb_labels
    label_20012 = srlb_labels["20012"]
    assert label_20012["label"] == 20012
    key_20012 = label_20012.get("label-key", {})
    assert key_20012.get("type") == "KEY_IPV4_ADJ"
    assert key_20012.get("nh-address") == "10.20.0.20"
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
    ext_is = lsp.get("extended-is-neighbor", {})
    assert len(ext_is) >= 2  # At least rtr2 and rtr3 neighbors

    # Check neighbor rtr2.00 with instance 802
    nbr_key = "rtr2.00:802"
    assert nbr_key in ext_is
    nbr = ext_is[nbr_key]

    assert nbr["system-id"] == "rtr2.00"
    assert nbr["instance-id"] == "802"
    assert nbr["metric"] == 10
    assert nbr.get("two-way") is True

    # Link ID
    assert "link-id" in nbr
    assert nbr["link-id"]["local"] == 802
    assert nbr["link-id"]["remote"] == 801

    # IPv4 addresses
    assert nbr.get("ipv4-interface-address") == ["10.20.0.10"]
    assert nbr.get("ipv4-neighbor-address") == ["10.20.0.20"]

    # IPv6 address
    assert nbr.get("ipv6-interface-address") == ["10:20::10"]

    # Adjacency SID (SR-MPLS)
    adj_sids = nbr.get("adjacency-sids", [])
    assert len(adj_sids) >= 1
    adj_sid = adj_sids[0]
    assert adj_sid["sid"] == 20012
    assert "VALUE" in adj_sid.get("flags", [])
    assert "LOCAL" in adj_sid.get("flags", [])
    assert adj_sid.get("weight") == 0

    # ASLA (Application-Specific Link Attributes)
    asla = nbr.get("asla", {})
    assert asla.get("application") == "flexible-algorithm"
    assert "admin-groups" in asla
    assert "red" in asla["admin-groups"]
    assert asla.get("te-metric") == 10
    assert asla.get("min-delay") == 5
    assert asla.get("max-delay") == 5


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
    ext_is = lsp.get("extended-is-neighbor", {})
    assert len(ext_is) >= 1

    # Check neighbor rtr2.00:802
    nbr_key = "rtr2.00:802"
    assert nbr_key in ext_is
    nbr = ext_is[nbr_key]

    # Adjacency SID should be present
    adj_sids = nbr.get("adjacency-sids", [])
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
    mt_is = lsp.get("mt-is-neighbor", {})
    assert len(mt_is) >= 1

    # Check neighbor rtr2.00 with mt-id 2, instance 802
    nbr_key = "rtr2.00:mt2:802"
    assert nbr_key in mt_is
    nbr = mt_is[nbr_key]

    assert nbr["system-id"] == "rtr2.00"
    assert nbr["mt-id"] == 2
    assert nbr["instance-id"] == "802"
    assert nbr["metric"] == 10
    assert nbr.get("two-way") is True

    # Link ID
    assert "link-id" in nbr
    assert nbr["link-id"]["local"] == 802

    # IPv4/IPv6 addresses
    assert nbr.get("ipv4-interface-address") == ["10.20.0.10"]
    assert nbr.get("ipv6-interface-address") == ["10:20::10"]

    # ASLA (FlexAlgo attributes)
    asla = nbr.get("asla", {})
    assert asla.get("application") == "flexible-algorithm"
    assert "admin-groups" in asla
    assert asla.get("min-delay") == 109  # Different delay value in MT_ISN

    # SRv6 End.X SID (should be present in MT_ISN)
    end_x_sids = nbr.get("end-x-sids", [])
    assert len(end_x_sids) >= 1
    end_x = end_x_sids[0]
    assert end_x["sid"] == "2400:2020:0:1191:8004::"
    assert end_x.get("algorithm") == "SPF"
    assert end_x.get("endpoint-func") == "END_X_PSP_USD"
    assert end_x.get("weight") == 0

    # SID structure
    sid_struct = end_x.get("sid-structure", {})
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
    ext4 = lsp.get("extended-ipv4-reachability", {})
    assert "1.1.1.1/32" in ext4

    pfx = ext4["1.1.1.1/32"]
    assert pfx["ip-prefix"] == "1.1.1.1"
    assert pfx["prefix-len"] == 32
    assert pfx["metric"] == 10

    # Prefix Tag
    assert pfx.get("tag") == [1]

    # Prefix SID (SR-MPLS)
    prefix_sids = pfx.get("prefix-sids", [])
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
    assert router_cap.get("instance-number") == 1
    assert router_cap.get("router-id") == "1.1.1.1"

    # IPv6 TE Router ID
    assert router_cap.get("ipv6-te-router-id") == "1::1"

    # SR Algorithms
    sr_algos = router_cap.get("sr-algorithms", [])
    assert "SPF" in sr_algos
    assert 131 in sr_algos
    assert 132 in sr_algos

    # SR Capability (SRGB)
    sr_cap = router_cap.get("sr-capability", {})
    assert "IPV4_MPLS" in sr_cap.get("flags", [])
    assert "IPV6_MPLS" in sr_cap.get("flags", [])
    assert sr_cap.get("range") == 10000
    assert sr_cap.get("label") == 10000

    # SRLB
    srlb = router_cap.get("srlb", {})
    assert srlb.get("range") == 10000
    assert srlb.get("label") == 20000

    # Node MSD
    node_msd = router_cap.get("node-msd", {})
    assert node_msd.get("srv6_max_segments_left") == 10
    assert node_msd.get("srv6_max_end_pop") == 5
    assert node_msd.get("srv6_max_h_encaps") == 3
    assert node_msd.get("srv6_max_end_d") == 10

    # Flex-Algo Definitions
    fads = router_cap.get("flex-algo-definitions", {})
    assert "131" in fads
    assert fads["131"].get("priority") == 128
    assert fads["131"].get("metric-type") == "LINK_DELAY"
    assert "132" in fads
    assert fads["132"].get("metric-type") == "IGP_METRIC"


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
    assert spf_loc["mt-id"] == 2
    assert spf_loc["metric"] == 10

    # Verify End SID parsing
    end_sids = spf_loc.get("end-sids", [])
    assert len(end_sids) >= 1

    end_sid = end_sids[0]
    assert end_sid["sid"] == "2400:2020:0:1191:1::"
    assert end_sid.get("endpoint-func") == "END_PSP_USD"

    # Verify SID structure
    sid_struct = end_sid.get("sid-structure", {})
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


def test_show_isis_level_state_sample():
    """Validate parsing of ISIS level state sample."""

    sample_file = SAMPLES_DIR / "isis_level_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLevelState(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result

    ni = result["network-instance"].get("default", {})
    assert "isis" in ni

    isis = ni["isis"].get("default", {})
    assert "levels" in isis

    levels = isis["levels"]
    assert "2" in levels

    level2 = levels["2"]
    assert level2["level"] == 2
    assert level2["enabled"] is True
    assert level2["metric-style"] == "WIDE_METRIC"
    assert level2["lsp-count"] == 4

    # Dynamic hostname - should be dict keyed by system-id
    dyn_hostname = level2.get("dynamic-hostname", {})
    assert "1111.1111.1111" in dyn_hostname
    assert dyn_hostname["1111.1111.1111"] == "rtr1"
    assert dyn_hostname["2222.2222.2222"] == "rtr2"
    assert dyn_hostname["3333.3333.3333"] == "rtr3"


def test_show_isis_level_state_with_filter():
    """Test level state parser with level filter."""

    sample_file = SAMPLES_DIR / "isis_level_state.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLevelState(device="dummy")

    # Filter by specific level
    result = parser.cli(level="2", output=output)
    levels = result["network-instance"]["default"]["isis"]["default"]["levels"]
    assert "2" in levels
    assert len(levels) == 1

    # Filter by non-existent level
    result = parser.cli(level="1", output=output)
    # Should return empty since level 1 doesn't exist in sample
    assert result.get("network-instance", {}).get("default", {}).get("isis", {}).get(
        "default", {}
    ).get("levels", {}) == {}


def test_show_isis_level_counters_sample():
    """Validate parsing of ISIS level counters sample."""

    sample_file = SAMPLES_DIR / "isis_level_counters.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLevelCounters(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result

    ni = result["network-instance"].get("default", {})
    assert "isis" in ni

    isis = ni["isis"].get("default", {})
    assert "levels" in isis

    levels = isis["levels"]
    assert "2" in levels

    level2 = levels["2"]

    # Verify all counter fields
    assert level2["corrupted-lsps"] == 0
    assert level2["database-overloads"] == 0
    assert level2["manual-address-drop-from-areas"] == 0
    assert level2["exceed-max-seq-nums"] == 0
    assert level2["seq-num-skips"] == 0
    assert level2["own-lsp-purges"] == 0
    assert level2["id-len-mismatch"] == 0
    assert level2["part-changes"] == 0
    assert level2["max-area-address-mismatches"] == 0
    assert level2["auth-fails"] == 0
    assert level2["auth-type-fails"] == 0
    assert level2["spf-runs"] == 35
    assert level2["lsp-errors"] == 0


def test_show_isis_level_counters_with_filter():
    """Test level counters parser with level filter."""

    sample_file = SAMPLES_DIR / "isis_level_counters.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLevelCounters(device="dummy")

    # Filter by specific level
    result = parser.cli(level="2", output=output)
    levels = result["network-instance"]["default"]["isis"]["default"]["levels"]
    assert "2" in levels
    assert levels["2"]["spf-runs"] == 35

    # Filter by non-existent level
    result = parser.cli(level="1", output=output)
    # Should return empty since level 1 doesn't exist in sample
    assert result.get("network-instance", {}).get("default", {}).get("isis", {}).get(
        "default", {}
    ).get("levels", {}) == {}


def test_show_isis_spf_log_sample():
    """Validate parsing of ISIS SPF log sample."""

    sample_file = SAMPLES_DIR / "isis_spf_log.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowIsisSpfLog(device="dummy")
    result = parser.cli(output=output)

    # Verify structure
    assert "network-instance" in result
    assert "default" in result["network-instance"]
    assert "isis" in result["network-instance"]["default"]
    assert "default" in result["network-instance"]["default"]["isis"]
    assert "spf-log" in result["network-instance"]["default"]["isis"]["default"]

    spf_log = result["network-instance"]["default"]["isis"]["default"]["spf-log"]

    # Verify we have 3 events
    assert len(spf_log) == 3
    assert "105" in spf_log
    assert "106" in spf_log
    assert "109" in spf_log

    # Verify incomplete event (route-only, id=105 - no duration/end_time)
    event_105 = spf_log["105"]
    assert event_105["id"] == 105
    assert event_105["spf-type"] == "route-only"
    assert event_105["level"] == 2
    assert event_105["topology-id"] == "ISIS_MT_ID0_STANDARD"
    assert event_105["algorithm"] == 132
    assert event_105["delay"] == 200000
    assert "duration" not in event_105  # incomplete
    assert "start-time" not in event_105
    assert "end-time" not in event_105
    # Verify trigger-lsp list
    assert len(event_105["trigger-lsp"]) == 3
    assert event_105["trigger-lsp"][0]["lsp-id"] == "rtr1.00-00"
    assert event_105["trigger-lsp"][0]["sequence"] == 244

    # Verify complete event (full, id=106)
    event_106 = spf_log["106"]
    assert event_106["id"] == 106
    assert event_106["spf-type"] == "full"
    assert event_106["level"] == 2
    assert event_106["topology-id"] == "ISIS_MT_ID2_IPV6_UNICAST"
    assert event_106["algorithm"] == 0
    assert event_106["delay"] == 200000
    assert event_106["duration"] == 1284
    assert event_106["node-count"] == 1
    assert event_106["prefix-count"] == 0
    assert event_106["route-download-count"] == 0
    assert "start-time" in event_106
    assert "end-time" in event_106
    assert len(event_106["trigger-lsp"]) == 2

    # Verify another complete event (id=109) with different prefix count
    event_109 = spf_log["109"]
    assert event_109["id"] == 109
    assert event_109["spf-type"] == "full"
    assert event_109["algorithm"] == 0
    assert event_109["duration"] == 292
    assert event_109["prefix-count"] == 8
    assert len(event_109["trigger-lsp"]) == 1


def test_show_isis_spf_log_enhanced():
    """Validate parsing of enhanced ISIS SPF log with many events and algorithms."""

    sample_file = SAMPLES_DIR / "isis_spf_log_enhanced.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowIsisSpfLog(device="dummy")
    result = parser.cli(output=output)

    # Verify structure
    assert "network-instance" in result
    assert "default" in result["network-instance"]
    assert "isis" in result["network-instance"]["default"]
    assert "default" in result["network-instance"]["default"]["isis"]
    assert "spf-log" in result["network-instance"]["default"]["isis"]["default"]

    spf_log = result["network-instance"]["default"]["isis"]["default"]["spf-log"]

    # Verify we have many events (128 in the enhanced sample)
    assert len(spf_log) == 128

    # Verify route-only event with algorithm 131 (id=226)
    event_226 = spf_log["226"]
    assert event_226["id"] == 226
    assert event_226["spf-type"] == "route-only"
    assert event_226["level"] == 2
    assert event_226["topology-id"] == "ISIS_MT_ID0_STANDARD"
    assert event_226["algorithm"] == 131
    assert event_226["delay"] == 200000
    assert event_226["duration"] == 9
    assert event_226["node-count"] == 0
    assert len(event_226["trigger-lsp"]) == 1

    # Verify IPv6 topology event (id=227)
    event_227 = spf_log["227"]
    assert event_227["topology-id"] == "ISIS_MT_ID2_IPV6_UNICAST"
    assert event_227["prefix-count"] == 2

    # Verify full SPF with algorithm 0 (id=228)
    event_228 = spf_log["228"]
    assert event_228["spf-type"] == "full"
    assert event_228["algorithm"] == 0
    assert event_228["node-count"] == 3
    assert event_228["prefix-count"] == 6
    assert event_228["route-download-count"] == 2

    # Verify event with algorithm 132 (id=230)
    event_230 = spf_log["230"]
    assert event_230["algorithm"] == 132

    # Verify event with multiple trigger LSPs (id=246 has 3 triggers)
    event_246 = spf_log["246"]
    assert event_246["id"] == 246
    assert event_246["spf-type"] == "full"
    assert event_246["delay"] == 3200000
    assert len(event_246["trigger-lsp"]) == 3
    # Verify trigger LSP details
    trigger_lsps = event_246["trigger-lsp"]
    assert trigger_lsps[0]["lsp-id"] == "rtr1.00-00"
    assert trigger_lsps[0]["sequence"] == 25
    assert trigger_lsps[1]["lsp-id"] == "rtr1.00-01"
    assert trigger_lsps[2]["lsp-id"] == "rtr3.00-00"


# ============================================================================
# ShowIsisProtectionTracker tests
# ============================================================================

def test_show_isis_protection_tracker_single():
    """Validate parsing of a single-entry protection-tracker."""

    sample_file = SAMPLES_DIR / "isis_protection_tracker_single.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisProtectionTracker(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "network-instance" in result
    isis = result["network-instance"]["default"]["isis"]["default"]
    trackers = isis["global"]["protection-trackers"]["protection-tracker"]

    # Exactly one tracker — id is implementation-assigned at runtime,
    # so assert properties rather than a specific id value.
    assert len(trackers) == 1
    (tracker_id, entry), = trackers.items()
    assert entry["id"] == tracker_id
    assert isinstance(entry["reference-count"], int)
    assert entry["reference-count"] >= 1
    assert entry["interface"] == "swp1"
    assert entry["system-id"] == "rtr2.00"
    assert "last-updated-time" in entry
    assert "T" in entry["last-updated-time"]   # RFC 3339 shape sanity


def test_show_isis_protection_tracker_multi():
    """Validate parsing of a multi-entry protection-tracker (TI-LFA on
    multiple interfaces of the same device)."""

    sample_file = SAMPLES_DIR / "isis_protection_tracker_multi.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisProtectionTracker(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    isis = result["network-instance"]["default"]["isis"]["default"]
    trackers = isis["global"]["protection-trackers"]["protection-tracker"]

    # Two trackers: id 268435459 (swp1 → rtr6.00) and 268435460 (swp2 → rtr2.00)
    assert len(trackers) == 2
    assert "268435459" in trackers
    assert "268435460" in trackers

    swp1 = trackers["268435459"]
    assert swp1["interface"] == "swp1"
    assert swp1["system-id"] == "rtr6.00"
    assert swp1["reference-count"] == 1

    swp2 = trackers["268435460"]
    assert swp2["interface"] == "swp2"
    assert swp2["system-id"] == "rtr2.00"
    assert swp2["reference-count"] == 1


def test_show_isis_protection_tracker_empty():
    """Validate the empty case — no TI-LFA enabled, device returns
    `{"data": {}}` and the parser returns an empty dict."""

    sample_file = SAMPLES_DIR / "isis_protection_tracker_empty.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisProtectionTracker(device="dummy")
    result = parser.cli(output=output)

    assert result == {}


def test_show_isis_protection_tracker_convention_compliance():
    """Spot-check Convention 1: all schema keys hyphenated, none with underscores."""
    import re

    parser = ShowIsisProtectionTracker(device="dummy")
    schema_str = repr(parser.schema)
    # Find Optional("foo_bar") style violations (lowercase with underscore inside Optional)
    violations = re.findall(
        r"Optional\(['\"]([a-z][a-z0-9]*(?:_[a-z0-9]+)+)['\"]\)", schema_str
    )
    assert violations == [], f"Schema has underscore-keys: {violations}"


# ============================================================================
# ShowIsisGlobalTunnel
# ============================================================================
#
# Captures SRv6 TI-LFA + Microloop-Avoidance tunnel state from
# `show network-instance default protocol ISIS default global tunnel`.
#
# All three captured live JSON samples (P_AND_Q_ARE_ADJACENT with adjacent P,
# PQ_IS_REMOTE, and P_AND_Q_ARE_ADJACENT with remote P) land at num-sids=1
# due to arcOS's PSP optimization — the schema's `list` typing for `sids`
# stays forward-compatible with multi-SID stacks.


def _isis_global_tunnel_only_tunnel(result, ni="default", inst="default"):
    """Return the (id, entry) pair when exactly one tunnel is parsed."""
    assert isinstance(result, dict)
    assert "network-instance" in result
    isis = result["network-instance"][ni]["isis"][inst]
    tunnels = isis["tunnels"]
    assert len(tunnels) == 1, f"Expected 1 tunnel, got {len(tunnels)}: {tunnels}"
    (tunnel_id, entry), = tunnels.items()
    return tunnel_id, entry


def test_show_isis_global_tunnel_p_and_q_adj_p_adj():
    """Validate parse of P_AND_Q_ARE_ADJACENT scenario where P is adjacent.

    Tunnel SID destination is rtr4's End.X SID toward rtr5
    (``fcbb:bb00:94:8002::``).
    """
    sample_file = SAMPLES_DIR / "isis_global_tunnel_p_and_q_adj_p_adj.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisGlobalTunnel(device="dummy")
    result = parser.cli(output=sample_file.read_text())

    tunnel_id, entry = _isis_global_tunnel_only_tunnel(result)

    assert entry["id"] == tunnel_id == "268435472"
    assert entry["nexthop-interface"] == "swp2"
    assert entry["tunnel-type"] == "SRV6_TUNNEL"
    assert entry["users"] == ["TI_LFA_TUNNEL"]
    assert entry["reference-count"] == 4

    srv6 = entry["srv6-tunnel"]
    assert srv6["destination"] == "fcbb:bb00:94:8002::"
    assert srv6["num-sids"] == 1
    assert srv6["sids"] == ["fcbb:bb00:94:8002::"]


def test_show_isis_global_tunnel_pq_is_remote():
    """Validate parse of PQ_IS_REMOTE scenario.

    Tunnel SID is rtr5's End SID (``fcbb:bb00:95:1::``).
    """
    sample_file = SAMPLES_DIR / "isis_global_tunnel_pq_is_remote.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisGlobalTunnel(device="dummy")
    result = parser.cli(output=sample_file.read_text())

    _tid, entry = _isis_global_tunnel_only_tunnel(result)
    assert entry["users"] == ["TI_LFA_TUNNEL"]
    assert entry["tunnel-type"] == "SRV6_TUNNEL"
    srv6 = entry["srv6-tunnel"]
    assert srv6["destination"] == "fcbb:bb00:95:1::"
    assert srv6["num-sids"] == 1
    assert srv6["sids"] == ["fcbb:bb00:95:1::"]


def test_show_isis_global_tunnel_p_and_q_adj_p_remote():
    """Validate parse of P_AND_Q_ARE_ADJACENT scenario where P is remote.

    Tunnel SID destination is rtr5's End.X SID toward rtr6
    (``fcbb:bb00:95:8003::``) — even though P=rtr5 is two hops from rtr1,
    arcOS uses PSP optimization and emits a single SID.
    """
    sample_file = SAMPLES_DIR / "isis_global_tunnel_p_and_q_adj_p_remote.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisGlobalTunnel(device="dummy")
    result = parser.cli(output=sample_file.read_text())

    _tid, entry = _isis_global_tunnel_only_tunnel(result)
    srv6 = entry["srv6-tunnel"]
    assert srv6["destination"] == "fcbb:bb00:95:8003::"
    assert srv6["num-sids"] == 1
    assert srv6["sids"] == ["fcbb:bb00:95:8003::"]


def test_show_isis_global_tunnel_empty():
    """Empty data `{"data": {}}` returns an empty dict (no tunnels)."""
    sample_file = SAMPLES_DIR / "isis_global_tunnel_empty.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisGlobalTunnel(device="dummy")
    result = parser.cli(output=sample_file.read_text())
    assert result == {}


def test_show_isis_global_tunnel_schema_keys_hyphenated():
    """Convention 1: all schema keys hyphenated, none with underscores."""
    import re

    parser = ShowIsisGlobalTunnel(device="dummy")
    schema_str = repr(parser.schema)
    violations = re.findall(
        r"Optional\(['\"]([a-z][a-z0-9]*(?:_[a-z0-9]+)+)['\"]\)", schema_str
    )
    assert violations == [], f"Schema has underscore-keys: {violations}"


# ============================================================================
# ShowIsisFastReroute — p-node/q-node schema extension
# ============================================================================
#
# arcOS emits two distinct JSON node shapes depending on the FR flag:
#   PQ_IS_ADJACENT / PQ_IS_REMOTE  → pq-node.state.system-id (collapsed)
#   P_AND_Q_ARE_ADJACENT           → p-node + q-node (separate)
# The parser extracts whichever fields are present; tests below cover both.


def _isis_fast_reroute_first_level(result, prefix):
    """Return the first level entry from a single-prefix FR result."""
    isis = result["network-instance"]["default"]["isis"]["default"]
    fr = isis["fast-reroute"]["IPV6-UNICAST"]["prefixes"][prefix]
    levels = fr["levels"]
    assert len(levels) >= 1
    _level_num, level_entry = next(iter(levels.items()))
    return level_entry


def test_show_isis_fast_reroute_pq_is_remote():
    """PQ_IS_REMOTE → pq-node-system-id present, p/q-node fields absent."""
    sample_file = SAMPLES_DIR / "isis_fast_reroute_pq_is_remote.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisFastReroute(device="dummy")
    result = parser.cli(output=sample_file.read_text())
    level = _isis_fast_reroute_first_level(result, "fcbb:bb00:96::/48")

    assert level["reroute-type"] == "TI_LFA"
    assert any("PQ_IS_REMOTE" in f for f in level["flags"])
    assert level["pq-node-system-id"] == "rtr5.00"
    assert "p-node-system-id" not in level
    assert "q-node-system-id" not in level


def test_show_isis_fast_reroute_p_and_q_adjacent_p_adj():
    """P_AND_Q_ARE_ADJACENT (P adj) → p-node + q-node populated, pq-node absent."""
    sample_file = SAMPLES_DIR / "isis_fast_reroute_p_and_q_adj_p_adj.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisFastReroute(device="dummy")
    result = parser.cli(output=sample_file.read_text())
    level = _isis_fast_reroute_first_level(result, "fcbb:bb00:96::/48")

    assert any("P_AND_Q_ARE_ADJACENT" in f for f in level["flags"])
    assert level["p-node-system-id"] == "rtr4.00"
    assert level["q-node-system-id"] == "rtr5.00"
    assert "pq-node-system-id" not in level


def test_show_isis_fast_reroute_p_and_q_adjacent_p_remote():
    """P_AND_Q_ARE_ADJACENT (P remote) — same shape, different system-ids."""
    sample_file = SAMPLES_DIR / "isis_fast_reroute_p_and_q_adj_p_remote.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisFastReroute(device="dummy")
    result = parser.cli(output=sample_file.read_text())
    level = _isis_fast_reroute_first_level(result, "fcbb:bb00:96::/48")

    assert level["p-node-system-id"] == "rtr5.00"
    assert level["q-node-system-id"] == "rtr6.00"


def test_show_isis_fast_reroute_q_null_docker_quirk():
    """Docker quirk: engine couldn't resolve Q → q-node.state.system-id is
    "0000.0000.0000.00". Parser must pass it through, not choke."""
    sample_file = SAMPLES_DIR / "isis_fast_reroute_q_null_docker_quirk.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    parser = ShowIsisFastReroute(device="dummy")
    result = parser.cli(output=sample_file.read_text())
    # This is the loopback target 2001::6/128 — the older capture used the
    # loopback prefix, not the locator prefix.
    isis = result["network-instance"]["default"]["isis"]["default"]
    prefixes = isis["fast-reroute"]["IPV6-UNICAST"]["prefixes"]
    # Take the first prefix in the dict
    prefix_key = next(iter(prefixes))
    level = _isis_fast_reroute_first_level(result, prefix_key)

    assert level["p-node-system-id"] == "rtr4.00"
    assert level["q-node-system-id"] == "0000.0000.0000.00"
