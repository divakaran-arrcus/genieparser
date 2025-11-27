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
    ShowIsisRedistributeRoute,
    ShowIsisRoute,
)


# Default location of ArcOS golden samples from the local arrcus_pyats repo.
# Can be overridden by setting ARCOS_PARSER_SAMPLES_DIR.
SAMPLES_DIR = Path(
    os.environ.get(
        "ARCOS_PARSER_SAMPLES_DIR",
        "/Users/divakaran/arrcus_workspace/isis_pyats/arrcus-pyats/arrcus_pyats/tests/test_samples",
    )
)

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS golden samples directory not available",
)


FAST_REROUTE_SAMPLE = """
{
  "data": {
    "openconfig-network-instance:network-instances": {
      "network-instance": [
        {
          "name": "default",
          "protocols": {
            "protocol": [
              {
                "identifier": "openconfig-policy-types:ISIS",
                "name": "default",
                "isis": {
                  "global": {
                    "afi-safi": {
                      "af": [
                        {
                          "afi-name": "openconfig-isis-types:IPV6",
                          "safi-name": "openconfig-isis-types:UNICAST",
                          "arcos-openconfig-isis-augments:fast-reroutes": {
                            "fast-reroute": [
                              {
                                "prefix": "2001:db8::/64",
                                "levels": {
                                  "level": [
                                    {
                                      "level-number": 2,
                                      "state": {
                                        "reroute-type": "TI_LFA",
                                        "metric": 10,
                                        "nexthop-address": "fe80::1",
                                        "nexthop-interface": "swp1",
                                        "flags": [
                                          "arcos-openconfig-isis-augments:remote"
                                        ],
                                        "last-updated-time": "2025-11-21T08:10:49.811578+00:00",
                                        "origin-system-id": "0000.0000.0001"
                                      },
                                      "pq-node": {
                                        "state": {
                                          "system-id": "0000.0000.0002"
                                        }
                                      }
                                    }
                                  ]
                                }
                              }
                            ]
                          }
                        }
                      ]
                    }
                  }
                }
              }
            ]
          }
        }
      ]
    }
  }
}
"""


FLEX_ALGO_FAST_REROUTE_SAMPLE = """
{
  "data": {
    "openconfig-network-instance:network-instances": {
      "network-instance": [
        {
          "name": "default",
          "protocols": {
            "protocol": [
              {
                "identifier": "openconfig-policy-types:ISIS",
                "name": "default",
                "isis": {
                  "global": {
                    "afi-safi": {
                      "af": [
                        {
                          "afi-name": "openconfig-isis-types:IPV6",
                          "safi-name": "openconfig-isis-types:UNICAST",
                          "arcos-openconfig-isis-augments:flexible-algorithms": {
                            "flexible-algorithm": [
                              {
                                "id": 128,
                                "fast-reroutes": {
                                  "fast-reroute": [
                                    {
                                      "prefix": "2001:db8:fa::/64",
                                      "levels": {
                                        "level": [
                                          {
                                            "level-number": 2,
                                            "state": {
                                              "reroute-type": "TI_LFA",
                                              "metric": 20,
                                              "nexthop-address": "fe80::2",
                                              "nexthop-interface": "swp2",
                                              "flags": [
                                                "arcos-openconfig-isis-augments:remote"
                                              ],
                                              "last-updated-time": "2025-11-21T08:10:49.811578+00:00",
                                              "origin-system-id": "0000.0000.0003"
                                            },
                                            "pq-node": {
                                              "state": {
                                                "system-id": "0000.0000.0004"
                                              }
                                            }
                                          }
                                        ]
                                      }
                                    }
                                  ]
                                }
                              }
                            ]
                          }
                        }
                      ]
                    }
                  }
                }
              }
            ]
          }
        }
      ]
    }
  }
}
"""


FLEX_ALGO_ROUTE_SAMPLE = """
{
  "data": {
    "openconfig-network-instance:network-instances": {
      "network-instance": [
        {
          "name": "default",
          "protocols": {
            "protocol": [
              {
                "identifier": "openconfig-policy-types:ISIS",
                "name": "default",
                "isis": {
                  "global": {
                    "afi-safi": {
                      "af": [
                        {
                          "afi-name": "openconfig-isis-types:IPV6",
                          "safi-name": "openconfig-isis-types:UNICAST",
                          "arcos-openconfig-isis-augments:flexible-algorithms": {
                            "flexible-algorithm": [
                              {
                                "id": 128,
                                "routes": {
                                  "route": [
                                    {
                                      "prefix": "2001:db8:fa::1/128",
                                      "state": {
                                        "best-level-number": 2
                                      },
                                      "levels": {
                                        "level": [
                                          {
                                            "level-number": 2,
                                            "state": {
                                              "metric": 15,
                                              "flags": [
                                                "arcos-openconfig-isis-augments:best"
                                              ],
                                              "next-hop-id": "2147483650",
                                              "prefix-origin-count": 1,
                                              "route-tag": 0,
                                              "last-updated-time": "2025-11-21T08:10:49.811578+00:00"
                                            },
                                            "next-hops": {
                                              "next-hop": [
                                                {
                                                  "outgoing-interface": "swp2",
                                                  "next-hop-address": "fe80::2",
                                                  "state": {
                                                    "tunnel-id": 1,
                                                    "backup": false
                                                  }
                                                }
                                              ]
                                            }
                                          }
                                        ]
                                      }
                                    }
                                  ]
                                }
                              }
                            ]
                          }
                        }
                      ]
                    }
                  }
                }
              }
            ]
          }
        }
      ]
    }
  }
}
"""


