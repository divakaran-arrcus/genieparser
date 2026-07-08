import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_srv6 import (
    ShowSrv6Config,
    ShowSrv6Locator,
    ShowSrv6LocalSids,
)


SAMPLES_DIR = Path(
    os.environ.get("ARCOS_PARSER_SAMPLES_DIR")
    or (Path(__file__).parent / "test_samples")
)

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(), reason="ArcOS SRv6 samples directory not available"
)


def test_show_srv6_config_minimal():
    """Validate parsing of a minimal SRv6 configuration sample."""

    sample_file = SAMPLES_DIR / "srv6_config.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6Config(device="dummy")
    result = parser.cli(output=output)

    # New structure: network_instances[instance]["srv6"]["config"]
    assert "network-instances" in result
    assert "default" in result["network-instances"]
    ni = result["network-instances"]["default"]
    assert "srv6" in ni

    cfg = ni["srv6"].get("config", {})
    encap = cfg.get("encapsulation", {})
    assert encap.get("source-address") == "2400:2020:0:1191::91"

    locators = cfg.get("locators", {})
    # The sample includes three locators: base_slice0, base_slice131, base_slice132
    assert "base_slice0" in locators
    assert "base_slice131" in locators
    assert "base_slice132" in locators

    loc0 = locators["base_slice0"]
    assert loc0["name"] == "base_slice0"
    assert loc0["locator-node-length"] == 24
    assert loc0["prefix"] == "2400:2020:0:1191::/64"
    assert loc0["function-length"] == 16
    # base_slice0 in the config sample has no explicit algorithm field

    loc131 = locators["base_slice131"]
    assert loc131["name"] == "base_slice131"
    assert loc131["prefix"] == "2400:2020:31:1191::/64"
    assert loc131["algorithm"] == 131

    loc132 = locators["base_slice132"]
    assert loc132["name"] == "base_slice132"
    assert loc132["prefix"] == "2400:2020:32:1191::/64"
    assert loc132["algorithm"] == 132


def test_show_srv6_locator_minimal():
    """Validate parsing of a minimal SRv6 locator state sample."""

    sample_file = SAMPLES_DIR / "srv6_locator.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6Locator(device="dummy")
    result = parser.cli(output=output)

    assert "network-instances" in result
    assert "default" in result["network-instances"]

    ni = result["network-instances"]["default"]
    assert "srv6" in ni
    locators = ni["srv6"].get("locators", {})
    # The locator state sample includes base_slice0, base_slice131, base_slice132
    assert "base_slice0" in locators
    assert "base_slice131" in locators
    assert "base_slice132" in locators

    loc0 = locators["base_slice0"]
    assert loc0["name"] == "base_slice0"
    assert loc0["locator-node-length"] == 24
    assert loc0["prefix"] == "2400:2020:0:1191::/64"
    assert loc0["micro-segment-behavior-unode"] is False
    assert loc0["function-length"] == 16
    assert loc0["algorithm"] == 0

    loc131 = locators["base_slice131"]
    assert loc131["algorithm"] == 131
    loc132 = locators["base_slice132"]
    assert loc132["algorithm"] == 132


def test_show_srv6_config_with_instance_parameter():
    """Validate ShowSrv6Config accepts instance parameter."""

    sample_file = SAMPLES_DIR / "srv6_config.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6Config(device="dummy")
    # Test with explicit instance parameter (output provided, so no command executed)
    result = parser.cli(instance="default", output=output)

    assert "network-instances" in result
    assert "default" in result["network-instances"]


def test_show_srv6_locator_with_instance_parameter():
    """Validate ShowSrv6Locator accepts instance parameter."""

    sample_file = SAMPLES_DIR / "srv6_locator.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6Locator(device="dummy")
    # Test with explicit instance parameter (output provided, so no command executed)
    result = parser.cli(instance="default", output=output)

    assert "network-instances" in result
    assert "default" in result["network-instances"]


def test_show_srv6_config_instance_validation():
    """Validate instance parameter is validated for invalid characters."""

    parser = ShowSrv6Config(device="dummy")

    with pytest.raises(ValueError, match="Invalid characters"):
        parser.cli(instance="default; rm -rf /")


def test_show_srv6_locator_instance_validation():
    """Validate instance parameter is validated for invalid characters."""

    parser = ShowSrv6Locator(device="dummy")

    with pytest.raises(ValueError, match="Invalid characters"):
        parser.cli(instance="default; rm -rf /")


