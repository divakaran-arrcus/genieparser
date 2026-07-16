"""ArcOS Keychain parsers.

Parsers for Arrcus ArcOS Keychain commands using OpenConfig JSON format.

Supports:
  - show running-config keychain | display json | nomore
  - show running-config keychain {name} | display json | nomore
  - show keychain | display json | nomore
  - show keychain {name} | display json | nomore
"""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

log = logging.getLogger(__name__)

# OpenConfig namespace constant
OPENCONFIG_KEYCHAINS = "openconfig-keychain:keychains"
ARCOS_KEYCHAIN_AUGMENTS = "arcos-openconfig-keychain-augments"


def _strip_oc_prefix(value):
    """Strip OpenConfig type prefix from a value.

    E.g., 'openconfig-keychain-types:HMAC_SHA_1' -> 'HMAC_SHA_1'
    """
    if isinstance(value, str) and ':' in value:
        return value.split(':', 1)[1]
    return value


def _get_keychains_data(json_output: Dict) -> list:
    """Navigate to the keychain list from the JSON output.

    The JSON structure is::

        data["openconfig-keychain:keychains"]["keychain"][...]

    Returns the list of keychain entries, or empty list if not found.
    """
    data = json_output.get("data", {})
    kc_container = data.get(OPENCONFIG_KEYCHAINS, {})
    return kc_container.get("keychain", [])


# ============================================================================
# Parser 1: ShowKeychainConfig (running-config)
# ============================================================================

class ShowKeychainConfigSchema(MetaParser):
    """Schema for ArcOS keychain running configuration.

    Represents keychain configuration as returned by::

        show running-config keychain | display json | nomore
        show running-config keychain {name} | display json | nomore
    """

    schema = {
        "keychains": {
            Any(): {  # keychain name
                "name": str,
                Optional("tolerance"): int,
                Optional("keys"): {
                    Any(): {  # key-id
                        "key-id": str,
                        Optional("secret-key"): str,
                        Optional("crypto-algorithm"): str,
                        Optional("send-lifetime"): {
                            Optional("always"): bool,
                            Optional("start-time"): str,
                            Optional("end-time"): str,
                        },
                    }
                },
            }
        }
    }


class ShowKeychainConfig(ShowKeychainConfigSchema):
    """Parser for ArcOS keychain running configuration (JSON format).

    Commands::

        show running-config keychain | display json | nomore
        show running-config keychain {name} | display json | nomore
    """

    cli_command = [
        "show running-config keychain | display json | nomore",
        "show running-config keychain {name} | display json | nomore",
    ]

    def cli(self, name: TypeOptional[str] = None,
            output: TypeOptional[str] = None) -> TypeAny:
        """Parse keychain running configuration.

        Args:
            name: Optional keychain name to filter.
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ShowKeychainConfigSchema.
        """
        if output is None:
            if name:
                cmd = f"show running-config keychain {name} | display json | nomore"
            else:
                cmd = "show running-config keychain | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowKeychainConfig: empty output")

        json_output = load_json_robust(output)
        if not json_output:
            raise SchemaEmptyParserError("No JSON output or empty response")

        kc_list = _get_keychains_data(json_output)
        if not kc_list:
            raise SchemaEmptyParserError("No keychain data found")

        result = {"keychains": {}}

        for kc in kc_list:
            kc_name = kc.get("name")
            if not kc_name:
                continue

            kc_entry = {
                "name": kc_name,
            }

            # Config container
            config = kc.get("config", {})
            tolerance = config.get("tolerance")
            if tolerance is not None:
                kc_entry["tolerance"] = tolerance

            # Keys
            keys_container = kc.get("keys", {})
            key_list = keys_container.get("key", [])
            if key_list:
                keys_dict = {}
                for key_entry in key_list:
                    key_id = key_entry.get("key-id")
                    if not key_id:
                        continue

                    key_config = key_entry.get("config", {})
                    parsed_key = {
                        "key-id": str(key_id),
                    }

                    secret = key_config.get("secret-key")
                    if secret is not None:
                        parsed_key["secret-key"] = secret

                    algo = key_config.get("crypto-algorithm")
                    if algo is not None:
                        parsed_key["crypto-algorithm"] = _strip_oc_prefix(algo)

                    # Send lifetime
                    sl = key_entry.get("send-lifetime", {}).get("config", {})
                    if sl:
                        lifetime = {}
                        always = sl.get(f"{ARCOS_KEYCHAIN_AUGMENTS}:always")
                        if always is not None:
                            lifetime["always"] = always
                        start = sl.get("start-time")
                        if start is not None:
                            lifetime["start-time"] = start
                        end = sl.get("end-time")
                        if end is not None:
                            lifetime["end-time"] = end
                        if lifetime:
                            parsed_key["send-lifetime"] = lifetime

                    keys_dict[str(key_id)] = parsed_key

                if keys_dict:
                    kc_entry["keys"] = keys_dict

            result["keychains"][kc_name] = kc_entry

        if not result["keychains"]:
            raise SchemaEmptyParserError("No keychains parsed")

        return result


