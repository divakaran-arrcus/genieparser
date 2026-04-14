"""Unit tests for simple ArcOS parsers (batch A).

Covers: ShowSnmpServer, ShowSystemHostname, ShowStpGlobal,
        ShowSynce, ShowStormControl, ShowDamping.
"""

import json
from unittest import TestCase
from unittest.mock import Mock

from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.show_snmp import ShowSnmpServer
from genie.libs.parser.arcos.show_system import ShowSystemHostname
from genie.libs.parser.arcos.show_stp import ShowStpGlobal
from genie.libs.parser.arcos.show_synce import ShowSynce
from genie.libs.parser.arcos.show_storm_control import ShowStormControl
from genie.libs.parser.arcos.show_damping import ShowDamping


# ============================================================================
# ShowSnmpServer
# ============================================================================

class TestShowSnmpServer(TestCase):

    def test_basic(self):
        sample = json.dumps({
            "data": {
                "openconfig-system:system": {
                    "arcos-snmp:snmp-server": {
                        "config": {
                            "enable": True
                        }
                    }
                }
            }
        })
        parser = ShowSnmpServer(device=Mock())
        result = parser.cli(output=sample)
        self.assertEqual(result["enabled"], True)

    def test_empty(self):
        sample = json.dumps({"data": {}})
        parser = ShowSnmpServer(device=Mock())
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=sample)


# ============================================================================
# ShowSystemHostname
# ============================================================================

class TestShowSystemHostname(TestCase):

    def test_basic(self):
        sample = json.dumps({
            "data": {
                "openconfig-system:system": {
                    "config": {
                        "hostname": "rtr1"
                    }
                }
            }
        })
        parser = ShowSystemHostname(device=Mock())
        result = parser.cli(output=sample)
        self.assertEqual(result["hostname"], "rtr1")

    def test_empty(self):
        sample = json.dumps({"data": {}})
        parser = ShowSystemHostname(device=Mock())
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=sample)


# ============================================================================
# ShowStpGlobal
# ============================================================================

class TestShowStpGlobal(TestCase):

    def test_basic(self):
        sample = json.dumps({
            "data": {
                "openconfig-spanning-tree:stp": {
                    "global": {
                        "config": {
                            "bridge-assurance": True,
                            "bpdu-guard": False,
                            "enabled-protocol": [
                                "openconfig-spanning-tree-types:RAPID_PVST"
                            ]
                        }
                    }
                }
            }
        })
        parser = ShowStpGlobal(device=Mock())
        result = parser.cli(output=sample)
        self.assertEqual(result["bridge-assurance"], True)
        self.assertEqual(result["bpdu-guard"], False)
        self.assertEqual(result["enabled-protocol"], "RAPID_PVST")

    def test_empty(self):
        sample = json.dumps({"data": {}})
        parser = ShowStpGlobal(device=Mock())
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=sample)


# ============================================================================
# ShowSynce
# ============================================================================

class TestShowSynce(TestCase):

    def test_basic(self):
        sample = json.dumps({
            "data": {
                "arcos-synce:sync-e": {
                    "state": {
                        "enabled": True,
                        "holdover": 300,
                        "quality-level-enabled": True,
                        "sync-e-clock-state": "LOCKED"
                    }
                }
            }
        })
        parser = ShowSynce(device=Mock())
        result = parser.cli(output=sample)
        self.assertEqual(result["enabled"], True)
        self.assertEqual(result["holdover"], 300)
        self.assertEqual(result["quality-level-enabled"], True)
        self.assertEqual(result["clock-state"], "LOCKED")

    def test_empty(self):
        sample = json.dumps({"data": {}})
        parser = ShowSynce(device=Mock())
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=sample)


# ============================================================================
# ShowStormControl
# ============================================================================

class TestShowStormControl(TestCase):

    def test_basic(self):
        sample = json.dumps({
            "data": {
                "openconfig-interfaces:interfaces": {
                    "interface": [
                        {
                            "name": "ethernet-1/1",
                            "arcos-storm-control:storm-control": {
                                "state": {
                                    "broadcast-kbps": 1000,
                                    "multicast-kbps": 500
                                }
                            }
                        }
                    ]
                }
            }
        })
        parser = ShowStormControl(device=Mock())
        result = parser.cli(output=sample)
        self.assertEqual(result["broadcast-kbps"], 1000)
        self.assertEqual(result["multicast-kbps"], 500)

    def test_empty(self):
        sample = json.dumps({"data": {}})
        parser = ShowStormControl(device=Mock())
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=sample)


# ============================================================================
# ShowDamping
# ============================================================================

class TestShowDamping(TestCase):

    def test_basic(self):
        sample = json.dumps({
            "data": {
                "openconfig-interfaces:interfaces": {
                    "interface": [
                        {
                            "name": "ethernet-1/1",
                            "arcos-damping:damping": {
                                "state": {
                                    "enabled": True,
                                    "max-suppress-time": 60,
                                    "decay-half-life": 15,
                                    "suppress-threshold": 2000,
                                    "reuse-threshold": 750
                                }
                            }
                        }
                    ]
                }
            }
        })
        parser = ShowDamping(device=Mock())
        result = parser.cli(output=sample)
        self.assertEqual(result["enabled"], True)
        self.assertEqual(result["max-suppress-time"], 60)
        self.assertEqual(result["decay-half-life"], 15)
        self.assertEqual(result["suppress-threshold"], 2000)
        self.assertEqual(result["reuse-threshold"], 750)

    def test_empty(self):
        sample = json.dumps({"data": {}})
        parser = ShowDamping(device=Mock())
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output=sample)
