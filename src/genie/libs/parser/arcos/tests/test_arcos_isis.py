import os
from pathlib import Path

import pytest

from genie.libs.parser.arcos.isis import ShowIsisAdjacency, ShowIsisLsp


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


def test_show_isis_adjacency_sample():
    """Validate parsing of a basic ISIS adjacency sample."""

    sample_file = SAMPLES_DIR / "isis_adjacency.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisAdjacency(device="dummy")
    result = parser.cli(adj_router=None, output=output)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    neighbors = result["isis"]["default"].get("neighbors", {})
    assert "rtr1" in neighbors

    adj = neighbors["rtr1"]
    assert adj["interface"] == "swp1"
    assert adj["state"] == "UP"
    assert adj["neighbor-ipv4-address"] == "10.20.0.10"
    assert adj["neighbor-circuit-type"] == "LEVEL_2"
    assert adj["adjacency-type"] == "LEVEL_2"
    assert adj.get("usable") is True


def test_show_isis_lsp_sample():
    """Validate parsing of an ISIS LSP database sample."""

    sample_file = SAMPLES_DIR / "isis_lsp.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()

    parser = ShowIsisLsp(device="dummy")
    result = parser.cli(lsp_id=None, output=output)

    assert isinstance(result, dict)
    assert "isis" in result and "default" in result["isis"]

    database = result["isis"]["default"].get("database", {})
    assert "rtr1.00-00" in database
    assert "rtr2.00-00" in database

    lsp = database["rtr1.00-00"]
    assert lsp["lsp-id"] == "rtr1.00-00"
    assert lsp["sequence"] == 151
    assert lsp["checksum"] == 12778

    # TLV-derived information
    tlvs = lsp.get("tlvs", {})
    # For LSP rtr1.00-00 the hostname in the sample is 'rtr1'
    assert tlvs.get("hostname") == "rtr1"

    # Extended IPv4 reachability for 1.1.1.1/32 on rtr1.00-00
    ext4 = lsp.get("extended_ipv4_reachability", {})
    assert "1.1.1.1/32" in ext4
    pfx4 = ext4["1.1.1.1/32"]
    assert pfx4["ip_prefix"] == "1.1.1.1"
    assert pfx4["prefix_len"] == 32
    assert pfx4["metric"] == 10

    # MT IPv6 reachability for 2400:2020:0:1191::91/128 on rtr1.00-00
    mt6 = lsp.get("mt_ipv6_reachability", {})
    assert "2400:2020:0:1191::91/128" in mt6
    pfx6 = mt6["2400:2020:0:1191::91/128"]
    assert pfx6["ip_prefix"] == "2400:2020:0:1191::91"
    assert pfx6["prefix_len"] == 128
    assert pfx6["metric"] == 10
    assert pfx6["mt-id"] == 2

    # Also verify that LSP rtr2.00-00 contains prefix 2.2.2.2/32 in its
    # extended IPv4 reachability, and MT IPv6 2400:2020:0:2291::91/128,
    # as per the golden sample.
    lsp2 = database["rtr2.00-00"]
    ext4_lsp2 = lsp2.get("extended_ipv4_reachability", {})
    assert "2.2.2.2/32" in ext4_lsp2
    pfx4_lsp2 = ext4_lsp2["2.2.2.2/32"]
    assert pfx4_lsp2["ip_prefix"] == "2.2.2.2"
    assert pfx4_lsp2["prefix_len"] == 32
    assert pfx4_lsp2["metric"] == 10

    mt6_lsp2 = lsp2.get("mt_ipv6_reachability", {})
    assert "2400:2020:0:2291::91/128" in mt6_lsp2
    pfx6_lsp2 = mt6_lsp2["2400:2020:0:2291::91/128"]
    assert pfx6_lsp2["ip_prefix"] == "2400:2020:0:2291::91"
    assert pfx6_lsp2["prefix_len"] == 128
    assert pfx6_lsp2["metric"] == 10
    assert pfx6_lsp2["mt-id"] == 2
