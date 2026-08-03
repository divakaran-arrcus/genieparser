"""show_bfd.py

ArcOS parsers for the following show commands:
    * show bfd
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import ARCOS_BFD_AUGMENTS
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)

# Prefix strings to strip from keys and values
_BFD_AUG_PREFIX = f"{ARCOS_BFD_AUGMENTS}:"
_POLICY_TYPES_PREFIX = "openconfig-policy-types:"


class ShowBfdSchema(MetaParser):
    """Schema for ArcOS ``show bfd`` output."""

    schema = {
        Optional("profile"): {
            Any(): {  # profile name (e.g., "GLOBAL-150m")
                Optional("id"): str,
                Optional("enabled"): bool,
                Optional("desired-minimum-tx-interval"): Or(str, int),
                Optional("required-minimum-receive"): Or(str, int),
                Optional("detection-multiplier"): Or(str, int),
                Optional("v4-hw-offload"): bool,
                Optional("v6-hw-offload"): bool,
                Optional("dscp-value"): Or(str, int),
                Optional("peers"): {
                    Any(): {  # local-discriminator (e.g., "20")
                        Optional("local-address"): str,
                        Optional("remote-address"): str,
                        Optional("subscribed-protocols"): list,
                        Optional("session-state"): str,
                        Optional("remote-session-state"): str,
                        Optional("local-discriminator"): Or(str, int),
                        Optional("remote-discriminator"): Or(str, int),
                        Optional("remote-minimum-receive-interval"): Or(str, int),
                        Optional("transmitted-packets"): Or(str, int),
                        Optional("received-packets"): Or(str, int),
                        Optional("hw-offload-status"): bool,
                        Optional("interface"): str,
                        Optional("hw-endpoint-id"): Or(str, int),
                        Optional("network-instance"): str,
                        Optional("local-desired-minimum-tx-interval"): Or(str, int),
                        Optional("local-required-minimum-receive"): Or(str, int),
                        Optional("local-detection-multiplier"): Or(str, int),
                        Optional("negotiated-tx-interval"): Or(str, int),
                        Optional("negotiated-rx-interval"): Or(str, int),
                        Optional("session-type"): str,
                        Optional("session-up-time"): str,
                    }
                },
            }
        }
    }


class ShowBfd(ShowBfdSchema):
    """Parser for ArcOS ``show bfd`` (JSON format).

    The parser expects OpenConfig JSON of the form::

        data["openconfig-bfd:bfd"]["interfaces"]["interface"][]

    Each interface entry represents a BFD profile with optional peer
    sessions.  Namespace prefixes (``arcos-openconfig-bfd-augments:``,
    ``openconfig-policy-types:``) are stripped from keys and values.

    When no explicit output is provided, the parser runs::

        show bfd | display json | nomore
    """

    cli_command = "show bfd"

    def cli(self, output: TypeOptional[TypeAny] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowBfd: empty output")

        parsed_json = load_json_robust(output)

        result = self._parse_bfd(parsed_json)

        if not result:
            raise SchemaEmptyParserError("No BFD data found in output")

        return result

    def _parse_bfd(self, json_data: Dict) -> Dict[str, TypeAny]:
        """Extract BFD profiles and peers from OpenConfig JSON."""
        data = json_data.get("data", {})
        bfd = data.get("openconfig-bfd:bfd", {})
        interfaces = bfd.get("interfaces", {})
        interface_list = interfaces.get("interface", [])

        if not interface_list:
            return {}

        profiles: Dict[str, TypeAny] = {}

        for iface in interface_list:
            profile_id = iface.get("id")
            if not profile_id:
                continue

            profile: Dict[str, TypeAny] = {}

            # Flatten state fields, stripping augment prefix from keys
            state = iface.get("state", {})
            for key, value in state.items():
                clean_key = _strip_augment_prefix(key)
                profile[clean_key] = value

            # Parse peers if present
            peers_container = iface.get("peers", {})
            peer_list = peers_container.get("peer", [])

            if peer_list:
                peers: Dict[str, TypeAny] = {}
                for peer in peer_list:
                    disc = str(peer.get("local-discriminator", ""))
                    if not disc:
                        continue

                    peer_data: Dict[str, TypeAny] = {}
                    peer_state = peer.get("state", {})

                    for key, value in peer_state.items():
                        # Skip the nested async dict — we flatten it
                        if key == "async":
                            async_data = value if isinstance(value, dict) else {}
                            for akey, aval in async_data.items():
                                peer_data[akey] = aval
                            continue

                        clean_key = _strip_augment_prefix(key)

                        # Strip namespace prefixes from values
                        if clean_key == "subscribed-protocols" and isinstance(value, list):
                            peer_data[clean_key] = [
                                _strip_value_prefix(v) for v in value
                            ]
                        elif clean_key == "session-type" and isinstance(value, str):
                            peer_data[clean_key] = _strip_value_prefix(value)
                        else:
                            peer_data[clean_key] = value

                    peers[disc] = peer_data

                profile["peers"] = peers

            profiles[profile_id] = profile

        return {"profile": profiles}


def _strip_augment_prefix(key: str) -> str:
    """Remove ``arcos-openconfig-bfd-augments:`` prefix from a key."""
    if key.startswith(_BFD_AUG_PREFIX):
        return key[len(_BFD_AUG_PREFIX):]
    return key


def _strip_value_prefix(value: str) -> str:
    """Remove known namespace prefixes from a value string."""
    if value.startswith(_POLICY_TYPES_PREFIX):
        return value[len(_POLICY_TYPES_PREFIX):]
    if value.startswith(_BFD_AUG_PREFIX):
        return value[len(_BFD_AUG_PREFIX):]
    return value
