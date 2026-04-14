"""Unit tests for ArcOS ACL parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_acl import ShowAclSet

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


class TestShowAclSet:
    """Tests for ShowAclSet parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "acl_set.json").read_text()
        parser = ShowAclSet(device="dummy")
        return parser.cli(output=output)

    def test_acl_set_count(self):
        """Validate that one ACL set is parsed."""
        result = self._parse()
        assert "acl-sets" in result
        assert len(result["acl-sets"]) == 1
        assert "pyats-test-v4 ACL_IPV4" in result["acl-sets"]

    def test_acl_set_fields(self):
        """Validate ACL set name and type with OC prefix stripped."""
        result = self._parse()
        acl = result["acl-sets"]["pyats-test-v4 ACL_IPV4"]
        assert acl["name"] == "pyats-test-v4"
        assert acl["type"] == "ACL_IPV4"

    def test_acl_entry_count(self):
        """Validate that both ACL entries are parsed."""
        result = self._parse()
        acl = result["acl-sets"]["pyats-test-v4 ACL_IPV4"]
        assert "acl-entries" in acl
        assert len(acl["acl-entries"]) == 2
        assert set(acl["acl-entries"].keys()) == {"10", "1000"}

    def test_acl_entry_drop_rule(self):
        """Validate the DROP rule (sequence 10) fields."""
        result = self._parse()
        ace = result["acl-sets"]["pyats-test-v4 ACL_IPV4"]["acl-entries"]["10"]
        assert ace["sequence-id"] == "10"
        assert ace["priority"] == 10
        assert ace["ipv4-source-address"] == "10.0.0.0/8"
        assert ace["forwarding-action"] == "DROP"
        assert ace["log-action"] == "LOG_NONE"

    def test_acl_entry_accept_rule(self):
        """Validate the ACCEPT rule (sequence 1000) fields."""
        result = self._parse()
        ace = result["acl-sets"]["pyats-test-v4 ACL_IPV4"]["acl-entries"]["1000"]
        assert ace["sequence-id"] == "1000"
        assert ace["priority"] == 1000
        assert ace["ipv4-source-address"] == "0.0.0.0/0"
        assert ace["forwarding-action"] == "ACCEPT"
        assert ace["log-action"] == "LOG_NONE"

    def test_acl_entry_counters(self):
        """Validate augmented counter fields are extracted."""
        result = self._parse()
        ace = result["acl-sets"]["pyats-test-v4 ACL_IPV4"]["acl-entries"]["10"]
        assert ace["matched-ingress-packets"] == "0"
        assert ace["matched-egress-packets"] == "0"
        assert ace["matched-ingress-octets"] == "0"
        assert ace["matched-egress-octets"] == "0"