def test_show_isis_adjacency_sample():
    """Validate parsing of a basic ISIS adjacency sample."""

    sample_file = SAMPLES_DIR / "isis_adjacency.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisAdjacency(device="dummy")
    result = parser.cli(adj_router=None, output=output)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    neighbors = result["isis"]["default"].get("neighbors", {})
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
    result = parser.cli(instance=None, output=output)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    cfg = result["isis"]["default"].get("config", {})

    # Global settings
    glb = cfg.get("global", {})
    assert glb.get("net") == ["49.0001.1111.1111.1111.00"]
    assert glb.get("level_capability") == "LEVEL_2"

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

    # Interfaces
    interfaces = cfg.get("interfaces", {})
    assert "swp1" in interfaces and "loopback0" in interfaces

    swp1 = interfaces["swp1"]
    assert swp1["interface_id"] == "swp1"
    assert swp1["enabled"] is True
    assert swp1.get("network_type") == "POINT_TO_POINT"

    swp1_afs = swp1.get("afi_safi", {})
    assert "IPV6-UNICAST" in swp1_afs and "IPV4-UNICAST" in swp1_afs

    swp1_lvls = swp1.get("levels", {})
    assert "2" in swp1_lvls
    assert swp1_lvls["2"]["enabled"] is True


def test_show_isis_lsp_sample():
    """Validate parsing of an ISIS LSP database sample."""

    sample_file = SAMPLES_DIR / "isis_lsp.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(lsp_id=None, output=output)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    database = result["isis"]["default"].get("database", {})
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
    assert "isis" in result and "default" in result["isis"]

    interfaces = result["isis"]["default"].get("interfaces", {})
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
    assert "isis" in result and "default" in result["isis"]

    routes_afs = result["isis"]["default"].get("routes", {})
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
    assert "isis" in result and "default" in result["isis"]

    redist_afs = result["isis"]["default"].get("redistribute_routes", {})
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

    parser = ShowIsisFastReroute(device="dummy")
    result = parser.cli(prefix=None, output=FAST_REROUTE_SAMPLE)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    frr = result["isis"]["default"].get("fast_reroute", {})
    assert "IPV6-UNICAST" in frr

    af = frr["IPV6-UNICAST"]
    assert af["afi_name"] == "IPV6"
    assert af["safi_name"] == "UNICAST"

    prefixes = af["prefixes"]
    assert "2001:db8::/64" in prefixes
    pfx = prefixes["2001:db8::/64"]
    lvl2 = pfx["levels"]["2"]
    assert lvl2["metric"] == 10
    assert lvl2["nexthop_interface"] == "swp1"
    assert lvl2["nexthop_address"] == "fe80::1"
    assert lvl2["origin_system_id"] == "0000.0000.0001"


def test_show_isis_flex_algo_fast_reroute_minimal():
    """Validate parsing of a minimal ISIS flex-algo fast-reroute sample."""

    parser = ShowIsisFlexAlgoFastReroute(device="dummy")
    result = parser.cli(prefix=None, output=FLEX_ALGO_FAST_REROUTE_SAMPLE)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    flex = result["isis"]["default"].get("flex_algo_fast_reroute", {})
    assert "IPV6-UNICAST" in flex

    af = flex["IPV6-UNICAST"]
    algos = af["algorithms"]
    assert "128" in algos

    algo = algos["128"]
    assert algo["id"] == 128
    prefixes = algo["prefixes"]
    assert "2001:db8:fa::/64" in prefixes
    pfx = prefixes["2001:db8:fa::/64"]
    lvl2 = pfx["levels"]["2"]
    assert lvl2["metric"] == 20
    assert lvl2["nexthop_interface"] == "swp2"
    assert lvl2["nexthop_address"] == "fe80::2"


def test_show_isis_flex_algo_route_minimal():
    """Validate parsing of a minimal ISIS flex-algo route sample."""

    parser = ShowIsisFlexAlgoRoute(device="dummy")
    result = parser.cli(prefix=None, output=FLEX_ALGO_ROUTE_SAMPLE)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    flex = result["isis"]["default"].get("flex_algo_routes", {})
    assert "IPV6-UNICAST" in flex

    af = flex["IPV6-UNICAST"]
    algos = af["algorithms"]
    assert "128" in algos

    algo = algos["128"]
    assert algo["id"] == 128
    routes = algo["routes"]
    assert "2001:db8:fa::1/128" in routes
    r = routes["2001:db8:fa::1/128"]
    assert r["best_level_number"] == 2
    lvl2 = r["levels"]["2"]
    assert lvl2["metric"] == 15
    assert "best" in lvl2["flags"]
