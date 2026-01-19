"""Tests for ArcOS RIB (Routing Information Base) parsers.

These tests validate the RIB parsers using sample JSON data.
The parsers handle commands like:
- show network-instance <instance> rib IPV4 ipv4-entries
- show network-instance <instance> rib IPV6 ipv6-entries
- show network-instance <instance> rib IPV4 state
- show network-instance <instance> rib IPV6 state
- show network-instance <instance> rib IPV4 ipv4-label-entries
"""

import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_rib import (
    ShowRibIpv4Entries,
    ShowRibIpv6Entries,
    ShowRibIpv4State,
    ShowRibIpv6State,
    ShowRibIpv4LabelEntries,
)


# Default location of ArcOS golden samples: local relative test_samples directory.
SAMPLES_DIR = Path(
    os.environ.get("ARCOS_PARSER_SAMPLES_DIR")
    or (Path(__file__).parent / "test_samples")
)

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS golden samples directory not available",
)


class TestShowRibIpv4Entries:
    """Tests for ShowRibIpv4Entries parser."""

    def test_parse_ipv4_entries_sample(self):
        """Validate parsing of IPv4 RIB entries."""
        sample_file = SAMPLES_DIR / "rib_ipv4_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4Entries(device="dummy")
        result = parser.cli(output=output)

        assert isinstance(result, dict)
        assert "network-instance" in result
        assert "default" in result["network-instance"]

        rib = result["network-instance"]["default"]["rib"]
        assert rib["address-family"] == "openconfig-types:IPV4"
        assert "ipv4-entries" in rib

        entries = rib["ipv4-entries"]

        # Check loopback route (directly connected)
        assert "1.1.1.1/32" in entries
        route1 = entries["1.1.1.1/32"]
        assert route1["prefix"] == "1.1.1.1/32"
        assert route1["best-protocol"] == "openconfig-policy-types:DIRECTLY_CONNECTED"
        assert route1["hw-update"]["install-ack"] is False
        assert route1["hw-update"]["status-code"] == 0

        # Check origin
        origin = route1["origins"]["0"]
        assert origin["origin-protocol"] == "openconfig-policy-types:DIRECTLY_CONNECTED"
        assert origin["protocol-name"] == "directly_connected"
        assert origin["metric"] == 1
        assert origin["pref"] == 0

        # Check next-hop
        nh = origin["next-hops"]["0"]
        assert nh["next-hop"] == "1.1.1.1"
        assert nh["interface"] == "loopback0"
        assert nh["weight"] == 100
        assert "LOCAL" in nh["flags"]

    def test_parse_isis_route(self):
        """Validate parsing of ISIS route with label-pref and route-type."""
        sample_file = SAMPLES_DIR / "rib_ipv4_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4Entries(device="dummy")
        result = parser.cli(output=output)

        entries = result["network-instance"]["default"]["rib"]["ipv4-entries"]

        # Check ISIS route
        assert "2.2.2.2/32" in entries
        route = entries["2.2.2.2/32"]
        assert route["best-protocol"] == "openconfig-policy-types:ISIS"

        origin = route["origins"]["0"]
        assert origin["origin-protocol"] == "openconfig-policy-types:ISIS"
        assert origin["protocol-name"] == "isis-default@default"
        assert origin["metric"] == 20
        assert origin["pref"] == 115
        assert origin["label-pref"] == 114
        assert origin["route-type"] == "ISIS_L1"

        nh = origin["next-hops"]["0"]
        assert nh["next-hop"] == "10.10.10.2"
        assert nh["interface"] == "swp1"
        assert nh["flags"] == "ATTACH"

    def test_parse_adjacency_route(self):
        """Validate parsing of adjacency route."""
        sample_file = SAMPLES_DIR / "rib_ipv4_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4Entries(device="dummy")
        result = parser.cli(output=output)

        entries = result["network-instance"]["default"]["rib"]["ipv4-entries"]

        # Check adjacency route
        assert "10.10.10.2/32" in entries
        route = entries["10.10.10.2/32"]
        assert route["best-protocol"] == "arcos-openconfig-policy-types:ADJACENCY"

        origin = route["origins"]["0"]
        assert origin["origin-protocol"] == "arcos-openconfig-policy-types:ADJACENCY"
        assert origin["protocol-name"] == "adjacency"
        assert origin["tag"] == 1

    def test_all_routes_parsed(self):
        """Verify all routes from sample are parsed."""
        sample_file = SAMPLES_DIR / "rib_ipv4_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4Entries(device="dummy")
        result = parser.cli(output=output)

        entries = result["network-instance"]["default"]["rib"]["ipv4-entries"]

        # Verify all 5 routes are present
        expected_prefixes = [
            "1.1.1.1/32",
            "2.2.2.2/32",
            "10.10.10.0/24",
            "10.10.10.1/32",
            "10.10.10.2/32",
        ]
        for prefix in expected_prefixes:
            assert prefix in entries, f"Missing prefix: {prefix}"


