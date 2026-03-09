"""Unit tests for ArcOS FIB parsers.

Tests three parser classes with af as a runtime parameter:
- ShowFibPrefixEntries (af="IPV4" / af="IPV6")
- ShowFibNexthopEntries (af="IPV4" / af="IPV6")
- ShowFibLabelEntries (af="IPV4" / af="IPV6")
"""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_fib import (
    ShowFibPrefixEntries,
    ShowFibNexthopEntries,
    ShowFibLabelEntries,
)
from genie.metaparser.util.exceptions import SchemaEmptyParserError

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


# -----------------------------------------------------------------------
# ShowFibPrefixEntries — IPv4
# -----------------------------------------------------------------------


class TestShowFibPrefixEntriesIpv4:
    """Test ShowFibPrefixEntries af=IPV4 with multiple entries."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "fib_ipv4_prefix_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibPrefixEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        assert isinstance(result, dict)
        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        entries = ni["prefix-entries"]
        assert len(entries) == 30

        # Spot-check a specific entry
        e = entries["5.5.5.5/32"]
        assert e["prefix"] == "5.5.5.5/32"
        assert e["next-hop-id"] == 643
        assert e["publish-type"] == "PATH"
        assert e["publish-id"] == 642

    def test_parse_ecmp_entry(self):
        sample = SAMPLES_DIR / "fib_ipv4_prefix_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibPrefixEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        e = result["network-instance"]["default"]["prefix-entries"]["4.4.4.4/32"]
        assert e["publish-type"] == "ECMP"


class TestShowFibPrefixEntriesIpv4Single:
    """Test ShowFibPrefixEntries af=IPV4 with a single entry."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "fib_ipv4_prefix_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibPrefixEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        entries = ni["prefix-entries"]
        assert len(entries) == 1
        assert "5.5.5.5/32" in entries
        e = entries["5.5.5.5/32"]
        assert e["next-hop-id"] == 643
        assert e["publish-type"] == "PATH"

    def test_entry_without_nexthop(self):
        """Test entry with no next-hop-id (e.g. 0.0.0.0/0 default)."""
        sample = SAMPLES_DIR / "fib_ipv4_prefix_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibPrefixEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        e = result["network-instance"]["default"]["prefix-entries"]["0.0.0.0/0"]
        assert e["prefix"] == "0.0.0.0/0"
        assert "next-hop-id" not in e


# -----------------------------------------------------------------------
# ShowFibPrefixEntries — IPv6
# -----------------------------------------------------------------------


class TestShowFibPrefixEntriesIpv6:
    """Test ShowFibPrefixEntries af=IPV6."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "fib_ipv6_prefix_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibPrefixEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        entries = ni["prefix-entries"]
        assert len(entries) == 26

        e = entries["2001::5/128"]
        assert e["next-hop-id"] == 268435890
        assert e["publish-type"] == "PATH"


class TestShowFibPrefixEntriesIpv6Single:
    """Test ShowFibPrefixEntries af=IPV6 with a single entry."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "fib_ipv6_prefix_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibPrefixEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        entries = ni["prefix-entries"]
        assert len(entries) == 1
        e = entries["2001::5/128"]
        assert e["next-hop-id"] == 268435890
        assert e["publish-id"] == 268435889


# -----------------------------------------------------------------------
# ShowFibNexthopEntries — IPv4
# -----------------------------------------------------------------------


class TestShowFibNexthopEntriesIpv4:
    """Test ShowFibNexthopEntries af=IPV4 with multiple entries."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "fib_ipv4_nexthop_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        nh = ni["nexthop-entries"]
        assert len(nh) > 10

        # Check a simple connected nexthop
        e = nh["643"]
        assert e["index"] == 643
        assert e["eos0-nexthop-index"] == 536871555
        assert e["level"] == 1
        assert e["flags"] == "IP_REACH"

        # Check paths
        paths = e["paths"]
        assert "0" in paths
        p = paths["0"]
        assert p["path-id"] == 642
        assert p["path-type"] == "CONNECTED_V4"
        assert p["next-hop"] == "10.15.4.5"
        assert p["interface"] == "swp4"

    def test_recursive_nexthop(self):
        """Test recursive nexthop with integer next-hop (NH-ID)."""
        sample = SAMPLES_DIR / "fib_ipv4_nexthop_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        # Index 641 is RECURSIVE with next-hop as integer NH-ID
        e = result["network-instance"]["default"]["nexthop-entries"]["641"]
        assert "RECURSIVE" in e["flags"]
        assert e["level"] == 2
        p = e["paths"]["0"]
        assert p["path-type"] == "RECURSIVE"
        assert p["nh-type"] == "IGP"
        assert p["next-hop"] == 630  # integer NH-ID
        assert p["num-coll-paths"] == 2
        assert p["igp-path-id"] == [622, 23]

    def test_mpls_push_label(self):
        """Test nexthop with push-label."""
        sample = SAMPLES_DIR / "fib_ipv4_nexthop_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        # Index 536871547 has MPLS_REACH and push-label
        e = result["network-instance"]["default"]["nexthop-entries"]["536871547"]
        assert "MPLS_REACH" in e["flags"]
        assert e["source-nexthop-index"] == 635
        p = e["paths"]["0"]
        assert p["push-label"] == [3]

    def test_ecmp_paths(self):
        """Test nexthop with multiple ECMP paths."""
        sample = SAMPLES_DIR / "fib_ipv4_nexthop_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        # Index 632 has 3 ECMP paths
        e = result["network-instance"]["default"]["nexthop-entries"]["632"]
        assert len(e["paths"]) == 3


class TestShowFibNexthopEntriesIpv4Single:
    """Test ShowFibNexthopEntries af=IPV4 with a single entry."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "fib_ipv4_nexthop_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        nh = ni["nexthop-entries"]
        assert len(nh) == 1
        e = nh["643"]
        assert e["index"] == 643
        assert e["paths"]["0"]["next-hop"] == "10.15.4.5"


