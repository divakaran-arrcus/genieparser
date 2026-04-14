"""Unit tests for ArcOS LDP parsers."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_ldp import (
    ShowLdpInterface,
    ShowLdpSession,
    ShowLdpHelloAdjacency,
    ShowLdpNeighbor,
)

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


# =====================================================================
# ShowLdpInterface
# =====================================================================

class TestShowLdpInterface:
    """Tests for ShowLdpInterface parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "ldp_interface.json").read_text()
        parser = ShowLdpInterface(device="dummy")
        return parser.cli(output=output)

    def test_interface_count(self):
        """Validate that both LDP interfaces are parsed."""
        result = self._parse()
        assert "interfaces" in result
        assert len(result["interfaces"]) == 2
        assert set(result["interfaces"].keys()) == {"swp1", "swp2"}

    def test_interface_fields(self):
        """Validate interface-level fields for swp1."""
        result = self._parse()
        intf = result["interfaces"]["swp1"]
        assert intf["interface-id"] == "swp1"
        assert intf["hello-holdtime"] == 15
        assert intf["hello-interval"] == 5
        assert intf["link-hello"] is True

    def test_interface_address_families(self):
        """Validate address-family data for swp2."""
        result = self._parse()
        intf = result["interfaces"]["swp2"]
        assert "address-families" in intf
        afs = intf["address-families"]
        assert "IPV4" in afs
        assert afs["IPV4"]["afi-name"] == "IPV4"
        assert afs["IPV4"]["enabled"] is True


# =====================================================================
# ShowLdpSession
# =====================================================================

class TestShowLdpSession:
    """Tests for ShowLdpSession parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "ldp_session.json").read_text()
        parser = ShowLdpSession(device="dummy")
        return parser.cli(output=output)

    def test_session_count(self):
        """Validate that both LDP sessions are parsed."""
        result = self._parse()
        assert "sessions" in result
        assert len(result["sessions"]) == 2
        assert set(result["sessions"].keys()) == {"1.1.1.1", "3.3.3.3"}

    def test_session_state_and_role(self):
        """Validate session state, role, and addresses for 1.1.1.1."""
        result = self._parse()
        sess = result["sessions"]["1.1.1.1"]
        assert sess["peer-address"] == "1.1.1.1"
        assert sess["local-address"] == "2.2.2.2"
        assert sess["session-state"] == "Operational"
        assert sess["session-role"] == "Active"
        assert sess["local-lsr-id"] == "2.2.2.2"
        assert sess["remote-lsr-id"] == "1.1.1.1"

    def test_session_timers_and_counters(self):
        """Validate keepalive timers, label space IDs, and graceful restart."""
        result = self._parse()
        sess = result["sessions"]["1.1.1.1"]
        assert sess["keepalive-timeout"] == 30
        assert sess["keepalive-interval"] == 10
        assert sess["local-label-space-id"] == 0
        assert sess["remote-label-space-id"] == 0
        assert sess["graceful-restart"] == "Disabled"
        assert sess["graceful-restart-state"] == "Inactive"
        assert sess["reconnect-time"] == 0
        assert sess["recovery-time"] == 0
        assert sess["forwarding-holdtime"] == 0
        assert sess["reset-count"] == 1

    def test_session_passive_role(self):
        """Validate passive session role for 3.3.3.3."""
        result = self._parse()
        sess = result["sessions"]["3.3.3.3"]
        assert sess["session-role"] == "Passive"
        assert sess["reset-count"] == 0
        assert sess["uptime"] == "0d 00:00:23"


# =====================================================================
# ShowLdpHelloAdjacency
# =====================================================================

class TestShowLdpHelloAdjacency:
    """Tests for ShowLdpHelloAdjacency parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "ldp_hello_adjacency.json").read_text()
        parser = ShowLdpHelloAdjacency(device="dummy")
        return parser.cli(output=output)

    def test_adjacency_count(self):
        """Validate that all 4 hello adjacencies are parsed (2 LINK + 2 TARGETED)."""
        result = self._parse()
        assert "hello-adjacencies" in result
        assert len(result["hello-adjacencies"]) == 4

    def test_link_adjacency_fields(self):
        """Validate LINK adjacency fields for 10.12.1.1."""
        result = self._parse()
        adj = result["hello-adjacencies"]["10.12.1.1:LINK"]
        assert adj["peer-address"] == "10.12.1.1"
        assert adj["adjacency-type"] == "LINK"
        assert adj["lsr-id"] == "1.1.1.1"
        assert adj["transport-address"] == "1.1.1.1"
        assert adj["source-address"] == "10.12.1.1"
        assert adj["holdtime"] == 15
        assert adj["interface"] == "swp1"
        assert adj["version"] == 1
        assert adj["label-space-id"] == 0

    def test_targeted_adjacency_fields(self):
        """Validate TARGETED adjacency fields and holdtime difference."""
        result = self._parse()
        adj = result["hello-adjacencies"]["1.1.1.1:TARGETED"]
        assert adj["peer-address"] == "1.1.1.1"
        assert adj["adjacency-type"] == "TARGETED"
        assert adj["holdtime"] == 45
        assert adj["source-address"] == "1.1.1.1"


# =====================================================================
# ShowLdpNeighbor
# =====================================================================

class TestShowLdpNeighbor:
    """Tests for ShowLdpNeighbor parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "ldp_neighbor.json").read_text()
        parser = ShowLdpNeighbor(device="dummy")
        return parser.cli(output=output)

    def test_neighbor_count(self):
        """Validate that both LDP neighbors are parsed."""
        result = self._parse()
        assert "neighbors" in result
        assert len(result["neighbors"]) == 2
        assert set(result["neighbors"].keys()) == {"1.1.1.1/0", "3.3.3.3/0"}

    def test_neighbor_fields(self):
        """Validate neighbor fields for 1.1.1.1/0."""
        result = self._parse()
        nbr = result["neighbors"]["1.1.1.1/0"]
        assert nbr["lsr-id"] == "1.1.1.1"
        assert nbr["label-space-id"] == 0
        assert nbr["auth-enable"] is False
        assert nbr["maximum-remote-binding"] == 0
        assert nbr["targeted-hello-holdtime"] == 45
        assert nbr["targeted-hello-interval"] == 15

    def test_neighbor_targeted_address_families(self):
        """Validate targeted address-family data for 3.3.3.3/0."""
        result = self._parse()
        nbr = result["neighbors"]["3.3.3.3/0"]
        assert "targeted-address-families" in nbr
        afs = nbr["targeted-address-families"]
        assert "IPV4" in afs
        assert afs["IPV4"]["afi-name"] == "IPV4"
        assert afs["IPV4"]["enabled"] is True
        assert afs["IPV4"]["destination-address"] == "3.3.3.3"
