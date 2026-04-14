"""Unit tests for 8 previously-untested ArcOS parsers.

Tested parsers:
1. ShowBgpLabelDb          (show_bgp.py)
2. ShowBgpVpnExportedRoutes (show_bgp_l3vpn.py)
3. ShowBridgeIsolation      (show_bridge_isolation.py)
4. ShowEvpnEsiInfo          (show_evpn_mpls.py)
5. ShowL2ribMacEntries      (show_evpn_mpls.py)
6. ShowL2ribVpwsEviEntries  (show_evpn_vpws.py)
7. ShowLldpInterface        (show_lldp.py)
8. ShowNtp                  (show_ntp.py)
"""

import json

import pytest

from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.show_bgp import ShowBgpLabelDb
from genie.libs.parser.arcos.show_bgp_l3vpn import ShowBgpVpnExportedRoutes
from genie.libs.parser.arcos.show_bridge_isolation import ShowBridgeIsolation
from genie.libs.parser.arcos.show_evpn_mpls import ShowEvpnEsiInfo, ShowL2ribMacEntries
from genie.libs.parser.arcos.show_evpn_vpws import ShowL2ribVpwsEviEntries
from genie.libs.parser.arcos.show_lldp import ShowLldpInterface
from genie.libs.parser.arcos.show_ntp import ShowNtp


# =====================================================================
# 1. ShowBgpLabelDb
# =====================================================================
# JSON path: data -> openconfig-network-instance:network-instances
#   -> network-instance[0] -> protocols -> protocol[0](BGP) -> bgp
#   -> global -> arcos-openconfig-bgp-augments:mpls -> label-db
#   -> label-entry[]

_BGP_LABEL_DB_JSON = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "protocols": {
                        "protocol": [
                            {
                                "identifier": "openconfig-policy-types:BGP",
                                "name": "default",
                                "bgp": {
                                    "global": {
                                        "arcos-openconfig-bgp-augments:mpls": {
                                            "label-db": {
                                                "label-entry": [
                                                    {
                                                        "label": 100001,
                                                        "state": {
                                                            "label": 100001,
                                                            "prefix": "10.0.0.0/24",
                                                            "afi-safi-name": "L3VPN_IPV4_UNICAST",
                                                            "neighbor": "10.1.1.1",
                                                        },
                                                    },
                                                    {
                                                        "label": 100002,
                                                        "state": {
                                                            "label": 100002,
                                                            "prefix": "10.0.1.0/24",
                                                        },
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                },
                            }
                        ],
                    },
                }
            ],
        },
    },
})


class TestShowBgpLabelDb:
    def test_basic(self):
        parser = ShowBgpLabelDb(device="dummy")
        result = parser.cli(output=_BGP_LABEL_DB_JSON)

        assert isinstance(result, dict)
        labels = result["labels"]
        assert "100001" in labels
        assert labels["100001"]["label"] == 100001
        assert labels["100001"]["prefix"] == "10.0.0.0/24"
        assert labels["100001"]["neighbor"] == "10.1.1.1"
        assert "100002" in labels
        assert labels["100002"]["label"] == 100002
        assert labels["100002"]["prefix"] == "10.0.1.0/24"

    def test_empty(self):
        parser = ShowBgpLabelDb(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 2. ShowBgpVpnExportedRoutes
# =====================================================================
# JSON path: data -> openconfig-network-instance:network-instances
#   -> network-instance[] -> protocols -> protocol[](BGP) -> bgp
#   -> rib -> afi-safis -> afi-safi[] -> network-instances
#   -> network-instance[] -> exported-rib -> route[]

_BGP_VPN_EXPORTED_JSON = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "protocols": {
                        "protocol": [
                            {
                                "identifier": "openconfig-policy-types:BGP",
                                "name": "default",
                                "bgp": {
                                    "rib": {
                                        "afi-safis": {
                                            "afi-safi": [
                                                {
                                                    "afi-safi-name": "L3VPN_IPV4_UNICAST",
                                                    "network-instances": {
                                                        "network-instance": [
                                                            {
                                                                "name": "VRF-A",
                                                                "exported-rib": {
                                                                    "route": [
                                                                        {
                                                                            "prefix": "192.168.1.0/24",
                                                                            "state": {
                                                                                "prefix": "192.168.1.0/24",
                                                                                "path-id": 0,
                                                                                "next-hop": "10.0.0.1",
                                                                                "local-label": 24001,
                                                                                "remote-label": 24002,
                                                                                "path-types": "BEST",
                                                                            },
                                                                        },
                                                                    ],
                                                                },
                                                            }
                                                        ],
                                                    },
                                                }
                                            ],
                                        },
                                    },
                                },
                            }
                        ],
                    },
                }
            ],
        },
    },
})


