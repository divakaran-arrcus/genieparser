"""Unit tests for ShowIsisGlobalTimers parser."""

from pathlib import Path
import pytest

from genie.libs.parser.arcos.show_isis import ShowIsisGlobalTimers

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_isis_global_timers_sample():
    """Validate parsing of ArcOS show isis global timers using local sample JSON."""

    sample_file = SAMPLES_DIR / "show_isis_global_timers.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisGlobalTimers(device="dummy")
    result = parser.cli(output=output)

    # Top-level structure
    assert isinstance(result, dict)
    assert "network-instance" in result

    ni = result["network-instance"]
    assert "default" in ni
    assert "isis" in ni["default"]
    assert "default" in ni["default"]["isis"]

    instance = ni["default"]["isis"]["default"]
    assert "timers" in instance

    timers = instance["timers"]

    # LSP timers
    assert timers["lsp-lifetime-interval"] == 1200
    assert timers["lsp-refresh-interval"] == 600
    assert timers["lsp-flood-delay-adj-up"] == 0

    # SPF timers
    assert "spf" in timers
    spf = timers["spf"]
    assert spf["spf-hold-interval"] == "5000"
    assert spf["spf-first-interval"] == "50"
    assert spf["spf-second-interval"] == "200"
    assert spf["spf-mla-interval"] == "25"


def test_show_isis_global_timers_empty_output():
    """Parser returns empty structure for empty/invalid output."""

    parser = ShowIsisGlobalTimers(device="dummy")
    result = parser.cli(output="{}")

    assert isinstance(result, dict)
    assert "network-instance" in result
    # No timers key when no data
    assert "timers" not in result["network-instance"]["default"]["isis"]["default"]


def test_show_isis_global_timers_no_spf():
    """Parser handles output with LSP timers only (no SPF block)."""

    output = """{
      "data": {
        "openconfig-network-instance:network-instances": {
          "network-instance": [
            {
              "name": "default",
              "protocols": {
                "protocol": [
                  {
                    "identifier": "openconfig-policy-types:ISIS",
                    "name": "default",
                    "isis": {
                      "global": {
                        "timers": {
                          "state": {
                            "lsp-lifetime-interval": 1200,
                            "lsp-refresh-interval": 600
                          }
                        }
                      }
                    }
                  }
                ]
              }
            }
          ]
        }
      }
    }"""

    parser = ShowIsisGlobalTimers(device="dummy")
    result = parser.cli(output=output)

    timers = result["network-instance"]["default"]["isis"]["default"]["timers"]
    assert timers["lsp-lifetime-interval"] == 1200
    assert timers["lsp-refresh-interval"] == 600
    assert "spf" not in timers