# -----------------------------------------------------------------------
# ShowFibNexthopEntries — IPv6
# -----------------------------------------------------------------------


class TestShowFibNexthopEntriesIpv6:
    """Test ShowFibNexthopEntries af=IPV6."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "fib_ipv6_nexthop_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        nh = ni["nexthop-entries"]
        assert len(nh) > 15

    def test_ipv6_recursive_nexthop(self):
        """Test IPv6 recursive nexthop with integer next-hop."""
        sample = SAMPLES_DIR / "fib_ipv6_nexthop_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        # Index 268435892 is RECURSIVE
        e = result["network-instance"]["default"]["nexthop-entries"]["268435892"]
        assert "RECURSIVE" in e["flags"]
        p = e["paths"]["0"]
        assert p["next-hop"] == 268435879  # integer NH-ID


class TestShowFibNexthopEntriesIpv6Single:
    """Test ShowFibNexthopEntries af=IPV6 with a single entry."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "fib_ipv6_nexthop_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibNexthopEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        nh = ni["nexthop-entries"]
        assert len(nh) == 1
        e = nh["268435890"]
        assert e["index"] == 268435890
        assert e["paths"]["0"]["next-hop"] == "fe80::b8d0:10ff:feb5:8ced"
        assert e["paths"]["0"]["interface"] == "swp4"


# -----------------------------------------------------------------------
# ShowFibLabelEntries — IPv4
# -----------------------------------------------------------------------


class TestShowFibLabelEntriesIpv4:
    """Test ShowFibLabelEntries af=IPV4 with multiple entries."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "fib_ipv4_label_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        labels = ni["label-entries"]
        assert len(labels) == 7

        # Entry with no next-hop-id (10001)
        e = labels["10001"]
        assert e["local-label"] == 10001
        assert e["vpn-table-id"] == 1
        assert e["control-word"] is False
        assert e["flow-label"] is False
        assert "next-hop-id" not in e

        # Entry with next-hop-id (10005)
        e = labels["10005"]
        assert e["local-label"] == 10005
        assert e["next-hop-id"] == 643
        assert e["publish-id"] == 536871554


class TestShowFibLabelEntriesIpv4Single:
    """Test ShowFibLabelEntries af=IPV4 with a single entry."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "fib_ipv4_label_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        labels = ni["label-entries"]
        assert len(labels) == 1
        e = labels["10005"]
        assert e["local-label"] == 10005
        assert e["next-hop-id"] == 643


# -----------------------------------------------------------------------
# ShowFibLabelEntries — IPv6
# -----------------------------------------------------------------------


class TestShowFibLabelEntriesIpv6:
    """Test ShowFibLabelEntries af=IPV6 with multiple entries."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "fib_ipv6_label_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        labels = ni["label-entries"]
        assert len(labels) == 4

        # Entry with no next-hop-id (10101)
        e = labels["10101"]
        assert e["local-label"] == 10101
        assert e["vpn-table-id"] == 2147483649
        assert e["control-word"] is False
        assert "next-hop-id" not in e

        # Entry with next-hop-id (10105)
        e = labels["10105"]
        assert e["local-label"] == 10105
        assert e["next-hop-id"] == 268435890


class TestShowFibLabelEntriesIpv6Single:
    """Test ShowFibLabelEntries af=IPV6 with a single entry."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "fib_ipv6_label_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowFibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        labels = ni["label-entries"]
        assert len(labels) == 1
        e = labels["10105"]
        assert e["local-label"] == 10105
        assert e["next-hop-id"] == 268435890
        assert e["publish-id"] == 805306801