class TestShowBgpVpnExportedRoutes:
    def test_basic(self):
        parser = ShowBgpVpnExportedRoutes(device="dummy")
        result = parser.cli(output=_BGP_VPN_EXPORTED_JSON)

        assert isinstance(result, dict)
        routes = result["routes"]
        assert "VRF-A:192.168.1.0/24" in routes
        entry = routes["VRF-A:192.168.1.0/24"]
        assert entry["prefix"] == "192.168.1.0/24"
        assert entry["network-instance"] == "VRF-A"
        assert entry["path-id"] == 0
        assert entry["next-hop"] == "10.0.0.1"
        assert entry["local-label"] == 24001
        assert entry["remote-label"] == 24002

    def test_empty(self):
        parser = ShowBgpVpnExportedRoutes(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 3. ShowBridgeIsolation
# =====================================================================
# JSON path: data -> openconfig-interfaces:interfaces -> interface[0]
#   -> arcos-bridge-isolation:bridge-isolation -> state

_BRIDGE_ISOLATION_JSON = json.dumps({
    "data": {
        "openconfig-interfaces:interfaces": {
            "interface": [
                {
                    "name": "ethernet-1/1",
                    "arcos-bridge-isolation:bridge-isolation": {
                        "state": {
                            "isolation": "enable",
                            "isolation-drop-packets": 42,
                            "isolation-drop-octets": 5600,
                        },
                    },
                }
            ],
        },
    },
})


class TestShowBridgeIsolation:
    def test_basic(self):
        parser = ShowBridgeIsolation(device="dummy")
        result = parser.cli(output=_BRIDGE_ISOLATION_JSON)

        assert isinstance(result, dict)
        assert result["isolation-enabled"] is True
        assert result["isolation-drop-packets"] == 42
        assert result["isolation-drop-octets"] == 5600

    def test_empty(self):
        parser = ShowBridgeIsolation(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 4. ShowEvpnEsiInfo
# =====================================================================
# JSON path: data -> arcos-evpn:evpn -> esi-info -> esi[]

_EVPN_ESI_JSON = json.dumps({
    "data": {
        "arcos-evpn:evpn": {
            "esi-info": {
                "esi": [
                    {
                        "esi": "00:11:22:33:44:55:66:77:88:99",
                        "state": {
                            "esi": "00:11:22:33:44:55:66:77:88:99",
                            "designated-forwarder": True,
                            "local": True,
                            "interface": "ethernet-1/1",
                        },
                    },
                    {
                        "esi": "00:AA:BB:CC:DD:EE:FF:00:11:22",
                        "state": {
                            "esi": "00:AA:BB:CC:DD:EE:FF:00:11:22",
                            "designated-forwarder": False,
                            "local": False,
                        },
                    },
                ],
            },
        },
    },
})


class TestShowEvpnEsiInfo:
    def test_basic(self):
        parser = ShowEvpnEsiInfo(device="dummy")
        result = parser.cli(output=_EVPN_ESI_JSON)

        assert isinstance(result, dict)
        entries = result["esi-entries"]
        assert "00:11:22:33:44:55:66:77:88:99" in entries
        e1 = entries["00:11:22:33:44:55:66:77:88:99"]
        assert e1["designated-forwarder"] is True
        assert e1["local"] is True
        assert e1["interface"] == "ethernet-1/1"

        assert "00:AA:BB:CC:DD:EE:FF:00:11:22" in entries
        e2 = entries["00:AA:BB:CC:DD:EE:FF:00:11:22"]
        assert e2["designated-forwarder"] is False

    def test_empty(self):
        parser = ShowEvpnEsiInfo(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 5. ShowL2ribMacEntries
# =====================================================================
# JSON path: data -> openconfig-network-instance:network-instances
#   -> network-instance[] -> arcos-l2rib:l2rib -> mac-entries
#   -> mac-entry[]

_L2RIB_MAC_JSON = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "arcos-l2rib:l2rib": {
                        "mac-entries": {
                            "mac-entry": [
                                {
                                    "mac-address": "00:11:22:33:44:55",
                                    "state": {
                                        "mac-address": "00:11:22:33:44:55",
                                        "origin": "local",
                                        "esi": "00:11:22:33:44:55:66:77:88:99",
                                        "next-hop": "10.0.0.1",
                                        "label": 5000,
                                    },
                                },
                                {
                                    "mac-address": "AA:BB:CC:DD:EE:FF",
                                    "state": {
                                        "mac-address": "AA:BB:CC:DD:EE:FF",
                                        "origin": "remote",
                                        "next-hop": "10.0.0.2",
                                    },
                                },
                            ],
                        },
                    },
                }
            ],
        },
    },
})


