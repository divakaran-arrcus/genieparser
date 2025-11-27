import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_srv6 import ShowSrv6Config, ShowSrv6Locator


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

    # New structure: srv6[instance]["config"]
    assert "srv6" in result
    assert "default" in result["srv6"]

    cfg = result["srv6"]["default"].get("config", {})
    encap = cfg.get("encapsulation", {})
    assert encap.get("source_address") == "2400:2020:0:1191::91"

    locators = cfg.get("locators", {})
    # The sample includes three locators: base_slice0, base_slice131, base_slice132
    assert "base_slice0" in locators
    assert "base_slice131" in locators
    assert "base_slice132" in locators

    loc0 = locators["base_slice0"]
    assert loc0["name"] == "base_slice0"
    assert loc0["locator_node_length"] == 24
    assert loc0["prefix"] == "2400:2020:0:1191::/64"
    assert loc0["function_length"] == 16
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

    assert "srv6" in result
    nis = result["srv6"].get("network_instances", {})
    assert "default" in nis

    ni = nis["default"]
    locators = ni.get("locators", {})
    # The locator state sample includes base_slice0, base_slice131, base_slice132
    assert "base_slice0" in locators
    assert "base_slice131" in locators
    assert "base_slice132" in locators

    loc0 = locators["base_slice0"]
    assert loc0["name"] == "base_slice0"
    assert loc0["locator_node_length"] == 24
    assert loc0["prefix"] == "2400:2020:0:1191::/64"
    assert loc0["micro_segment_behavior_unode"] is False
    assert loc0["function_length"] == 16
    assert loc0["algorithm"] == 0

    loc131 = locators["base_slice131"]
    assert loc131["algorithm"] == 131
    loc132 = locators["base_slice132"]
    assert loc132["algorithm"] == 132