class TestShowRibIpv6Entries:
    """Tests for ShowRibIpv6Entries parser."""

    def test_parse_ipv6_entries_sample(self):
        """Validate parsing of IPv6 RIB entries."""
        sample_file = SAMPLES_DIR / "rib_ipv6_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv6Entries(device="dummy")
        result = parser.cli(output=output)

        assert isinstance(result, dict)
        assert "network-instance" in result
        assert "default" in result["network-instance"]

        rib = result["network-instance"]["default"]["rib"]
        assert rib["address-family"] == "openconfig-types:IPV6"
        assert "ipv6-entries" in rib

        entries = rib["ipv6-entries"]

        # Check ISIS route with link-local next-hop
        assert "1:1::1:1/128" in entries
        route1 = entries["1:1::1:1/128"]
        assert route1["prefix"] == "1:1::1:1/128"
        assert route1["best-protocol"] == "openconfig-policy-types:ISIS"

        origin = route1["origins"]["0"]
        assert origin["origin-protocol"] == "openconfig-policy-types:ISIS"
        assert origin["protocol-name"] == "isis-default@default"
        assert origin["metric"] == 10
        assert origin["pref"] == 115
        assert origin["label-pref"] == 114
        assert origin["route-type"] == "ISIS_L2"

        nh = origin["next-hops"]["0"]
        assert nh["next-hop"] == "fe80::b6a9:fcff:fed5:c5af"
        assert nh["interface"] == "swp26"
        assert nh["flags"] == "ATTACH"

    def test_parse_ipv6_directly_connected(self):
        """Validate parsing of directly connected IPv6 route."""
        sample_file = SAMPLES_DIR / "rib_ipv6_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv6Entries(device="dummy")
        result = parser.cli(output=output)

        entries = result["network-instance"]["default"]["rib"]["ipv6-entries"]

        # Check loopback route
        assert "2:2::2:2/128" in entries
        route = entries["2:2::2:2/128"]
        assert route["best-protocol"] == "openconfig-policy-types:DIRECTLY_CONNECTED"

        origin = route["origins"]["0"]
        assert origin["protocol-name"] == "directly_connected"
        assert origin["pref"] == 0

        nh = origin["next-hops"]["0"]
        assert nh["interface"] == "loopback0"
        assert "LOCAL" in nh["flags"]

    def test_all_ipv6_routes_parsed(self):
        """Verify all routes from sample are parsed."""
        sample_file = SAMPLES_DIR / "rib_ipv6_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv6Entries(device="dummy")
        result = parser.cli(output=output)

        entries = result["network-instance"]["default"]["rib"]["ipv6-entries"]

        # Verify all 10 routes are present
        expected_prefixes = [
            "1:1::1:1/128",
            "2:2::2:2/128",
            "3:3::3:3/128",
            "4:4::4:4/128",
            "2001:10:1::1:0/127",
            "2001:10:1::1:2/127",
            "2001:10:1::1:2/128",
            "2001:20:1::1:0/127",
            "2001:20:1::1:2/127",
            "2001:20:1::1:2/128",
        ]
        for prefix in expected_prefixes:
            assert prefix in entries, f"Missing prefix: {prefix}"

    def test_empty_ipv6_entries(self):
        """Test handling of empty IPv6 RIB."""
        # Empty IPv6 output
        output = '{"data": {}}'
        parser = ShowRibIpv6Entries(device="dummy")

        with pytest.raises(Exception):  # SchemaEmptyParserError
            parser.cli(output=output)


