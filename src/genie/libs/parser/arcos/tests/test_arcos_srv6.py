from genie.libs.parser.arcos.srv6 import ShowSrv6Config, ShowSrv6Locator


# Minimal synthetic SRv6 samples to validate parser behaviour. These are
# intentionally small and self-contained, independent of external files.

CONFIG_SAMPLE = """
{
  "data": {
    "openconfig-network-instance:network-instances": {
      "network-instance": [
        {
          "name": "default",
          "arcos-srv6:srv6": {
            "encapsulation": {
              "config": {
                "source-address": "2400:2020:0:1191::91"
              }
            },
            "locator": [
              {
                "name": "base_slice0",
                "config": {
                  "locator-node-length": 24,
                  "prefix": "2400:2020:0:1191::/64",
                  "function-length": 16,
                  "algorithm": 0
                }
              }
            ]
          }
        }
      ]
    }
  }
}
"""


LOCATOR_SAMPLE = """
{
  "data": {
    "openconfig-network-instance:network-instances": {
      "network-instance": [
        {
          "name": "default",
          "arcos-srv6:srv6": {
            "locator": [
              {
                "name": "base_slice0",
                "state": {
                  "locator-node-length": 24,
                  "prefix": "2400:2020:0:1191::/64",
                  "micro-segment-behavior-unode": true,
                  "function-length": 16,
                  "algorithm": 0
                }
              }
            ]
          }
        }
      ]
    }
  }
}
"""


def test_show_srv6_config_minimal():
    """Validate parsing of a minimal SRv6 configuration sample."""

    parser = ShowSrv6Config(device="dummy")
    result = parser.cli(output=CONFIG_SAMPLE)

    # New structure: srv6[instance]["config"]
    assert "srv6" in result
    assert "default" in result["srv6"]

    cfg = result["srv6"]["default"].get("config", {})
    encap = cfg.get("encapsulation", {})
    assert encap.get("source_address") == "2400:2020:0:1191::91"

    locators = cfg.get("locators", {})
    assert "base_slice0" in locators
    loc = locators["base_slice0"]
    assert loc["name"] == "base_slice0"
    assert loc["locator_node_length"] == 24
    assert loc["prefix"] == "2400:2020:0:1191::/64"
    assert loc["function_length"] == 16
    assert loc["algorithm"] == 0


def test_show_srv6_locator_minimal():
    """Validate parsing of a minimal SRv6 locator state sample."""

    parser = ShowSrv6Locator(device="dummy")
    result = parser.cli(output=LOCATOR_SAMPLE)

    assert "srv6" in result
    nis = result["srv6"].get("network_instances", {})
    assert "default" in nis

    ni = nis["default"]
    locators = ni.get("locators", {})
    assert "base_slice0" in locators

    loc = locators["base_slice0"]
    assert loc["name"] == "base_slice0"
    assert loc["locator_node_length"] == 24
    assert loc["prefix"] == "2400:2020:0:1191::/64"
    assert loc["micro_segment_behavior_unode"] is True
    assert loc["function_length"] == 16
    assert loc["algorithm"] == 0
