from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_version import ShowVersion


# Use the local ArcOS test_samples directory within this repo.
SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_version_sample():
    """Validate parsing of ArcOS show version using local version.json sample."""

    sample_file = SAMPLES_DIR / "version.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowVersion(device="dummy")
    result = parser.cli(output=output)

    assert isinstance(result, dict)
    assert "version" in result

    ver = result["version"]

    assert ver["platform"] == "Virtual"
    assert ver["software"] == "Arrcus ArcOS"
    assert ver["version"] == "8.2.1A"
    assert "uptime" in ver
