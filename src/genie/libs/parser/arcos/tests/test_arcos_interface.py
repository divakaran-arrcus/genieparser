import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_interface import ShowInterface


# Default location of ArcOS golden samples from the local arrcus_pyats repo.
# Can be overridden by setting ARCOS_PARSER_SAMPLES_DIR.
SAMPLES_DIR = Path(
    os.environ.get(
        "ARCOS_PARSER_SAMPLES_DIR",
        "/Users/divakaran/arrcus_workspace/isis_pyats/arrcus-pyats/arrcus_pyats/tests/test_samples",
    )
)

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS golden samples directory not available",
)


def test_show_interface_loopback_sample():
    """Validate parsing of a loopback interface sample JSON."""

    sample_file = SAMPLES_DIR / "interface_loopback.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowInterface(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "loopback0" in result

    intf = result["loopback0"]

    assert intf["name"] == "loopback0"
    assert intf["mtu"] == 9000
    assert intf["oper_status"] == "UP"
    assert intf["enabled"] is True

    # At least one IPv6 address with expected prefix length
    ipv6 = intf.get("ipv6_addresses", {})
    assert "1::1" in ipv6
    assert ipv6["1::1"]["prefix_length"] == 128