class TestShowL2ribMacEntries:
    def test_basic(self):
        parser = ShowL2ribMacEntries(device="dummy")
        result = parser.cli(output=_L2RIB_MAC_JSON)

        assert isinstance(result, dict)
        entries = result["mac-entries"]
        assert "00:11:22:33:44:55" in entries
        e1 = entries["00:11:22:33:44:55"]
        assert e1["mac-address"] == "00:11:22:33:44:55"
        assert e1["origin"] == "local"
        assert e1["esi"] == "00:11:22:33:44:55:66:77:88:99"
        assert e1["next-hop"] == "10.0.0.1"
        assert e1["label"] == 5000

        assert "AA:BB:CC:DD:EE:FF" in entries
        e2 = entries["AA:BB:CC:DD:EE:FF"]
        assert e2["origin"] == "remote"

    def test_empty(self):
        parser = ShowL2ribMacEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 6. ShowL2ribVpwsEviEntries
# =====================================================================
# JSON path: data -> openconfig-network-instance:network-instances
#   -> network-instance[] -> arcos-l2rib:l2rib -> vpws-evi-entries
#   -> vpws-evi-entry[]

_L2RIB_VPWS_EVI_JSON = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "vpws-100",
                    "arcos-l2rib:l2rib": {
                        "vpws-evi-entries": {
                            "vpws-evi-entry": [
                                {
                                    "state": {
                                        "evi": 100,
                                        "ingress-label": 50001,
                                        "esi": "00:11:22:33:44:55:66:77:88:99",
                                        "control-word": True,
                                    },
                                },
                                {
                                    "state": {
                                        "evi": 200,
                                        "ingress-label": 50002,
                                        "control-word": False,
                                    },
                                },
                            ],
                        },
                    },
                }
            ],
        },
    },
})


class TestShowL2ribVpwsEviEntries:
    def test_basic(self):
        parser = ShowL2ribVpwsEviEntries(device="dummy")
        result = parser.cli(output=_L2RIB_VPWS_EVI_JSON)

        assert isinstance(result, dict)
        entries = result["vpws-evi-entries"]
        assert "vpws-100:100" in entries
        e1 = entries["vpws-100:100"]
        assert e1["evi"] == 100
        assert e1["ingress-label"] == 50001
        assert e1["esi"] == "00:11:22:33:44:55:66:77:88:99"
        assert e1["control-word"] is True

        assert "vpws-100:200" in entries
        e2 = entries["vpws-100:200"]
        assert e2["evi"] == 200
        assert e2["control-word"] is False

    def test_empty(self):
        parser = ShowL2ribVpwsEviEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 7. ShowLldpInterface
# =====================================================================
# JSON path: data -> openconfig-lldp:lldp -> interfaces -> interface[]
#   Each interface has: name, state{enabled, mode, counters{}},
#   neighbors -> neighbor[] -> {id, state{...}, capabilities{capability[]}}

