"""Unit tests for 5 simple ArcOS parsers (group B).

Parsers covered:
    ShowSflow          (show_sflow.py)
    ShowPtpInstance     (show_ptp.py)
    ShowRsvpGlobal      (show_rsvp_te.py)
    ShowStaticVxlanTunnels (show_static_vxlan.py)
    ShowCoppPolicy      (show_copp.py)
"""

import json
from unittest import TestCase
from unittest.mock import Mock

from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.show_sflow import ShowSflow
from genie.libs.parser.arcos.show_ptp import ShowPtpInstance
from genie.libs.parser.arcos.show_rsvp_te import ShowRsvpGlobal
from genie.libs.parser.arcos.show_static_vxlan import ShowStaticVxlanTunnels
from genie.libs.parser.arcos.show_copp import ShowCoppPolicy


# ============================================================================
# Sample JSON outputs
# ============================================================================

SHOW_SFLOW_OUTPUT = json.dumps({
    "data": {
        "openconfig-sampling:sampling": {
            "sflow": {
                "state": {
                    "counter-sampling-interval": 20,
                    "packet-sampling-rate": 4096
                },
                "collectors": {
                    "collector": [
                        {
                            "address": "10.0.0.1",
                            "port": 6343
                        }
                    ]
                },
                "interfaces": {
                    "interface": [
                        {
                            "name": "swp1",
                            "state": {
                                "direction": "INGRESS",
                                "packet-sampling-rate": 8192
                            }
                        }
                    ]
                }
            }
        }
    }
})

SHOW_PTP_INSTANCE_OUTPUT = json.dumps({
    "data": {
        "arcos-ptp:ptp": {
            "instance-list": [
                {
                    "instance-number": 1,
                    "state": {
                        "clock-profile": "G.8275.1",
                        "clock-role": "SLAVE"
                    },
                    "default-ds": {
                        "state": {
                            "domain-number": 24,
                            "priority2": 128
                        }
                    }
                }
            ]
        }
    }
})

SHOW_RSVP_GLOBAL_OUTPUT = json.dumps({
    "data": {
        "openconfig-network-instance:network-instances": {
            "network-instance": [
                {
                    "name": "default",
                    "protocols": {
                        "protocol": [
                            {
                                "rsvp-te": {
                                    "global": {
                                        "state": {
                                            "hello-supported": True,
                                            "hello-interval": 5,
                                            "refresh-reduction": True
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

SHOW_STATIC_VXLAN_TUNNELS_OUTPUT = json.dumps({
    "data": {
        "arcos-overlay:overlay": {
            "static-vxlan-tunnels": {
                "tunnel": [
                    {
                        "state": {
                            "remote-vtep": "10.1.1.2",
                            "local-vtep": "10.1.1.1",
                            "state": "UP",
                            "vnis": [100, 200]
                        }
                    }
                ]
            }
        }
    }
})

SHOW_COPP_POLICY_OUTPUT = json.dumps({
    "data": {
        "arcos-copp:copp": {
            "policy": [
                {
                    "name": "default-copp",
                    "classifier": [
                        {
                            "name": "arp-cls",
                            "action": {
                                "type": "POLICE"
                            }
                        }
                    ]
                }
            ]
        }
    }
})


# ============================================================================
# Tests: ShowSflow
# ============================================================================

class TestShowSflow(TestCase):
    """Unit tests for ShowSflow parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic sFlow parsing with state, collectors, interfaces."""
        parser = ShowSflow(device=self.device)
        result = parser.cli(output=SHOW_SFLOW_OUTPUT)

        self.assertEqual(result["counter-sampling-interval"], 20)
        self.assertEqual(result["packet-sampling-rate"], 4096)

        # Collectors keyed by address:port
        self.assertIn("collectors", result)
        self.assertIn("10.0.0.1:6343", result["collectors"])
        collector = result["collectors"]["10.0.0.1:6343"]
        self.assertEqual(collector["address"], "10.0.0.1")
        self.assertEqual(collector["port"], 6343)

        # Interfaces keyed by name
        self.assertIn("interfaces", result)
        self.assertIn("swp1", result["interfaces"])
        intf = result["interfaces"]["swp1"]
        self.assertEqual(intf["name"], "swp1")
        self.assertEqual(intf["direction"], "INGRESS")
        self.assertEqual(intf["packet-sampling-rate"], 8192)

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowSflow(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")


# ============================================================================
# Tests: ShowPtpInstance
# ============================================================================

class TestShowPtpInstance(TestCase):
    """Unit tests for ShowPtpInstance parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic PTP instance parsing."""
        parser = ShowPtpInstance(device=self.device)
        result = parser.cli(output=SHOW_PTP_INSTANCE_OUTPUT)

        self.assertIn("instances", result)
        self.assertIn("1", result["instances"])
        inst = result["instances"]["1"]
        self.assertEqual(inst["instance-number"], 1)
        self.assertEqual(inst["clock-profile"], "G.8275.1")
        self.assertEqual(inst["clock-role"], "SLAVE")
        self.assertEqual(inst["domain-number"], 24)
        self.assertEqual(inst["priority2"], 128)

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowPtpInstance(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")


# ============================================================================
# Tests: ShowRsvpGlobal
# ============================================================================

class TestShowRsvpGlobal(TestCase):
    """Unit tests for ShowRsvpGlobal parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic RSVP global state parsing."""
        parser = ShowRsvpGlobal(device=self.device)
        result = parser.cli(output=SHOW_RSVP_GLOBAL_OUTPUT)

        self.assertEqual(result["hello-supported"], True)
        self.assertEqual(result["hello-interval"], 5)
        self.assertEqual(result["refresh-reduction"], True)

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowRsvpGlobal(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")


# ============================================================================
# Tests: ShowStaticVxlanTunnels
# ============================================================================

class TestShowStaticVxlanTunnels(TestCase):
    """Unit tests for ShowStaticVxlanTunnels parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic static VXLAN tunnel parsing."""
        parser = ShowStaticVxlanTunnels(device=self.device)
        result = parser.cli(output=SHOW_STATIC_VXLAN_TUNNELS_OUTPUT)

        self.assertIn("tunnels", result)
        self.assertIn("10.1.1.2", result["tunnels"])
        tunnel = result["tunnels"]["10.1.1.2"]
        self.assertEqual(tunnel["remote-vtep"], "10.1.1.2")
        self.assertEqual(tunnel["local-vtep"], "10.1.1.1")
        self.assertEqual(tunnel["state"], "UP")
        self.assertEqual(tunnel["vnis"], [100, 200])

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowStaticVxlanTunnels(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")


# ============================================================================
# Tests: ShowCoppPolicy
# ============================================================================

class TestShowCoppPolicy(TestCase):
    """Unit tests for ShowCoppPolicy parser."""

    def setUp(self):
        self.device = Mock()

    def test_basic_parsing(self):
        """Test basic CoPP policy parsing."""
        parser = ShowCoppPolicy(device=self.device)
        result = parser.cli(output=SHOW_COPP_POLICY_OUTPUT)

        self.assertIn("policies", result)
        self.assertIn("default-copp", result["policies"])
        policy = result["policies"]["default-copp"]
        self.assertEqual(policy["name"], "default-copp")

        self.assertIn("classifiers", policy)
        self.assertIn("arp-cls", policy["classifiers"])
        cls = policy["classifiers"]["arp-cls"]
        self.assertEqual(cls["name"], "arp-cls")
        self.assertIn("actions", cls)
        self.assertEqual(cls["actions"]["type"], "POLICE")

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        parser = ShowCoppPolicy(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")
