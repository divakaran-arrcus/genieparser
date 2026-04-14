"""Unit tests for 7 remaining ArcOS parsers (group B).

Parsers covered:
    ShowTelemetry             (show_telemetry.py)
    ShowGnmiServer            (show_gnmi.py)
    ShowSlaIcmp               (show_sla.py)
    ShowBgpDeaggregationLabel (show_bgp_l3vpn.py)
    ShowEvpnState             (show_evpn_mpls.py)
    ShowEvpnVpws              (show_evpn_vpws.py)
    ShowSrmsMappingsConfig    (show_segment_routing.py)
"""

import json
from unittest import TestCase
from unittest.mock import Mock

from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.show_telemetry import ShowTelemetry
from genie.libs.parser.arcos.show_gnmi import ShowGnmiServer
from genie.libs.parser.arcos.show_sla import ShowSlaIcmp
from genie.libs.parser.arcos.show_bgp_l3vpn import ShowBgpDeaggregationLabel
from genie.libs.parser.arcos.show_evpn_mpls import ShowEvpnState
from genie.libs.parser.arcos.show_evpn_vpws import ShowEvpnVpws
from genie.libs.parser.arcos.show_segment_routing import ShowSrmsMappingsConfig


# ============================================================================
# Sample JSON outputs
# ============================================================================

SHOW_TELEMETRY_OUTPUT = json.dumps({
    "data": {
        "arcos-telemetry:telemetry-system": {
            "global": {
                "state": {
                    "status": "ENABLED",
                    "cuid": "arcos-device-001"
                }
            },
            "destination-group": [
                {
                    "group-id": "dg-1",
                    "destination": [
                        {
                            "address": "10.0.0.100",
                            "port": 50051
                        }
                    ]
                }
            ],
            "persistent-subscription": [
                {
                    "subscription-name": "sub-interfaces",
                    "state": {
                        "sensors": ["/interfaces/interface/state"],
                        "destination-group": "dg-1"
                    }
                }
            ]
        }
    }
})

SHOW_GNMI_SERVER_OUTPUT = json.dumps({
    "data": {
        "openconfig-system:system": {
            "arcos-grpc-server:grpc-server": {
                "state": {
                    "enable": True,
                    "transport-security": True,
                    "port": 6030,
                    "listen-addresses": ["0.0.0.0"]
                },
                "clients": {
                    "client": [
                        {"address": "10.0.0.50"},
                        {"address": "10.0.0.51"}
                    ]
                }
            }
        }
    }
})