_LLDP_INTERFACE_JSON = json.dumps({
    "data": {
        "openconfig-lldp:lldp": {
            "interfaces": {
                "interface": [
                    {
                        "name": "ethernet-1/1",
                        "state": {
                            "enabled": True,
                            "mode": "BOTH",
                            "counters": {
                                "frame-in": "1000",
                                "frame-out": "950",
                                "frame-error-in": "0",
                            },
                        },
                        "neighbors": {
                            "neighbor": [
                                {
                                    "id": "nbr1",
                                    "state": {
                                        "system-name": "switch-01",
                                        "system-description": "ArcOS switch",
                                        "chassis-id": "00:11:22:33:44:55",
                                        "chassis-id-type": "MAC_ADDRESS",
                                        "port-id": "ethernet-1/2",
                                        "port-id-type": "INTERFACE_NAME",
                                        "management-address": "10.0.0.1",
                                        "management-address-type": "IPv4",
                                        "arcos-openconfig-lldp-augments:management-address": "fd00::1",
                                        "arcos-openconfig-lldp-augments:management-address-type": "IPv6",
                                    },
                                    "capabilities": {
                                        "capability": [
                                            {
                                                "name": "openconfig-lldp-types:ROUTER",
                                                "state": {
                                                    "enabled": True,
                                                },
                                            },
                                            {
                                                "name": "openconfig-lldp-types:BRIDGE",
                                                "state": {
                                                    "enabled": False,
                                                },
                                            },
                                        ],
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        },
    },
})


class TestShowLldpInterface:
    def test_basic(self):
        parser = ShowLldpInterface(device="dummy")
        result = parser.cli(output=_LLDP_INTERFACE_JSON)

        assert isinstance(result, dict)
        interfaces = result["interfaces"]
        assert "ethernet-1/1" in interfaces
        intf = interfaces["ethernet-1/1"]
        assert intf["name"] == "ethernet-1/1"
        assert intf["enabled"] is True
        assert intf["mode"] == "BOTH"

        # Counters
        assert intf["counters"]["frame-in"] == "1000"
        assert intf["counters"]["frame-out"] == "950"

        # Neighbor
        assert "nbr1" in intf["neighbors"]
        nbr = intf["neighbors"]["nbr1"]
        assert nbr["id"] == "nbr1"
        assert nbr["system-name"] == "switch-01"
        assert nbr["chassis-id"] == "00:11:22:33:44:55"
        assert nbr["port-id"] == "ethernet-1/2"
        assert nbr["management-address"] == "10.0.0.1"
        assert nbr["management-address-ipv6"] == "fd00::1"
        assert nbr["management-address-ipv6-type"] == "IPv6"

        # Capabilities
        assert "ROUTER" in nbr["capabilities"]
        assert nbr["capabilities"]["ROUTER"]["enabled"] is True
        assert "BRIDGE" in nbr["capabilities"]
        assert nbr["capabilities"]["BRIDGE"]["enabled"] is False

    def test_empty(self):
        parser = ShowLldpInterface(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# =====================================================================
# 8. ShowNtp
# =====================================================================
# JSON path: data -> openconfig-system:system -> ntp
#   -> state -> arcos-openconfig-system-augments:network-instance
#   -> arcos-openconfig-system-augments:status[] (address, stratum, etc.)

_NTP_JSON = json.dumps({
    "data": {
        "openconfig-system:system": {
            "ntp": {
                "state": {
                    "arcos-openconfig-system-augments:network-instance": "default",
                },
                "arcos-openconfig-system-augments:status": [
                    {
                        "address": "66.118.228.14",
                        "stratum": 2,
                        "root-delay": 12,
                        "root-dispersion": "22",
                        "offset": "150",
                        "poll-interval": 64,
                        "reach": 377,
                        "time-since-last-response": "44",
                        "association-status": "COMBINED",
                    },
                    {
                        "address": "216.229.0.49",
                        "stratum": 2,
                        "root-delay": 22,
                        "root-dispersion": "11",
                        "offset": "141",
                        "poll-interval": 64,
                        "reach": 377,
                        "time-since-last-response": "40",
                        "association-status": "SYNC_SOURCE",
                    },
                ],
            },
        },
    },
})


class TestShowNtp:
    def test_basic(self):
        parser = ShowNtp(device="dummy")
        result = parser.cli(output=_NTP_JSON)

        assert isinstance(result, dict)
        assert result["network-instance"] == "default"
        assert "associations" in result
        assoc = result["associations"]
        assert "66.118.228.14" in assoc
        a1 = assoc["66.118.228.14"]
        assert a1["address"] == "66.118.228.14"
        assert a1["stratum"] == 2
        assert a1["root-delay"] == 12
        assert a1["poll-interval"] == 64
        assert a1["reach"] == 377
        assert a1["association-status"] == "COMBINED"

        assert "216.229.0.49" in assoc
        a2 = assoc["216.229.0.49"]
        assert a2["association-status"] == "SYNC_SOURCE"

    def test_empty(self):
        parser = ShowNtp(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')