class TestShowRibIpv4State:
    """Tests for ShowRibIpv4State parser."""

    def test_parse_ipv4_state_sample(self):
        """Validate parsing of IPv4 RIB state."""
        sample_file = SAMPLES_DIR / "rib_ipv4_state.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4State(device="dummy")
        result = parser.cli(output=output)

        assert isinstance(result, dict)
        assert "network-instance" in result
        assert "default" in result["network-instance"]

        rib = result["network-instance"]["default"]["rib"]
        assert rib["address-family"] == "openconfig-types:IPV4"
        assert "state" in rib
        assert rib["state"]["address-family"] == "openconfig-types:IPV4"


class TestShowRibIpv6State:
    """Tests for ShowRibIpv6State parser."""

    def test_empty_ipv6_state(self):
        """Test handling of empty IPv6 state."""
        output = '{"data": {}}'
        parser = ShowRibIpv6State(device="dummy")

        with pytest.raises(Exception):  # SchemaEmptyParserError
            parser.cli(output=output)


class TestShowRibIpv4LabelEntries:
    """Tests for ShowRibIpv4LabelEntries parser."""

    def test_parse_ipv4_label_entries_sample(self):
        """Validate parsing of IPv4 label entries."""
        sample_file = SAMPLES_DIR / "rib_ipv4_label_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4LabelEntries(device="dummy")
        result = parser.cli(output=output)

        assert isinstance(result, dict)
        assert "network-instance" in result
        assert "default" in result["network-instance"]

        rib = result["network-instance"]["default"]["rib"]
        assert rib["address-family"] == "openconfig-types:IPV4"
        assert "ipv4-label-entries" in rib

        entries = rib["ipv4-label-entries"]

        # Check first label entry
        assert "200011" in entries
        entry1 = entries["200011"]
        assert entry1["label"] == 200011
        assert entry1["label-type"] == "NONE"
        assert entry1["vpn-table-id"] == 1
        assert entry1["protocol"] == "openconfig-policy-types:ISIS"
        assert entry1["fec"] == "1.1.1.1/32"
        assert entry1["nhid"] == "66"
        assert entry1["flags"] == "ECMP_FEC_OPTIMIZE"

        # Check second label entry
        assert "200012" in entries
        entry2 = entries["200012"]
        assert entry2["label"] == 200012
        assert entry2["fec"] == "3.3.3.3/32"
        assert entry2["nhid"] == "90"

    def test_all_label_entries_parsed(self):
        """Verify all label entries from sample are parsed."""
        sample_file = SAMPLES_DIR / "rib_ipv4_label_entries.json"
        if not sample_file.exists():
            pytest.skip(f"Sample file not found: {sample_file}")

        output = sample_file.read_text()
        parser = ShowRibIpv4LabelEntries(device="dummy")
        result = parser.cli(output=output)

        entries = result["network-instance"]["default"]["rib"]["ipv4-label-entries"]

        # Verify all 2 label entries are present
        assert len(entries) == 2
        assert "200011" in entries
        assert "200012" in entries

    def test_empty_label_entries(self):
        """Test handling of empty label entries."""
        output = '{"data": {}}'
        parser = ShowRibIpv4LabelEntries(device="dummy")

        with pytest.raises(Exception):  # SchemaEmptyParserError
            parser.cli(output=output)


class TestParameterValidation:
    """Tests for input parameter validation."""

    def test_invalid_network_instance_characters(self):
        """Test that invalid characters raise ValueError."""
        from genie.libs.parser.arcos.utils import validate_input

        with pytest.raises(ValueError):
            validate_input("default; rm -rf /", "network_instance")

    def test_invalid_prefix_characters(self):
        """Test that invalid characters in prefix raise ValueError."""
        from genie.libs.parser.arcos.utils import validate_input

        with pytest.raises(ValueError):
            validate_input("10.0.0.0/24; cat /etc/passwd", "prefix")

    def test_valid_parameters_accepted(self):
        """Test that valid parameters are accepted."""
        from genie.libs.parser.arcos.utils import validate_input

        # Valid network instance names - should not raise
        validate_input("default", "network_instance")
        validate_input("vrf1", "network_instance")
        validate_input("mgmt-vrf", "network_instance")

        # Valid prefixes
        validate_input("10.0.0.0/24", "prefix")
        validate_input("2001:db8::/32", "prefix")