SHOW_SLA_ICMP_OUTPUT = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "arcos-sla:sla": {
                        "icmp": {
                            "state": {
                                "admin-state": True
                            },
                            "icmp-session": [
                                {
                                    "session-name": "probe-to-peer",
                                    "state": {
                                        "admin-state": True,
                                        "target-address": "10.1.1.2",
                                        "source-address": "10.1.1.1",
                                        "session-interval": 60
                                    },
                                    "probe": {
                                        "state": {
                                            "probe-count": 5,
                                            "probe-interval": 1000,
                                            "payload-size": 64
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            ]
        }
    }
})

SHOW_BGP_DEAGG_LABEL_OUTPUT = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "vrf-cust1",
                    "protocols": {
                        "protocol": [
                            {
                                "identifier": "openconfig-policy-types:BGP",
                                "bgp": {
                                    "global": {
                                        "afi-safis": {
                                            "afi-safi": [
                                                {
                                                    "afi-safi-name": "openconfig-bgp-types:L3VPN_IPV4_UNICAST",
                                                    "state": {
                                                        "deaggregation-label": 100001
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
})

SHOW_EVPN_STATE_OUTPUT = json.dumps({
    "data": {
        "arcos-evpn:evpn": {
            "state": {
                "router-ip-selected": "10.0.0.1"
            }
        }
    }
})

SHOW_EVPN_VPWS_OUTPUT = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "protocols": {
                        "protocol": [
                            {
                                "identifier": "openconfig-policy-types:BGP",
                                "bgp": {
                                    "global": {
                                        "afi-safis": {
                                            "afi-safi": [
                                                {
                                                    "afi-safi-name": "L2VPN_EVPN",
                                                    "vpws": {
                                                        "service": [
                                                            {
                                                                "state": {
                                                                    "network-instance": "vpws-svc-1",
                                                                    "evi": 100,
                                                                    "local-service-id": 1,
                                                                    "remote-service-id": 2,
                                                                    "control-word": True,
                                                                    "link-loss-forwarding": False,
                                                                    "oper-status": "UP"
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
})

SHOW_SRMS_MAPPINGS_CONFIG_OUTPUT = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "segment-routing": {
                        "arcos-openconfig-segment-routing-augments:srms": {
                            "mappings": {
                                "mapping": [
                                    {
                                        "local-id": "map-1",
                                        "ipv4": {
                                            "prefixes": {
                                                "prefix": [
                                                    {
                                                        "ipv4-prefix": "10.0.0.0/24",
                                                        "config": {
                                                            "sid": 16000,
                                                            "range": 100
                                                        }
                                                    }
                                                ]
                                            }
                                        },
                                        "ipv6": {
                                            "prefixes": {
                                                "prefix": [
                                                    {
                                                        "ipv6-prefix": "2001:db8::/32",
                                                        "config": {
                                                            "sid": 17000,
                                                            "range": 50
                                                        }
                                                    }
                                                ]
                                            }
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
})


# ============================================================================
# Tests: ShowTelemetry
# ============================================================================

class TestShowTelemetry(TestCase):
    """Unit tests for ShowTelemetry parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic telemetry parsing with global state, destinations, subscriptions."""
        parser = ShowTelemetry(device=self.device)
        result = parser.cli(output=SHOW_TELEMETRY_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "ENABLED")
        self.assertEqual(result["cuid"], "arcos-device-001")

        # Destination groups
        self.assertIn("destination-groups", result)
        self.assertIn("dg-1", result["destination-groups"])
        dg = result["destination-groups"]["dg-1"]
        self.assertEqual(dg["name"], "dg-1")
        self.assertIn("destinations", dg)
        self.assertEqual(dg["destinations"], ["10.0.0.100:50051"])

        # Subscriptions
        self.assertIn("subscriptions", result)
        self.assertIn("sub-interfaces", result["subscriptions"])
        sub = result["subscriptions"]["sub-interfaces"]
        self.assertEqual(sub["name"], "sub-interfaces")
        self.assertEqual(sub["sensors"], ["/interfaces/interface/state"])
        self.assertEqual(sub["destination-group"], "dg-1")

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowTelemetry(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# ============================================================================
# Tests: ShowGnmiServer
# ============================================================================

class TestShowGnmiServer(TestCase):
    """Unit tests for ShowGnmiServer parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic gNMI server state parsing."""
        parser = ShowGnmiServer(device=self.device)
        result = parser.cli(output=SHOW_GNMI_SERVER_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["enabled"], True)
        self.assertEqual(result["transport-security"], True)
        self.assertEqual(result["port"], 6030)
        self.assertEqual(result["listen-addresses"], ["0.0.0.0"])
        self.assertEqual(result["clients-connected"], 2)

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowGnmiServer(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# ============================================================================
# Tests: ShowSlaIcmp
# ============================================================================

class TestShowSlaIcmp(TestCase):
    """Unit tests for ShowSlaIcmp parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic SLA ICMP parsing with admin state, sessions, and probes."""
        parser = ShowSlaIcmp(device=self.device)
        result = parser.cli(output=SHOW_SLA_ICMP_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["admin-state"], True)

        # Sessions
        self.assertIn("sessions", result)
        self.assertIn("probe-to-peer", result["sessions"])
        sess = result["sessions"]["probe-to-peer"]
        self.assertEqual(sess["name"], "probe-to-peer")
        self.assertEqual(sess["admin-state"], True)
        self.assertEqual(sess["target-address"], "10.1.1.2")
        self.assertEqual(sess["source-address"], "10.1.1.1")
        self.assertEqual(sess["session-interval"], 60)
        self.assertEqual(sess["probe-count"], 5)
        self.assertEqual(sess["probe-interval"], 1000)
        self.assertEqual(sess["payload-size"], 64)

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowSlaIcmp(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# ============================================================================
# Tests: ShowBgpDeaggregationLabel
# ============================================================================

class TestShowBgpDeaggregationLabel(TestCase):
    """Unit tests for ShowBgpDeaggregationLabel parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic BGP deaggregation label parsing."""
        parser = ShowBgpDeaggregationLabel(device=self.device)
        result = parser.cli(output=SHOW_BGP_DEAGG_LABEL_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertIn("entries", result)

        # Key is "vrf-cust1:L3VPN_IPV4_UNICAST" after prefix stripping
        key = "vrf-cust1:L3VPN_IPV4_UNICAST"
        self.assertIn(key, result["entries"])
        entry = result["entries"][key]
        self.assertEqual(entry["network-instance"], "vrf-cust1")
        self.assertEqual(entry["afi-safi"], "L3VPN_IPV4_UNICAST")
        self.assertEqual(entry["deaggregation-label"], 100001)

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowBgpDeaggregationLabel(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# ============================================================================
# Tests: ShowEvpnState
# ============================================================================

class TestShowEvpnState(TestCase):
    """Unit tests for ShowEvpnState parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic EVPN state router-ip-selected parsing."""
        parser = ShowEvpnState(device=self.device)
        result = parser.cli(output=SHOW_EVPN_STATE_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["router-ip-selected"], "10.0.0.1")

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowEvpnState(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# ============================================================================
# Tests: ShowEvpnVpws
# ============================================================================

class TestShowEvpnVpws(TestCase):
    """Unit tests for ShowEvpnVpws parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic EVPN VPWS service parsing."""
        parser = ShowEvpnVpws(device=self.device)
        result = parser.cli(output=SHOW_EVPN_VPWS_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertIn("vpws-services", result)
        self.assertIn("vpws-svc-1", result["vpws-services"])

        svc = result["vpws-services"]["vpws-svc-1"]
        self.assertEqual(svc["network-instance"], "vpws-svc-1")
        self.assertEqual(svc["evi"], 100)
        self.assertEqual(svc["local-service-id"], 1)
        self.assertEqual(svc["remote-service-id"], 2)
        self.assertEqual(svc["control-word"], True)
        self.assertEqual(svc["link-loss-forwarding"], False)
        self.assertEqual(svc["oper-status"], "UP")

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowEvpnVpws(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output='{"data": {}}')


# ============================================================================
# Tests: ShowSrmsMappingsConfig
# ============================================================================

class TestShowSrmsMappingsConfig(TestCase):
    """Unit tests for ShowSrmsMappingsConfig parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic SRMS mappings config parsing with IPv4 and IPv6 prefixes."""
        parser = ShowSrmsMappingsConfig(device=self.device)
        result = parser.cli(output=SHOW_SRMS_MAPPINGS_CONFIG_OUTPUT)

        self.assertIsInstance(result, dict)
        self.assertIn("network-instances", result)
        self.assertIn("default", result["network-instances"])

        ni = result["network-instances"]["default"]
        self.assertIn("srms", ni)
        self.assertIn("mappings", ni["srms"])
        self.assertIn("map-1", ni["srms"]["mappings"])

        mapping = ni["srms"]["mappings"]["map-1"]
        self.assertEqual(mapping["local-id"], "map-1")

        # IPv4 prefixes
        self.assertIn("ipv4-prefixes", mapping)
        self.assertEqual(len(mapping["ipv4-prefixes"]), 1)
        ipv4 = mapping["ipv4-prefixes"][0]
        self.assertEqual(ipv4["prefix"], "10.0.0.0/24")
        self.assertEqual(ipv4["sid"], 16000)
        self.assertEqual(ipv4["range"], 100)

        # IPv6 prefixes
        self.assertIn("ipv6-prefixes", mapping)
        self.assertEqual(len(mapping["ipv6-prefixes"]), 1)
        ipv6 = mapping["ipv6-prefixes"][0]
        self.assertEqual(ipv6["prefix"], "2001:db8::/32")
        self.assertEqual(ipv6["sid"], 17000)
        self.assertEqual(ipv6["range"], 50)

    def test_empty_output(self):
        """Test empty output returns empty network-instances dict."""
        parser = ShowSrmsMappingsConfig(device=self.device)
        result = parser.cli(output='{"data": {}}')

        # ShowSrmsMappingsConfig returns empty dict rather than raising
        self.assertIsInstance(result, dict)
        self.assertIn("network-instances", result)
        self.assertEqual(result["network-instances"], {})
