"""Unit tests for ArcOS RIB parsers.

Tests two parser classes with af as a runtime parameter:
- ShowRibEntries (af="IPV4" / af="IPV6")
- ShowRibLabelEntries (af="IPV4" / af="IPV6")
"""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_rib import (
    ShowRibEntries,
    ShowRibLabelEntries,
)
from genie.metaparser.util.exceptions import SchemaEmptyParserError

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


# -----------------------------------------------------------------------
# ShowRibEntries — IPv4
# -----------------------------------------------------------------------


class TestShowRibEntriesIpv4Single:
    """Test ShowRibEntries af=IPV4 with a single IPv4 prefix."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "rib_ipv4_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowRibEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        assert isinstance(result, dict)
        assert "network-instance" in result
        ni = result["network-instance"]["default"]

        # address-family stripped
        assert ni["address-family"] == "IPV4"

        # single entry keyed by prefix
        entries = ni["entries"]
        assert "5.5.5.5/32" in entries
        entry = entries["5.5.5.5/32"]

        assert entry["prefix"] == "5.5.5.5/32"
        assert entry["best-protocol"] == "ISIS"  # stripped

        # hw-update
        hw = entry["hw-update"]
        assert hw["install-ack"] is False
        assert hw["status-code"] == 0
        assert hw["version"] == "0"

        # origins — single origin at index "0"
        origins = entry["origins"]
        assert "0" in origins
        origin = origins["0"]
        assert origin["origin-protocol"] == "ISIS"  # stripped
        assert origin["protocol-name"] == "isis-default@default"
        assert origin["metric"] == 20
        assert origin["pref"] == 115
        assert origin["label-pref"] == 114
        assert origin["route-type"] == "ISIS_L2"

        # next-hops — single next-hop at index "0"
        nhs = origin["next-hops"]
        assert "0" in nhs
        nh = nhs["0"]
        assert nh["next-hop"] == "10.15.4.5"
        assert nh["interface"] == "swp4"
        assert nh["weight"] == 100
        assert nh["pushed-mpls-label-stack"] == [3]


class TestShowRibEntriesIpv4Multi:
    """Test ShowRibEntries af=IPV4 with multiple IPv4 entries."""

    def test_parse_multiple_entries(self):
        sample = SAMPLES_DIR / "rib_ipv4_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowRibEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        entries = ni["entries"]

        # Verify multiple entries present
        assert "1.1.1.1/32" in entries
        assert "2.2.2.2/32" in entries
        assert "3.3.3.3/32" in entries

        # Directly connected entry
        local = entries["1.1.1.1/32"]
        assert local["best-protocol"] == "DIRECTLY_CONNECTED"
        origin = local["origins"]["0"]
        assert origin["origin-protocol"] == "DIRECTLY_CONNECTED"
        assert origin["protocol-name"] == "directly_connected"
        assert origin["metric"] == 1
        assert origin["pref"] == 0

        # ISIS entry
        isis = entries["2.2.2.2/32"]
        assert isis["best-protocol"] == "ISIS"
        origin = isis["origins"]["0"]
        assert origin["metric"] == 20
        assert origin["pref"] == 115


# -----------------------------------------------------------------------
# ShowRibEntries — IPv6
# -----------------------------------------------------------------------


class TestShowRibEntriesIpv6Single:
    """Test ShowRibEntries af=IPV6 with a single IPv6 prefix."""

    def test_parse_single_entry(self):
        sample = SAMPLES_DIR / "rib_ipv6_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowRibEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        entries = ni["entries"]
        assert "2001::5/128" in entries
        entry = entries["2001::5/128"]

        assert entry["prefix"] == "2001::5/128"
        assert entry["best-protocol"] == "ISIS"

        origin = entry["origins"]["0"]
        assert origin["origin-protocol"] == "ISIS"
        assert origin["metric"] == 20

        nh = origin["next-hops"]["0"]
        assert nh["next-hop"] == "fe80::b8d0:10ff:feb5:8ced"
        assert nh["type"] == "IPV6"
        assert nh["interface"] == "swp4"


# -----------------------------------------------------------------------
# ShowRibEntries — empty / error
# -----------------------------------------------------------------------


class TestShowRibEntriesEmpty:
    """Test RIB entry parsers raise on empty data."""

    def test_ipv4_empty_json_raises(self):
        empty_output = '{"data": {}}'
        parser = ShowRibEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output=empty_output, network_instance="default", af="IPV4")

    def test_ipv6_empty_json_raises(self):
        empty_output = '{"data": {}}'
        parser = ShowRibEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output=empty_output, network_instance="default", af="IPV6")

    def test_ipv4_no_entries_raises(self):
        no_entries = """{
          "data": {
            "openconfig-network-instance:network-instances": {
              "network-instance": [{
                "name": "default",
                "arcos-rib:rib": [{
                  "address-family": "openconfig-types:IPV4",
                  "ipv4-entries": {"entry": []}
                }]
              }]
            }
          }
        }"""
        parser = ShowRibEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output=no_entries, network_instance="default", af="IPV4")


# -----------------------------------------------------------------------
# ShowRibLabelEntries — IPv4
# -----------------------------------------------------------------------


class TestShowRibLabelEntriesIpv4Single:
    """Test ShowRibLabelEntries af=IPV4 with a single IPv4 label."""

    def test_parse_single_label(self):
        sample = SAMPLES_DIR / "rib_ipv4_label_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowRibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV4"

        labels = ni["label-entries"]
        assert "10005" in labels
        entry = labels["10005"]

        assert entry["label"] == 10005
        assert entry["label-type"] == "NONE"
        assert entry["vpn-table-id"] == 1
        assert entry["protocol"] == "ISIS"  # stripped
        assert entry["fec"] == "5.5.5.5/32"
        assert entry["nhid"] == "643"
        assert entry["flags"] == "ECMP_FEC_OPTIMIZE"


class TestShowRibLabelEntriesIpv4Multi:
    """Test ShowRibLabelEntries af=IPV4 with multiple IPv4 labels."""

    def test_parse_multiple_labels(self):
        sample = SAMPLES_DIR / "rib_ipv4_label_entries.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowRibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV4")

        ni = result["network-instance"]["default"]
        labels = ni["label-entries"]

        # 7 entries in the sample
        assert len(labels) == 7

        # DEAGG entry
        deagg = labels["10001"]
        assert deagg["label"] == 10001
        assert deagg["label-type"] == "DEAGG"
        assert deagg["protocol"] == "ISIS"
        assert deagg["fec"] == "1.1.1.1/32"
        assert deagg.get("control-word") is False
        assert deagg.get("flow-label") is False

        # Regular entry
        regular = labels["10005"]
        assert regular["fec"] == "5.5.5.5/32"
        assert regular["flags"] == "ECMP_FEC_OPTIMIZE"

        # Adjacency SID entry (no fec)
        adj = labels["20121"]
        assert adj["label"] == 20121
        assert "fec" not in adj or adj.get("fec") is None


# -----------------------------------------------------------------------
# ShowRibLabelEntries — IPv6
# -----------------------------------------------------------------------


class TestShowRibLabelEntriesIpv6Single:
    """Test ShowRibLabelEntries af=IPV6 with a single IPv6 label."""

    def test_parse_single_label(self):
        sample = SAMPLES_DIR / "rib_ipv6_label_entry_single.json"
        if not sample.exists():
            pytest.skip(f"Sample not found: {sample}")

        output = sample.read_text()
        parser = ShowRibLabelEntries(device="dummy")
        result = parser.cli(output=output, network_instance="default", af="IPV6")

        ni = result["network-instance"]["default"]
        assert ni["address-family"] == "IPV6"

        labels = ni["label-entries"]
        assert "10105" in labels
        entry = labels["10105"]

        assert entry["label"] == 10105
        assert entry["protocol"] == "ISIS"
        assert entry["fec"] == "2001::5/128"
        assert entry["vpn-table-id"] == 2147483649


# -----------------------------------------------------------------------
# ShowRibLabelEntries — empty / error
# -----------------------------------------------------------------------


class TestShowRibLabelEntriesEmpty:
    """Test RIB label parsers raise on empty data."""

    def test_ipv4_empty_json_raises(self):
        empty_output = '{"data": {}}'
        parser = ShowRibLabelEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output=empty_output, network_instance="default", af="IPV4")

    def test_ipv6_empty_json_raises(self):
        empty_output = '{"data": {}}'
        parser = ShowRibLabelEntries(device="dummy")
        with pytest.raises(SchemaEmptyParserError):
            parser.cli(output=empty_output, network_instance="default", af="IPV6")