# ============================================================================
# Parser 2: ShowKeychain (operational state)
# ============================================================================

class ShowKeychainSchema(MetaParser):
    """Schema for ArcOS keychain operational state.

    Represents keychain state as returned by::

        show keychain | display json | nomore
        show keychain {name} | display json | nomore
    """

    schema = {
        "keychains": {
            Any(): {  # keychain name
                "name": str,
                Optional("tolerance"): int,
                Optional("keys"): {
                    Any(): {  # key-id
                        "key-id": str,
                        Optional("secret-key"): str,
                        Optional("crypto-algorithm"): str,
                        Optional("send-active"): bool,
                        Optional("receive-active"): bool,
                        Optional("send-lifetime"): {
                            Optional("always"): bool,
                            Optional("start-time"): str,
                            Optional("end-time"): str,
                            Optional("send-and-receive"): bool,
                        },
                    }
                },
            }
        }
    }


class ShowKeychain(ShowKeychainSchema):
    """Parser for ArcOS keychain operational state (JSON format).

    Commands::

        show keychain | display json | nomore
        show keychain {name} | display json | nomore
    """

    cli_command = [
        "show keychain | display json | nomore",
        "show keychain {name} | display json | nomore",
    ]

    def cli(self, name: TypeOptional[str] = None,
            output: TypeOptional[str] = None) -> TypeAny:
        """Parse keychain operational state.

        Args:
            name: Optional keychain name to filter.
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ShowKeychainSchema.
        """
        if output is None:
            if name:
                cmd = f"show keychain {name} | display json | nomore"
            else:
                cmd = "show keychain | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowKeychain: empty output")

        json_output = load_json_robust(output)
        if not json_output:
            raise SchemaEmptyParserError("No JSON output or empty response")

        kc_list = _get_keychains_data(json_output)
        if not kc_list:
            raise SchemaEmptyParserError("No keychain data found")

        result = {"keychains": {}}

        for kc in kc_list:
            kc_name = kc.get("name")
            if not kc_name:
                continue

            kc_entry = {
                "name": kc_name,
            }

            # State container
            state = kc.get("state", {})
            tolerance = state.get("tolerance")
            if tolerance is not None:
                kc_entry["tolerance"] = tolerance

            # Keys
            keys_container = kc.get("keys", {})
            key_list = keys_container.get("key", [])
            if key_list:
                keys_dict = {}
                for key_entry in key_list:
                    key_id = key_entry.get("key-id")
                    if not key_id:
                        continue

                    key_state = key_entry.get("state", {})
                    parsed_key = {
                        "key-id": str(key_id),
                    }

                    secret = key_state.get("secret-key")
                    if secret is not None:
                        parsed_key["secret-key"] = secret

                    algo = key_state.get("crypto-algorithm")
                    if algo is not None:
                        parsed_key["crypto-algorithm"] = _strip_oc_prefix(algo)

                    send_active = key_state.get(
                        f"{ARCOS_KEYCHAIN_AUGMENTS}:send-active")
                    if send_active is not None:
                        parsed_key["send-active"] = send_active

                    recv_active = key_state.get(
                        f"{ARCOS_KEYCHAIN_AUGMENTS}:receive-active")
                    if recv_active is not None:
                        parsed_key["receive-active"] = recv_active

                    # Send lifetime
                    sl = key_entry.get("send-lifetime", {}).get("state", {})
                    if sl:
                        lifetime = {}
                        always = sl.get(f"{ARCOS_KEYCHAIN_AUGMENTS}:always")
                        if always is not None:
                            lifetime["always"] = always
                        start = sl.get("start-time")
                        if start is not None:
                            lifetime["start-time"] = start
                        end = sl.get("end-time")
                        if end is not None:
                            lifetime["end-time"] = end
                        sar = sl.get("send-and-receive")
                        if sar is not None:
                            lifetime["send-and-receive"] = sar
                        if lifetime:
                            parsed_key["send-lifetime"] = lifetime

                    keys_dict[str(key_id)] = parsed_key

                if keys_dict:
                    kc_entry["keys"] = keys_dict

            result["keychains"][kc_name] = kc_entry

        if not result["keychains"]:
            raise SchemaEmptyParserError("No keychains parsed")

        return result
