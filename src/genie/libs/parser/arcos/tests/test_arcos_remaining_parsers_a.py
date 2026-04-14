"""Unit tests for remaining arcOS parsers (batch A).

Parsers covered:
    1. ShowNatInstance        (show_nat.py)
    2. ShowDhcpRelay          (show_dhcp_relay.py)
    3. ShowIpsecConnEntry     (show_ipsec.py)
    4. ShowIpfix              (show_ipfix.py)
    5. ShowPortSecurity       (show_port_security.py)
    6. ShowMonitorSession     (show_monitor_session.py)
    7. ShowQosPolicy          (show_qos.py)

Each parser has two tests:
    - test_basic: minimal synthetic JSON that exercises the main code paths
    - test_empty: empty/missing data triggers SchemaEmptyParserError
"""

import json
from unittest import TestCase

from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.show_nat import ShowNatInstance
from genie.libs.parser.arcos.show_dhcp_relay import ShowDhcpRelay
from genie.libs.parser.arcos.show_ipsec import ShowIpsecConnEntry
from genie.libs.parser.arcos.show_ipfix import ShowIpfix
from genie.libs.parser.arcos.show_port_security import ShowPortSecurity
from genie.libs.parser.arcos.show_monitor_session import ShowMonitorSession
from genie.libs.parser.arcos.show_qos import ShowQosPolicy


