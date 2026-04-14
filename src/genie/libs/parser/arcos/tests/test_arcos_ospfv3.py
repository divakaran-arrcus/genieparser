"""Unit tests for ArcOS OSPFv3 parsers using synthetic data."""

import json

import pytest

from pathlib import Path

from genie.libs.parser.arcos.show_ospfv3 import (
    ShowOspfv3Global,
    ShowOspfv3Neighbor,
    ShowOspfv3RunningConfig,
)

SAMPLES_DIR = Path(__file__).parent / "test_samples"
from genie.metaparser.util.exceptions import SchemaEmptyParserError


# Synthetic OSPFv3 global state JSON matching the parser navigation path.
# Structure: data -> openconfig-network-instance:network-instances ->
#   network-instance[] -> protocols -> protocol[] -> arcos-ospf:ospfv3 ->
#   global -> state
OSPFV3_GLOBAL_JSON = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "protocols": {
                        "protocol": [
                            {
                                "identifier": "openconfig-policy-types:OSPF3",
                                "name": "default",
                                "arcos-ospf:ospfv3": {
                                    "global": {
                                        "state": {
                                            "router-id": "3.3.3.3",
                                            "log-adjacency-changes": "LOG_ADJ_ENABLE_DETAIL",
                                            "max-ecmp-paths": 64,
                                            "abr-router": False,
                                            "asbr-router": True,
                                            "area-count": 1,
                                            "neighbor-count": 3,
                                            "full-neighbor-count": 3,
                                            "up-interface-count": 2,
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
})

# Synthetic OSPFv3 neighbor JSON.
OSPFV3_NEIGHBOR_JSON = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "protocols": {
                        "protocol": [
                            {
                                "identifier": "openconfig-policy-types:OSPF3",
                                "name": "default",
                                "arcos-ospf:ospfv3": {
                                    "areas": {
                                        "area": [
                                            {
                                                "identifier": 0,
                                                "interfaces": {
                                                    "interface": [
                                                        {
                                                            "id": "swp1",
                                                            "neighbors": {
                                                                "neighbor": [
                                                                    {
                                                                        "neighbor-router-id": "1.1.1.1",
                                                                        "state": {
                                                                            "neighbor-ip-address": "fe80::1",
                                                                            "adjacency-state": "arcos-ospf-types:NEIGHBOR_FULL",
                                                                            "priority": 1,
                                                                        }
                                                                    }
                                                                ]
                                                            }
                                                        },
                                                        {
                                                            "id": "swp2",
                                                            "neighbors": {
                                                                "neighbor": [
                                                                    {
                                                                        "neighbor-router-id": "4.4.4.4",
                                                                        "state": {
                                                                            "neighbor-ip-address": "fe80::4",
                                                                            "adjacency-state": "NEIGHBOR_2WAY",
                                                                            "priority": 0,
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
                        ]
                    }
                }
            ]
        }
    }
})


def test_show_ospfv3_global_basic():
    """Validate OSPFv3 global state is parsed from synthetic data."""
    parser = ShowOspfv3Global(device="dummy")
    result = parser.cli(output=OSPFV3_GLOBAL_JSON)

    assert isinstance(result, dict)
    assert result["router-id"] == "3.3.3.3"
    assert result["log-adjacency-changes"] == "LOG_ADJ_ENABLE_DETAIL"
    assert result["max-ecmp-paths"] == 64
    assert result["abr-router"] is False
    assert result["asbr-router"] is True
    assert result["area-count"] == 1
    assert result["neighbor-count"] == 3
    assert result["full-neighbor-count"] == 3
    assert result["up-interface-count"] == 2


def test_show_ospfv3_global_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfv3Global(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


def test_show_ospfv3_neighbor_basic():
    """Validate OSPFv3 neighbor parsing from synthetic data."""
    parser = ShowOspfv3Neighbor(device="dummy")
    result = parser.cli(output=OSPFV3_NEIGHBOR_JSON)

    assert "neighbors" in result
    neighbors = result["neighbors"]
    assert len(neighbors) == 2

    # Check first neighbor key format: "area:interface:router-id"
    key1 = "0:swp1:1.1.1.1"
    assert key1 in neighbors
    nbr1 = neighbors[key1]
    assert nbr1["area"] == 0
    assert nbr1["interface"] == "swp1"
    assert nbr1["neighbor-router-id"] == "1.1.1.1"
    assert nbr1["neighbor-ip-address"] == "fe80::1"
    # Namespace prefix should be stripped
    assert nbr1["adjacency-state"] == "NEIGHBOR_FULL"
    assert nbr1["priority"] == 1

    # Check second neighbor
    key2 = "0:swp2:4.4.4.4"
    assert key2 in neighbors
    nbr2 = neighbors[key2]
    assert nbr2["neighbor-router-id"] == "4.4.4.4"
    assert nbr2["neighbor-ip-address"] == "fe80::4"
    # No namespace prefix to strip in this value
    assert nbr2["adjacency-state"] == "NEIGHBOR_2WAY"
    assert nbr2["priority"] == 0


def test_show_ospfv3_neighbor_empty():
    """Empty areas should raise SchemaEmptyParserError."""
    parser = ShowOspfv3Neighbor(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')


# =====================================================================
# ShowOspfv3RunningConfig tests
# =====================================================================

def test_show_ospfv3_running_config_basic():
    """Validate OSPFv3 running config from rtr2."""
    sample_file = SAMPLES_DIR / "ospfv3_running_config.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowOspfv3RunningConfig(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)

    # Global
    assert result["global"]["router-id"] == "2.2.2.2"

    # Areas
    areas = result["areas"]
    assert "0" in areas

    intfs = areas["0"]["interfaces"]
    assert "loopback0" in intfs
    assert "swp1" in intfs

    swp1 = intfs["swp1"]
    assert swp1["network-type"] == "POINT_TO_POINT_NETWORK"
    assert swp1["hello-interval"] == 10
    assert swp1["dead-interval"] == 40


def test_show_ospfv3_running_config_empty():
    """Empty data should raise SchemaEmptyParserError."""
    parser = ShowOspfv3RunningConfig(device="dummy")
    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output='{"data": {}}')
