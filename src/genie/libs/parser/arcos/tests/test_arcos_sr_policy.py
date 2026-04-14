"""Unit tests for ArcOS SR-Policy parsers."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_sr_policy import (
    ShowSrPolicySegmentList,
    ShowSrPolicyPolicy,
    ShowSrPolicyDatabasePolicy,
)

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


# =====================================================================
# ShowSrPolicySegmentList
# =====================================================================

class TestShowSrPolicySegmentList:
    """Tests for ShowSrPolicySegmentList parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "sr_policy_segment_list.json").read_text()
        parser = ShowSrPolicySegmentList(device="dummy")
        return parser.cli(output=output)

    def test_segment_list_count(self):
        """Validate that one segment-list is parsed."""
        result = self._parse()
        assert "segment-lists" in result
        assert len(result["segment-lists"]) == 1
        assert "sl1" in result["segment-lists"]

    def test_segment_list_fields(self):
        """Validate segment-list state fields."""
        result = self._parse()
        sl = result["segment-lists"]["sl1"]
        assert sl["name"] == "sl1"
        assert sl["index"] == 2

    def test_segment_list_segments(self):
        """Validate individual segments within the segment-list."""
        result = self._parse()
        sl = result["segment-lists"]["sl1"]
        assert "segments" in sl
        segments = sl["segments"]
        assert len(segments) == 2

        seg1 = segments["1"]
        assert seg1["index"] == 1
        assert seg1["type"] == "MPLS_LABEL"
        assert seg1["validate"] is False
        assert seg1["mpls-label"] == 100000

        seg2 = segments["2"]
        assert seg2["index"] == 2
        assert seg2["type"] == "MPLS_LABEL"
        assert seg2["mpls-label"] == 100001


# =====================================================================
# ShowSrPolicyPolicy
# =====================================================================

class TestShowSrPolicyPolicy:
    """Tests for ShowSrPolicyPolicy parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "sr_policy_policy.json").read_text()
        parser = ShowSrPolicyPolicy(device="dummy")
        return parser.cli(output=output)

    def test_policy_count(self):
        """Validate that one policy is parsed."""
        result = self._parse()
        assert "policies" in result
        assert len(result["policies"]) == 1
        assert "2.2.2.2 100" in result["policies"]

    def test_policy_fields(self):
        """Validate policy-level fields."""
        result = self._parse()
        pol = result["policies"]["2.2.2.2 100"]
        assert pol["endpoint"] == "2.2.2.2"
        assert pol["color"] == 100
        assert pol["name"] == "test-policy-to-rtr2"
        assert pol["description"] == "Test SR-Policy towards rtr2"
        assert pol["enabled"] is True
        assert pol["priority"] == 128

    def test_policy_candidate_paths(self):
        """Validate candidate-path data within the policy."""
        result = self._parse()
        pol = result["policies"]["2.2.2.2 100"]
        assert "candidate-paths" in pol
        cps = pol["candidate-paths"]
        assert len(cps) == 1
        assert "10" in cps

        cp = cps["10"]
        assert cp["discriminator"] == 10
        assert cp["preference"] == 200
        assert cp["originator-as"] == 0
        assert cp["originator-address"] == "0.0.0.0"
        assert cp["type"] == "EXPLICIT_SEGMENT_LIST"
        assert cp["explicit-segment-lists"] == ["sl1"]


# =====================================================================
# ShowSrPolicyDatabasePolicy
# =====================================================================

class TestShowSrPolicyDatabasePolicy:
    """Tests for ShowSrPolicyDatabasePolicy parser."""

    def _parse(self):
        output = (SAMPLES_DIR / "sr_policy_database_policy.json").read_text()
        parser = ShowSrPolicyDatabasePolicy(device="dummy")
        return parser.cli(output=output)

    def test_database_policy_count(self):
        """Validate that one database policy is parsed."""
        result = self._parse()
        assert "policies" in result
        assert len(result["policies"]) == 1
        assert "2.2.2.2 100" in result["policies"]

    def test_database_policy_oper_state(self):
        """Validate operational state fields."""
        result = self._parse()
        pol = result["policies"]["2.2.2.2 100"]
        assert pol["endpoint"] == "2.2.2.2"
        assert pol["color"] == 100
        assert pol["oper-state"] == "DOWN"
        assert pol["transition-count"] == 0
        assert pol["down-time"] == "2026-04-01T10:21:07+00:00"

    def test_database_policy_candidate_paths(self):
        """Validate database candidate-path with segment-lists."""
        result = self._parse()
        pol = result["policies"]["2.2.2.2 100"]
        assert "candidate-paths" in pol
        cps = pol["candidate-paths"]
        assert len(cps) == 1

        cp_key = "LOCAL:0:0.0.0.0:10"
        assert cp_key in cps

        cp = cps[cp_key]
        assert cp["protocol-origin"] == "LOCAL"
        assert cp["originator"] == "0:0.0.0.0"
        assert cp["discriminator"] == 10
        assert cp["preference"] == 200
        assert cp["type"] == "EXPLICIT_SEGMENT_LIST"
        assert cp["best-candidate-path"] is False
        assert cp["valid"] is False

        assert "segment-lists" in cp
        assert len(cp["segment-lists"]) == 1
        sl = cp["segment-lists"][0]
        assert sl["index"] == 2
        assert sl["name"] == "sl1"
        assert sl["valid"] is False
