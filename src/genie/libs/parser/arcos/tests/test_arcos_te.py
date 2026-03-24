"""Unit tests for ArcOS TE parsers."""

from pathlib import Path
import pytest

from genie.libs.parser.arcos.show_te import ShowTeAdminGroup

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_te_admin_group():
    """Validate parsing of ArcOS show te admin-group using local sample JSON."""

    sample_file = SAMPLES_DIR / "te_admin_group.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowTeAdminGroup(device="dummy")
    result = parser.cli(output=output)

    # Top-level structure
    assert isinstance(result, dict)
    assert "network-instance" in result
    assert "default" in result["network-instance"]

    ni_default = result["network-instance"]["default"]
    assert "admin-groups" in ni_default

    admin_groups = ni_default["admin-groups"]

    # Verify all 4 admin-groups parsed
    assert len(admin_groups) == 4
    assert "INTRA-COUNTRY" in admin_groups
    assert "green" in admin_groups
    assert "red" in admin_groups
    assert "yellow" in admin_groups

    # Verify specific values
    assert admin_groups["INTRA-COUNTRY"]["name"] == "INTRA-COUNTRY"
    assert admin_groups["INTRA-COUNTRY"]["bit-position"] == 1

    assert admin_groups["green"]["name"] == "green"
    assert admin_groups["green"]["bit-position"] == 2

    assert admin_groups["red"]["name"] == "red"
    assert admin_groups["red"]["bit-position"] == 11

    assert admin_groups["yellow"]["name"] == "yellow"
    assert admin_groups["yellow"]["bit-position"] == 3


def test_show_te_admin_group_empty():
    """Validate parser raises SchemaEmptyParserError on empty output."""
    from genie.metaparser.util.exceptions import SchemaEmptyParserError

    parser = ShowTeAdminGroup(device="dummy")

    with pytest.raises(SchemaEmptyParserError):
        parser.cli(output="{}")