def test_show_srv6_local_sids_golden():
    """Validate parsing of the golden SRv6 local-sids sample (live capture)."""

    sample_file = SAMPLES_DIR / "srv6_local_sids.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6LocalSids(device="dummy")
    result = parser.cli(output=output)

    assert "network_instance" in result
    assert "default" in result["network_instance"]

    ni = result["network_instance"]["default"]
    local_sids = ni.get("local_sids", {})

    # Golden sample has 15 local-SIDs: 3 plain End (one per locator/algo)
    # and 12 End.X (4 adjacency SIDs per locator/algo).
    assert len(local_sids) == 15

    # Plain End SID (sidmgr-owned) — no sid_paths key.
    end_sid = local_sids["fcbb:bb00:1:1::/64"]
    assert end_sid["behavior"] == "END_PSP_USD"
    assert end_sid["locator_name"] == "LOC_R1_ALG128"
    assert end_sid["client_name"] == "sidmgr"
    assert "sid_paths" not in end_sid

    # End.X SID (isis-owned) — behavior prefix stripped, sid_paths present.
    endx_sid = local_sids["fcbb:bb00:1:8012::/64"]
    assert endx_sid["behavior"] == "END_X_PSP_USD"
    assert endx_sid["locator_name"] == "LOC_R1_ALG128"
    assert endx_sid["client_name"] == "isis-default@defaul"
    assert endx_sid["sid_paths"] == [
        {
            "next_hop_address": "fe80::b436:c5ff:fe66:85ed",
            "interface": "swp1",
        }
    ]

    # All 15 SIDs have module-prefix-stripped, bare-token behaviors.
    for sid, entry in local_sids.items():
        assert ":" not in entry["behavior"], (
            f"behavior for {sid} still has a module prefix: {entry['behavior']}"
        )


def test_show_srv6_local_sids_with_instance_parameter():
    """Validate ShowSrv6LocalSids accepts instance parameter."""

    sample_file = SAMPLES_DIR / "srv6_local_sids.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6LocalSids(device="dummy")
    result = parser.cli(instance="default", output=output)

    assert "network_instance" in result
    assert "default" in result["network_instance"]


def test_show_srv6_local_sids_instance_validation():
    """Validate instance parameter is validated for invalid characters."""

    parser = ShowSrv6LocalSids(device="dummy")

    with pytest.raises(ValueError, match="Invalid characters"):
        parser.cli(instance="default; rm -rf /")


def test_show_srv6_local_sids_usid_behaviors():
    """Validate parsing of uSID local-sid behaviors (generic prefix-strip).

    Regression coverage for the generic ``behavior`` module-prefix strip:
    uSID flavors (UN_SL_*, UA_SX_*) must come out bare, same as the
    non-uSID END_PSP_USD/END_X_PSP_USD flavors covered by the golden
    sample.
    """

    sample_file = SAMPLES_DIR / "srv6_local_sids_usid.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6LocalSids(device="dummy")
    result = parser.cli(output=output)

    ni = result["network_instance"]["default"]
    local_sids = ni.get("local_sids", {})
    assert len(local_sids) == 2

    # uSID plain End (UN_SL_*) — no sid_paths key.
    un_sid = local_sids["fc00:0:1:1::/48"]
    assert un_sid["behavior"] == "UN_SL_END_PSP_USD"
    assert un_sid["locator_name"] == "LOC_USID_ALG128"
    assert un_sid["client_name"] == "sidmgr"
    assert "sid_paths" not in un_sid

    # uSID End.X (UA_SX_*) — behavior prefix stripped, sid_paths present.
    ua_sid = local_sids["fc00:0:1:f001::/48"]
    assert ua_sid["behavior"] == "UA_SX_END_X_PSP_USD"
    assert ua_sid["locator_name"] == "LOC_USID_ALG128"
    assert ua_sid["client_name"] == "isis-default@defaul"
    assert ua_sid["sid_paths"] == [
        {
            "next_hop_address": "fe80::b436:c5ff:fe66:85ed",
            "interface": "swp1",
        }
    ]

    for sid, entry in local_sids.items():
        assert ":" not in entry["behavior"], (
            f"behavior for {sid} still has a module prefix: {entry['behavior']}"
        )


def test_show_srv6_local_sids_single_bare_dict():
    """Validate the H1 guard: a single local-sid rendered as a bare dict.

    When a network-instance has exactly one local-SID, ArcOS may emit
    "local-sid" as a single dict rather than a single-element list (the
    same YANG list-collapsing quirk already guarded for "sid-path").
    Without the guard, ``for entry in sid_list`` would iterate the dict's
    keys (strings) and ``entry.get("sid")`` would raise AttributeError.
    """

    sample_file = SAMPLES_DIR / "srv6_local_sids_usid_single.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowSrv6LocalSids(device="dummy")
    # Must not raise AttributeError.
    result = parser.cli(output=output)

    ni = result["network_instance"]["default"]
    local_sids = ni.get("local_sids", {})
    assert len(local_sids) == 1

    sid_entry = local_sids["fc00:0:1:1::/48"]
    assert sid_entry["behavior"] == "UN_SL_END_PSP_USD"
    assert sid_entry["locator_name"] == "LOC_USID_ALG128"
    assert sid_entry["client_name"] == "sidmgr"