# ---------------------------------------------------------------------------
# 1. ShowNatInstance
# ---------------------------------------------------------------------------
class TestShowNatInstance(TestCase):

    def test_basic(self):
        """Parse a NAT instance with mapping entries and policies."""
        sample = json.dumps({
            "data": {
                "arcos-nat:nat": {
                    "instance": [
                        {
                            "id": 1,
                            "state": {
                                "name": "nat-pool-1",
                                "enable": True,
                                "type": "STATIC",
                            },
                            "mapping-entry": [
                                {
                                    "id": 10,
                                    "state": {
                                        "internal-src-address": "10.0.0.1",
                                        "total-packets": 500,
                                        "total-bytes": 64000,
                                    },
                                }
                            ],
                            "policy": [
                                {
                                    "id": 100,
                                    "state": {
                                        "external-interface": "ethernet-1/1",
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        })

        parser = ShowNatInstance(device="dummy")
        result = parser.cli(output=sample)

        self.assertIn("instances", result)
        inst = result["instances"]["1"]
        self.assertEqual(inst["id"], 1)
        self.assertEqual(inst["name"], "nat-pool-1")
        self.assertTrue(inst["enabled"])
        self.assertEqual(inst["type"], "STATIC")

        # Mapping entries
        self.assertIn("mapping-entries", inst)
        me = inst["mapping-entries"]["10"]
        self.assertEqual(me["id"], 10)
        self.assertEqual(me["internal-src-address"], "10.0.0.1")
        self.assertEqual(me["total-packets"], 500)
        self.assertEqual(me["total-bytes"], 64000)

        # Policies
        self.assertIn("policies", inst)
        pol = inst["policies"]["100"]
        self.assertEqual(pol["id"], 100)
        self.assertEqual(pol["external-interface"], "ethernet-1/1")

    def test_empty(self):
        """Empty NAT data raises SchemaEmptyParserError."""
        parser = ShowNatInstance(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))


# ---------------------------------------------------------------------------
# 2. ShowDhcpRelay
# ---------------------------------------------------------------------------
class TestShowDhcpRelay(TestCase):

    def test_basic(self):
        """Parse DHCP relay with helpers, counters, and interfaces."""
        sample = json.dumps({
            "data": {
                "arcos-dhcp-relay:relay-agent": {
                    "dhcp": {
                        "config": {
                            "helper-address": ["10.1.1.1", "10.1.1.2"],
                            "use-interface-vrf": True,
                            "agent-information-option": {
                                "config": {
                                    "enable": True,
                                }
                            },
                        },
                        "counters": {
                            "received-requests": 100,
                            "received-responses": 90,
                            "relayed-requests": 95,
                            "relayed-responses": 85,
                            "total-drops": 5,
                        },
                        "interface": [
                            {
                                "name": "Vlan100",
                                "config": {
                                    "enable": True,
                                    "helper-address": ["10.2.2.1"],
                                },
                            }
                        ],
                    }
                }
            }
        })

        parser = ShowDhcpRelay(device="dummy")
        result = parser.cli(output=sample)

        self.assertEqual(result["helper-addresses"], ["10.1.1.1", "10.1.1.2"])
        self.assertTrue(result["use-interface-vrf"])
        self.assertTrue(result["agent-information-option"])

        # Counters
        c = result["counters"]
        self.assertEqual(c["received-requests"], 100)
        self.assertEqual(c["relayed-requests"], 95)
        self.assertEqual(c["total-drops"], 5)

        # Interfaces
        intf = result["interfaces"]["Vlan100"]
        self.assertEqual(intf["name"], "Vlan100")
        self.assertTrue(intf["enabled"])
        self.assertEqual(intf["helper-addresses"], ["10.2.2.1"])

    def test_empty(self):
        """Empty DHCP relay data raises SchemaEmptyParserError."""
        parser = ShowDhcpRelay(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))


# ---------------------------------------------------------------------------
# 3. ShowIpsecConnEntry
# ---------------------------------------------------------------------------
class TestShowIpsecConnEntry(TestCase):

    def test_basic(self):
        """Parse IPsec conn-entry with SPD entries."""
        sample = json.dumps({
            "data": {
                "arcos-ipsec-ike:ipsec-ike": {
                    "conn-entry": [
                        {
                            "name": "tunnel-vpn1",
                            "config": {
                                "version": "IKEv2",
                                "autostartup": "add",
                                "authalg": "sha256",
                                "encalg": "aes256",
                                "dh-group": 14,
                                "ike-sa-lifetime-soft": {
                                    "rekey-time": 3600,
                                },
                            },
                            "spd": {
                                "spd-entry": [
                                    {
                                        "name": "spd-rule-1",
                                        "ipsec-policy-config": {
                                            "traffic-selector": {
                                                "local-subnets": [
                                                    "192.168.1.0/24"
                                                ],
                                                "remote-subnets": [
                                                    "10.0.0.0/8"
                                                ],
                                            }
                                        },
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        })

        parser = ShowIpsecConnEntry(device="dummy")
        result = parser.cli(output=sample)

        self.assertIn("connections", result)
        conn = result["connections"]["tunnel-vpn1"]
        self.assertEqual(conn["name"], "tunnel-vpn1")
        self.assertEqual(conn["version"], "IKEv2")
        self.assertEqual(conn["autostartup"], "add")
        self.assertEqual(conn["authalg"], "sha256")
        self.assertEqual(conn["encalg"], "aes256")
        self.assertEqual(conn["dh-group"], 14)
        self.assertEqual(conn["rekey-time"], 3600)

        # SPD entries
        spd = conn["spd-entries"]["spd-rule-1"]
        self.assertEqual(spd["name"], "spd-rule-1")
        self.assertEqual(spd["local-subnets"], ["192.168.1.0/24"])
        self.assertEqual(spd["remote-subnets"], ["10.0.0.0/8"])

    def test_empty(self):
        """Empty IPsec data raises SchemaEmptyParserError."""
        parser = ShowIpsecConnEntry(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))


# ---------------------------------------------------------------------------
# 4. ShowIpfix
# ---------------------------------------------------------------------------
class TestShowIpfix(TestCase):

    def test_basic(self):
        """Parse IPFIX observation points and exporting processes."""
        sample = json.dumps({
            "data": {
                "arcos-ipfix:ipfix": {
                    "observationPoint": [
                        {
                            "name": "obs-point-1",
                            "state": {
                                "observationDomainId": 100,
                            },
                        }
                    ],
                    "exportingProcess": [
                        {
                            "name": "exporter-1",
                            "destination": [
                                {
                                    "name": "collector-a",
                                    "udpExporter": {
                                        "transportSession": {
                                            "destinationAddress": "10.10.10.1",
                                            "destinationPort": 4739,
                                            "packetsSent": 2000,
                                            "packetsDropped": 3,
                                        }
                                    },
                                }
                            ],
                        }
                    ],
                }
            }
        })

        parser = ShowIpfix(device="dummy")
        result = parser.cli(output=sample)

        # Observation points
        obs = result["observation-points"]["obs-point-1"]
        self.assertEqual(obs["name"], "obs-point-1")
        self.assertEqual(obs["observation-domain-id"], 100)

        # Exporting processes
        exp = result["exporting-processes"]["exporter-1"]
        self.assertEqual(exp["name"], "exporter-1")

        dest = exp["destinations"]["collector-a"]
        self.assertEqual(dest["name"], "collector-a")
        self.assertEqual(dest["destination-address"], "10.10.10.1")
        self.assertEqual(dest["destination-port"], 4739)
        self.assertEqual(dest["packets-sent"], 2000)
        self.assertEqual(dest["packets-dropped"], 3)

    def test_empty(self):
        """Empty IPFIX data raises SchemaEmptyParserError."""
        parser = ShowIpfix(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))


# ---------------------------------------------------------------------------
# 5. ShowPortSecurity
# ---------------------------------------------------------------------------
class TestShowPortSecurity(TestCase):

    def test_basic(self):
        """Parse port-security profiles and interfaces."""
        sample = json.dumps({
            "data": {
                "arcos-port-security:port-security": {
                    "profile": [
                        {
                            "name": "secure-profile-1",
                            "config": {
                                "limit": 5,
                                "sticky": True,
                                "violation-policy": "shutdown",
                            },
                        }
                    ],
                    "interface": [
                        {
                            "name": "ethernet-1/1",
                            "state": {
                                "security-enable": True,
                                "profile": "secure-profile-1",
                                "violation-count": 2,
                                "learned-mac-hit-count": 3,
                            },
                        }
                    ],
                }
            }
        })

        parser = ShowPortSecurity(device="dummy")
        result = parser.cli(output=sample)

        # Profiles
        prof = result["profiles"]["secure-profile-1"]
        self.assertEqual(prof["name"], "secure-profile-1")
        self.assertEqual(prof["limit"], 5)
        self.assertTrue(prof["sticky"])
        self.assertEqual(prof["violation-policy"], "shutdown")

        # Interfaces
        intf = result["interfaces"]["ethernet-1/1"]
        self.assertEqual(intf["name"], "ethernet-1/1")
        self.assertTrue(intf["enabled"])
        self.assertEqual(intf["profile"], "secure-profile-1")
        self.assertEqual(intf["violation-count"], 2)
        self.assertEqual(intf["learned-mac-count"], 3)

    def test_empty(self):
        """Empty port-security data raises SchemaEmptyParserError."""
        parser = ShowPortSecurity(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))


# ---------------------------------------------------------------------------
# 6. ShowMonitorSession
# ---------------------------------------------------------------------------
class TestShowMonitorSession(TestCase):

    def test_basic(self):
        """Parse monitor session with sources and destination."""
        sample = json.dumps({
            "data": {
                "arcos-monitor-session:monitor-session": {
                    "session": [
                        {
                            "session-name": "span-1",
                            "state": {
                                "session-name": "span-1",
                                "enable": True,
                            },
                            "source": [
                                {
                                    "state": {
                                        "interface": "ethernet-1/1",
                                        "direction": "BOTH",
                                    }
                                },
                                {
                                    "state": {
                                        "interface": "ethernet-1/2",
                                        "direction": "arcos-monitor:INGRESS",
                                    }
                                },
                            ],
                            "destination": {
                                "state": {
                                    "interface": "ethernet-1/10",
                                }
                            },
                        }
                    ]
                }
            }
        })

        parser = ShowMonitorSession(device="dummy")
        result = parser.cli(output=sample)

        self.assertIn("sessions", result)
        sess = result["sessions"]["span-1"]
        self.assertEqual(sess["name"], "span-1")
        self.assertTrue(sess["enabled"])

        # Source interfaces
        src = sess["source-interfaces"]
        self.assertIn("ethernet-1/1", src)
        self.assertEqual(src["ethernet-1/1"]["name"], "ethernet-1/1")
        self.assertEqual(src["ethernet-1/1"]["direction"], "BOTH")

        # Namespace-prefixed direction should be stripped
        self.assertIn("ethernet-1/2", src)
        self.assertEqual(src["ethernet-1/2"]["direction"], "INGRESS")

        # Destination
        self.assertEqual(sess["destination"], "ethernet-1/10")

    def test_empty(self):
        """Empty monitor session data raises SchemaEmptyParserError."""
        parser = ShowMonitorSession(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))


# ---------------------------------------------------------------------------
# 7. ShowQosPolicy
# ---------------------------------------------------------------------------
class TestShowQosPolicy(TestCase):

    def test_basic(self):
        """Parse QoS policy with classifiers and actions."""
        sample = json.dumps({
            "data": {
                "arcos-qos:qos": {
                    "arcos-qos-policy:policies": {
                        "policy": [
                            {
                                "name": "ingress-policy",
                                "classifiers": {
                                    "classifier": [
                                        {
                                            "name": "class-voice",
                                            "state": {
                                                "description": "Voice traffic",
                                            },
                                            "actions": {
                                                "action": [
                                                    {
                                                        "type": "arcos-qos:POLICE",
                                                        "police": {
                                                            "state": {
                                                                "committed": {
                                                                    "rate": {
                                                                        "value": 1000000,
                                                                        "unit": "bps",
                                                                    },
                                                                    "burst": {
                                                                        "value": 4096,
                                                                        "unit": "bytes",
                                                                    },
                                                                }
                                                            }
                                                        },
                                                    },
                                                    {
                                                        "type": "PRIORITY",
                                                        "priority": {
                                                            "state": {
                                                                "level": 1,
                                                            }
                                                        },
                                                    },
                                                    {
                                                        "type": "MARKING",
                                                        "marking": {
                                                            "state": {
                                                                "local-tc": 7,
                                                            }
                                                        },
                                                    },
                                                ]
                                            },
                                        },
                                        {
                                            "name": "class-default",
                                            "state": {},
                                            "actions": {
                                                "action": [
                                                    {
                                                        "type": "RATE_MAX",
                                                        "rate-max": {
                                                            "state": {
                                                                "rate": {
                                                                    "value": 5000000,
                                                                    "unit": "bps",
                                                                }
                                                            }
                                                        },
                                                    },
                                                    {
                                                        "type": "RATE_MIN",
                                                        "rate-min": {
                                                            "state": {
                                                                "rate": {
                                                                    "value": 500000,
                                                                    "unit": "bps",
                                                                }
                                                            }
                                                        },
                                                    },
                                                    {
                                                        "type": "RATE_EXCESS",
                                                        "rate-excess": {
                                                            "state": {
                                                                "ratio": 50,
                                                            }
                                                        },
                                                    },
                                                ]
                                            },
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        })

        parser = ShowQosPolicy(device="dummy")
        result = parser.cli(output=sample)

        self.assertIn("policies", result)
        pol = result["policies"]["ingress-policy"]
        self.assertEqual(pol["name"], "ingress-policy")

        # Classifiers
        cls_voice = pol["classifiers"]["class-voice"]
        self.assertEqual(cls_voice["name"], "class-voice")
        self.assertEqual(cls_voice["description"], "Voice traffic")

        # Actions on voice classifier
        actions = cls_voice["actions"]
        self.assertEqual(len(actions), 3)

        # POLICE action (namespace prefix stripped)
        police_act = actions[0]
        self.assertEqual(police_act["type"], "POLICE")
        self.assertEqual(police_act["rate_value"], 1000000)
        self.assertEqual(police_act["rate_unit"], "bps")
        self.assertEqual(police_act["burst_value"], 4096)
        self.assertEqual(police_act["burst_unit"], "bytes")

        # PRIORITY action
        prio_act = actions[1]
        self.assertEqual(prio_act["type"], "PRIORITY")
        self.assertEqual(prio_act["level"], 1)

        # MARKING action
        mark_act = actions[2]
        self.assertEqual(mark_act["type"], "MARKING")
        self.assertEqual(mark_act["local_tc"], 7)

        # class-default with RATE_MAX, RATE_MIN, RATE_EXCESS
        cls_def = pol["classifiers"]["class-default"]
        def_actions = cls_def["actions"]
        self.assertEqual(len(def_actions), 3)

        # RATE_MAX
        self.assertEqual(def_actions[0]["type"], "RATE_MAX")
        self.assertEqual(def_actions[0]["rate_value"], 5000000)

        # RATE_MIN
        self.assertEqual(def_actions[1]["type"], "RATE_MIN")
        self.assertEqual(def_actions[1]["rate_value"], 500000)

        # RATE_EXCESS
        self.assertEqual(def_actions[2]["type"], "RATE_EXCESS")
        self.assertEqual(def_actions[2]["ratio"], 50)

    def test_empty(self):
        """Empty QoS policy data raises SchemaEmptyParserError."""
        parser = ShowQosPolicy(device="dummy")
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=json.dumps({"data": {}}))
