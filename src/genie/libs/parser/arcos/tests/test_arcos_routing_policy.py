from __future__ import annotations

import pytest
from pathlib import Path

from genie.libs.parser.arcos.show_routing_policy import (
    ShowRoutingPolicyConfig,
    ShowRoutingPolicyDefinedSets,
    ShowRoutingPolicyPolicyDefinition,
)


SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS routing-policy samples directory not available",
)


def _load_sample(name: str) -> str:
    sample_file = SAMPLES_DIR / name
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")
    return sample_file.read_text()


def test_show_running_config_routing_policy_from_config() -> None:
    """Validate combined parsing of defined-sets and policy-definitions
    from a running-config style JSON sample.
    """

    output = _load_sample("routing_policy_config.json")

    parser = ShowRoutingPolicyConfig(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    rp = result.get("routing-policy", {})

    # Defined-sets should be present and contain known prefix-sets
    defined_sets = rp.get("defined-sets", {})
    prefix_sets = defined_sets.get("prefix-sets", {})
    assert "906" in prefix_sets
    assert "__IPV4_MARTIAN_PREFIX_SET__" in prefix_sets
    assert "__IPV6_MARTIAN_PREFIX_SET__" in prefix_sets

    # Policy-definitions should be present and contain known policies
    policy_defs = rp.get("policy-definitions", {})
    assert "906" in policy_defs
    assert "set_redis_level" in policy_defs
    assert "v6_L2_to_L1" in policy_defs

    # Spot-check one statement wiring to ensure the merge is correct
    policy_906 = policy_defs["906"]
    stmt_50 = policy_906["statements"]["50"]
    actions_50 = stmt_50.get("actions", {})
    assert actions_50.get("reject-route") is True


def test_show_routing_policy_defined_sets_state_sample():
    """Validate parsing of routing-policy defined-sets (state variant)."""

    output = _load_sample("routing_policy_defined_set.json")

    parser = ShowRoutingPolicyDefinedSets(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    rp = result.get("routing-policy", {}).get("defined-sets", {})

    prefix_sets = rp.get("prefix-sets", {})

    # Basic presence checks
    assert "906" in prefix_sets
    assert "__IPV4_MARTIAN_PREFIX_SET__" in prefix_sets
    assert "__IPV6_MARTIAN_PREFIX_SET__" in prefix_sets
    assert "leaf_deny" in prefix_sets
    assert "v6_L2_to_L1" in prefix_sets

    # Sample checks for a regular prefix-set
    ps_906 = prefix_sets["906"]
    assert ps_906["name"] == "906"
    assert any(
        p["ip-prefix"] == "2400:2020:0:900::/56" and p["masklength-range"] == "exact"
        for p in ps_906["prefixes"]
    )

    # Martian sets should be flagged
    ipv4_martian = prefix_sets["__IPV4_MARTIAN_PREFIX_SET__"]
    assert ipv4_martian["name"] == "__IPV4_MARTIAN_PREFIX_SET__"
    assert ipv4_martian.get("is-martian") is True
    assert any(
        p["ip-prefix"] == "0.0.0.0/8" and p["masklength-range"] == "8..32"
        for p in ipv4_martian["prefixes"]
    )

    ipv6_martian = prefix_sets["__IPV6_MARTIAN_PREFIX_SET__"]
    assert ipv6_martian["name"] == "__IPV6_MARTIAN_PREFIX_SET__"
    assert ipv6_martian.get("is-martian") is True
    assert any(
        p["ip-prefix"] == "::/128" and p["masklength-range"] == "exact"
        for p in ipv6_martian["prefixes"]
    )

    # String-set
    string_sets = rp.get("string-sets", {})
    assert "abc" in string_sets
    ss = string_sets["abc"]
    assert ss["name"] == "abc"
    assert ss["strings"][0]["value"] == "xyz"
    assert ss["strings"][0]["match-type"] == "EXACT"

    # Tag-set
    tag_sets = rp.get("tag-sets", {})
    assert "pqr" in tag_sets
    ts = tag_sets["pqr"]
    assert ts["name"] == "pqr"
    assert ts["tags"] == [55]

    # Next-hop-set
    next_hop_sets = rp.get("next-hop-sets", {})
    assert "abc" in next_hop_sets
    nh = next_hop_sets["abc"]
    assert nh["name"] == "abc"
    assert nh["addresses"] == ["10.20.0.0"]


def test_show_routing_policy_defined_sets_config_sample():
    """Validate parsing of routing-policy defined-sets (config variant)."""

    output = _load_sample("routing_policy_config.json")

    parser = ShowRoutingPolicyDefinedSets(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    rp = result.get("routing-policy", {}).get("defined-sets", {})

    prefix_sets = rp.get("prefix-sets", {})

    # Expect the same key set as in the state variant
    for name in ("906", "__IPV4_MARTIAN_PREFIX_SET__", "__IPV6_MARTIAN_PREFIX_SET__"):
        assert name in prefix_sets

    ps_906 = prefix_sets["906"]
    assert ps_906["name"] == "906"
    # Ensure at least one known prefix was normalized correctly from config.*
    assert any(
        p["ip-prefix"] == "2400:2020:0:900::/56" and p["masklength-range"] == "exact"
        for p in ps_906["prefixes"]
    )

    # Next-hop-set from running-config
    next_hop_sets = rp.get("next-hop-sets", {})
    assert "abc" in next_hop_sets
    nh = next_hop_sets["abc"]
    assert nh["name"] == "abc"
    assert nh["addresses"] == ["10.20.0.0/24"]


def test_show_routing_policy_policy_definition_from_config() -> None:
    output = _load_sample("routing_policy_config.json")

    parser = ShowRoutingPolicyPolicyDefinition(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    rp = result.get("routing-policy", {})
    policy_defs = rp.get("policy-definitions", {})

    assert "906" in policy_defs
    assert "set_redis_level" in policy_defs
    assert "v6_L2_to_L1" in policy_defs
    assert "abc" in policy_defs

    policy_906 = policy_defs["906"]
    statements_906 = policy_906["statements"]
    stmt_50 = statements_906["50"]

    conditions_50 = stmt_50.get("conditions", {})
    match_prefix_set_50 = conditions_50.get("match-prefix-set", {})
    assert match_prefix_set_50.get("prefix-set") == "906"
    assert match_prefix_set_50.get("match-set-options") == "ANY"

    actions_50 = stmt_50.get("actions", {})
    assert actions_50.get("reject-route") is True
    assert actions_50.get("accept-route") is not True

    policy_set_redis = policy_defs["set_redis_level"]
    statements_set_redis = policy_set_redis["statements"]
    stmt_10 = statements_set_redis["10"]

    actions_10 = stmt_10.get("actions", {})
    assert actions_10.get("accept-route") is True
    igp_10 = actions_10.get("igp-actions", {})
    isis_10 = igp_10.get("isis-actions", {})
    assert isis_10.get("set-level") == 2

    policy_v6 = policy_defs["v6_L2_to_L1"]
    statements_v6 = policy_v6["statements"]
    stmt_20 = statements_v6["20"]

    conditions_20 = stmt_20.get("conditions", {})
    match_prefix_set_20 = conditions_20.get("match-prefix-set", {})
    assert match_prefix_set_20.get("prefix-set") == "v6_L2_to_L1"

    actions_20 = stmt_20.get("actions", {})
    assert actions_20.get("accept-route") is True
    igp_20 = actions_20.get("igp-actions", {})
    assert igp_20.get("set-tag") == 69


def test_show_routing_policy_policy_definition_state_match_sets() -> None:
    """Validate match-*set conditions from a state-based sample."""

    output = _load_sample("routing_policy_policy_definition.json")

    parser = ShowRoutingPolicyPolicyDefinition(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    rp = result.get("routing-policy", {})
    policy_defs = rp.get("policy-definitions", {})

    assert "906" in policy_defs
    policy_906 = policy_defs["906"]
    statements_906 = policy_906["statements"]
    stmt_50 = statements_906["50"]

    conditions_50 = stmt_50.get("conditions", {})

    # Match-prefix-set
    mps = conditions_50.get("match-prefix-set", {})
    assert mps.get("prefix-set") == "906"
    assert mps.get("match-set-options") == "ANY"

    # Match-tag-set
    mts = conditions_50.get("match-tag-set", {})
    assert mts.get("match-set-options") == "ANY"

    # Match-next-hop-set
    mnh = conditions_50.get("match-next-hop-set", {})
    assert mnh.get("match-set-options") == "ANY"

    # State sample focuses on match-*set conditions for policy 906 only
