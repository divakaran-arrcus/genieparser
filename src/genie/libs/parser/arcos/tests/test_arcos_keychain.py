"""Unit tests for ArcOS Keychain parsers."""

from unittest import TestCase
from unittest.mock import Mock

from genie.libs.parser.arcos.show_keychain import (
    ShowKeychainConfig,
    ShowKeychain,
)


# ============================================================================
# Sample JSON outputs from lab
# ============================================================================

SHOW_RUNNING_CONFIG_KEYCHAIN = """{
  "data": {
    "openconfig-keychain:keychains": {
      "keychain": [
        {
          "name": "isis-key",
          "config": {
            "name": "isis-key",
            "tolerance": 30
          },
          "keys": {
            "key": [
              {
                "key-id": "10",
                "config": {
                  "key-id": "10",
                  "secret-key": "$8$k0hukL5Ih3oArk9s4tGPhV8HHYVhV17wkpyA9BBer/o=",
                  "crypto-algorithm": "openconfig-keychain-types:HMAC_SHA_1"
                },
                "send-lifetime": {
                  "config": {
                    "arcos-openconfig-keychain-augments:always": true
                  }
                }
              },
              {
                "key-id": "20",
                "config": {
                  "key-id": "20",
                  "secret-key": "$8$87/ZbJSkGZaFrTNsgTXHHqPN6GHa4ttRaumqShughxjKZQnrSzhpTVfJzl+7fyJo",
                  "crypto-algorithm": "openconfig-keychain-types:HMAC_SHA_256"
                },
                "send-lifetime": {
                  "config": {
                    "start-time": "2026-01-01T00:00:00-00:00",
                    "end-time": "2026-12-31T23:59:59-00:00"
                  }
                }
              }
            ]
          }
        }
      ]
    }
  }
}"""

SHOW_KEYCHAIN = """{
  "data": {
    "openconfig-keychain:keychains": {
      "keychain": [
        {
          "name": "isis-key",
          "state": {
            "name": "isis-key",
            "tolerance": 30
          },
          "keys": {
            "key": [
              {
                "key-id": "10",
                "state": {
                  "key-id": "10",
                  "secret-key": "$8$k0hukL5Ih3oArk9s4tGPhV8HHYVhV17wkpyA9BBer/o=",
                  "crypto-algorithm": "openconfig-keychain-types:HMAC_SHA_1",
                  "arcos-openconfig-keychain-augments:send-active": true,
                  "arcos-openconfig-keychain-augments:receive-active": true
                },
                "send-lifetime": {
                  "state": {
                    "send-and-receive": true,
                    "arcos-openconfig-keychain-augments:always": true
                  }
                }
              },
              {
                "key-id": "20",
                "state": {
                  "key-id": "20",
                  "secret-key": "$8$87/ZbJSkGZaFrTNsgTXHHqPN6GHa4ttRaumqShughxjKZQnrSzhpTVfJzl+7fyJo",
                  "crypto-algorithm": "openconfig-keychain-types:HMAC_SHA_256",
                  "arcos-openconfig-keychain-augments:send-active": false,
                  "arcos-openconfig-keychain-augments:receive-active": true
                },
                "send-lifetime": {
                  "state": {
                    "start-time": "2026-01-01T00:00:00-00:00",
                    "end-time": "2026-12-31T23:59:59-00:00",
                    "send-and-receive": true
                  }
                }
              }
            ]
          }
        }
      ]
    }
  }
}"""


class TestShowKeychainConfig(TestCase):
    """Unit tests for ShowKeychainConfig parser."""

    def setUp(self):
        self.device = Mock()

    def test_parse_all_keychains(self):
        """Test parsing all keychains from running config."""
        parser = ShowKeychainConfig(device=self.device)
        result = parser.cli(output=SHOW_RUNNING_CONFIG_KEYCHAIN)

        self.assertIn("keychains", result)
        self.assertIn("isis-key", result["keychains"])

        kc = result["keychains"]["isis-key"]
        self.assertEqual(kc["name"], "isis-key")
        self.assertEqual(kc["tolerance"], 30)

        # Key 10
        self.assertIn("10", kc["keys"])
        key10 = kc["keys"]["10"]
        self.assertEqual(key10["key-id"], "10")
        self.assertEqual(key10["crypto-algorithm"], "HMAC_SHA_1")
        self.assertIn("secret-key", key10)
        self.assertTrue(key10["send-lifetime"]["always"])

        # Key 20
        self.assertIn("20", kc["keys"])
        key20 = kc["keys"]["20"]
        self.assertEqual(key20["key-id"], "20")
        self.assertEqual(key20["crypto-algorithm"], "HMAC_SHA_256")
        self.assertEqual(
            key20["send-lifetime"]["start-time"],
            "2026-01-01T00:00:00-00:00")
        self.assertEqual(
            key20["send-lifetime"]["end-time"],
            "2026-12-31T23:59:59-00:00")
        self.assertNotIn("always", key20["send-lifetime"])

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        from genie.metaparser.util.exceptions import SchemaEmptyParserError
        parser = ShowKeychainConfig(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")


class TestShowKeychain(TestCase):
    """Unit tests for ShowKeychain parser (operational state)."""

    def setUp(self):
        self.device = Mock()

    def test_parse_keychain_state(self):
        """Test parsing keychain operational state."""
        parser = ShowKeychain(device=self.device)
        result = parser.cli(output=SHOW_KEYCHAIN)

        self.assertIn("keychains", result)
        self.assertIn("isis-key", result["keychains"])

        kc = result["keychains"]["isis-key"]
        self.assertEqual(kc["name"], "isis-key")
        self.assertEqual(kc["tolerance"], 30)

        # Key 10 — active
        key10 = kc["keys"]["10"]
        self.assertEqual(key10["crypto-algorithm"], "HMAC_SHA_1")
        self.assertTrue(key10["send-active"])
        self.assertTrue(key10["receive-active"])
        self.assertTrue(key10["send-lifetime"]["always"])
        self.assertTrue(key10["send-lifetime"]["send-and-receive"])

        # Key 20 — send not active, receive active
        key20 = kc["keys"]["20"]
        self.assertEqual(key20["crypto-algorithm"], "HMAC_SHA_256")
        self.assertFalse(key20["send-active"])
        self.assertTrue(key20["receive-active"])
        self.assertEqual(
            key20["send-lifetime"]["start-time"],
            "2026-01-01T00:00:00-00:00")
        self.assertTrue(key20["send-lifetime"]["send-and-receive"])

    def test_empty_output(self):
        """Test empty output raises SchemaEmptyParserError."""
        from genie.metaparser.util.exceptions import SchemaEmptyParserError
        parser = ShowKeychain(device=self.device)
        with self.assertRaises(SchemaEmptyParserError):
            parser.cli(output="{}")
