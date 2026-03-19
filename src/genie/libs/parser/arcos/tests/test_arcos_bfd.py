"""Unit tests for ArcOS BFD parser."""

from pathlib import Path

import pytest

from genie.libs.parser.arcos.show_bfd import ShowBfd

SAMPLES_DIR = Path(__file__).parent / "test_samples"

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR.exists(),
    reason="ArcOS local test_samples directory not available",
)


def test_show_bfd_profiles_count():
    """Validate that all 7 BFD profiles are parsed."""
    sample_file = SAMPLES_DIR / "bfd.json"
    if not sample_file.exists():
        pytest.skip(f"Sample file not found: {sample_file}")

    output = sample_file.read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    assert "profile" in result
    profiles = result["profile"]
    assert len(profiles) == 7
    expected_names = {
        "GLOBAL", "GLOBAL-1000m", "GLOBAL-100m", "GLOBAL-150m",
        "GLOBAL-200m", "GLOBAL-250m", "GLOBAL-500m-5x",
    }
    assert set(profiles.keys()) == expected_names


def test_show_bfd_profile_fields():
    """Validate profile-level fields are correctly parsed."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    profile = result["profile"]["GLOBAL-150m"]
    assert profile["id"] == "GLOBAL-150m"
    assert profile["enabled"] is True
    assert profile["desired-minimum-tx-interval"] == 150
    assert profile["required-minimum-receive"] == 150
    assert profile["detection-multiplier"] == 3
    assert profile["v4-hw-offload"] is True
    assert profile["v6-hw-offload"] is True
    assert profile["dscp-value"] == 48


def test_show_bfd_profile_no_peers():
    """Profiles without peers should not have a peers key."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    assert "peers" not in result["profile"]["GLOBAL"]
    assert "peers" not in result["profile"]["GLOBAL-250m"]


def test_show_bfd_peers_150m():
    """Validate GLOBAL-150m has 2 peers with correct discriminators."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    peers = result["profile"]["GLOBAL-150m"]["peers"]
    assert len(peers) == 2
    assert "20" in peers
    assert "24" in peers


def test_show_bfd_peers_200m():
    """Validate GLOBAL-200m has 2 peers with correct discriminators."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    peers = result["profile"]["GLOBAL-200m"]["peers"]
    assert len(peers) == 2
    assert "12" in peers
    assert "16" in peers


def test_show_bfd_peer_fields():
    """Validate peer session fields are correctly parsed."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    peer = result["profile"]["GLOBAL-150m"]["peers"]["20"]
    assert peer["local-address"] == "191.168.7.1"
    assert peer["remote-address"] == "191.168.7.0"
    assert peer["session-state"] == "UP"
    assert peer["remote-session-state"] == "UP"
    assert peer["local-discriminator"] == "20"
    assert peer["remote-discriminator"] == "24"
    assert peer["remote-minimum-receive-interval"] == 150
    assert peer["hw-offload-status"] is True
    assert peer["interface"] == "swp19"
    assert peer["network-instance"] == "default"
    assert peer["hw-endpoint-id"] == 20
    assert peer["local-desired-minimum-tx-interval"] == 150
    assert peer["local-required-minimum-receive"] == 150
    assert peer["local-detection-multiplier"] == 3
    assert peer["negotiated-tx-interval"] == 150
    assert peer["negotiated-rx-interval"] == 450
    assert peer["session-up-time"] == "0d 02:07:58"


def test_show_bfd_async_flattened():
    """Validate async counters are flattened into peer dict."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    peer = result["profile"]["GLOBAL-150m"]["peers"]["20"]
    assert peer["transmitted-packets"] == "51086"
    assert peer["received-packets"] == "51091"


def test_show_bfd_namespace_stripping():
    """Validate namespace prefixes are stripped from keys and values."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    # No augment prefix in profile keys
    profile = result["profile"]["GLOBAL-150m"]
    assert "arcos-openconfig-bfd-augments:v4-hw-offload" not in profile
    assert "v4-hw-offload" in profile

    # No augment prefix in peer keys
    peer = profile["peers"]["20"]
    assert "arcos-openconfig-bfd-augments:interface" not in peer
    assert "interface" in peer

    # subscribed-protocols values stripped
    assert peer["subscribed-protocols"] == ["ISIS"]

    # session-type value stripped
    assert peer["session-type"] == "BFD_SESSION_TYPE_UDP_IPV4"


def test_show_bfd_multihop_session_type():
    """Validate multi-hop session type is correctly stripped."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    peer = result["profile"]["GLOBAL-200m"]["peers"]["12"]
    assert peer["session-type"] == "BFD_SESSION_TYPE_MULTI_HOP_UDP_IPV4"
    assert peer["subscribed-protocols"] == ["BGP"]


def test_show_bfd_500m_5x_multiplier():
    """Validate GLOBAL-500m-5x has detection-multiplier of 5."""
    output = (SAMPLES_DIR / "bfd.json").read_text()
    parser = ShowBfd(device="dummy")
    result = parser.cli(output=output)

    profile = result["profile"]["GLOBAL-500m-5x"]
    assert profile["detection-multiplier"] == 5
    assert profile["desired-minimum-tx-interval"] == 500
