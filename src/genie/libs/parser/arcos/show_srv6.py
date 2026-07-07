"""ArcOS SRv6 parsers.

Parsers for Arrcus ArcOS SRv6 (Segment Routing v6) commands using
OpenConfig JSON format.
"""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional

from genie.libs.parser.arcos.constants import (
    ARCOS_SRV6,
    DEFAULT_INSTANCE,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input


log = logging.getLogger(__name__)


def _get_srv6_data(json_output: Dict, instance: str = DEFAULT_INSTANCE) -> Dict:
    """Navigate to the SRv6 data for a given network-instance.

    The JSON structure is of the form::

        data[OPENCONFIG_NETWORK_INSTANCES].network-instance[]
            .name == <instance>
            .ARCOS_SRV6

    Returns the inner ``srv6`` dictionary or an empty dict if not found.
    """

    data = json_output.get("data", {})
    ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

    for ni in ni_container.get("network-instance", []):
        if ni.get("name") == instance and ARCOS_SRV6 in ni:
            return ni.get(ARCOS_SRV6, {}) or {}

    return {}


class ShowSrv6ConfigSchema(MetaParser):
    """Schema for SRv6 running configuration.

    Represents a high-level view of SRv6 configuration per
    network-instance as returned by::

        show running-config network-instance * srv6 | display json | nomore
    """

    schema = {
        "network-instances": {
            Any(): {  # network-instance name
                "srv6": {
                    Optional("config"): {
                        Optional("encapsulation"): {
                            Optional("source-address"): str,
                        },
                        Optional("locators"): {
                            Any(): {  # locator name
                                "name": str,
                                Optional("locator-node-length"): int,
                                Optional("prefix"): str,
                                Optional("function-length"): int,
                                Optional("algorithm"): int,
                            }
                        },
                    }
                }
            }
        }
    }


class ShowSrv6Config(ShowSrv6ConfigSchema):
    """Parser for ArcOS SRv6 running configuration (JSON)."""

    cli_command = [
        "show running-config network-instance {instance} srv6",
    ]

    def cli(
        self,
        instance: str = "*",
        locator: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(instance, "instance")
            cmd = f"show running-config network-instance {instance} srv6"
            if locator:
                validate_input(locator, "locator")
                cmd += f" locator {locator}"
            log.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        log.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {"network-instances": {}}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse SRv6 config JSON output: %s", exc)
            return ret_dict
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Unexpected error parsing SRv6 config JSON: %s", exc)
            return ret_dict

        # Parse all network instances
        instances_to_parse = []
        data = parsed_json.get("data", {})
        ni_container = data.get("network-instances", {})
        for ni in ni_container.get("network-instance", []):
            ni_name = ni.get("name")
            if not ni_name:
                continue
            instances_to_parse.append(ni_name)

        if not instances_to_parse:
            instances_to_parse = [DEFAULT_INSTANCE]

        for inst_name in instances_to_parse:
            srv6 = _get_srv6_data(parsed_json, instance=inst_name)
            if not srv6:
                continue

            ni_entry: Dict[str, TypeAny] = {}

            # Encapsulation source-address
            encap_cfg = srv6.get("encapsulation", {}).get("config", {})
            if encap_cfg:
                src = encap_cfg.get("source-address")
                ni_entry["encapsulation"] = {"source-address": src}

            # Locator configuration
            loc_list = srv6.get("locator", []) or []
            if loc_list:
                locators_dict: Dict[str, TypeAny] = {}
                for loc in loc_list:
                    name = loc.get("name")
                    if not name:
                        continue

                    cfg = loc.get("config", {}) or {}
                    loc_entry: Dict[str, TypeAny] = {"name": name}

                    if "locator-node-length" in cfg:
                        loc_entry["locator-node-length"] = cfg["locator-node-length"]
                    if "prefix" in cfg:
                        loc_entry["prefix"] = cfg["prefix"]
                    if "function-length" in cfg:
                        loc_entry["function-length"] = cfg["function-length"]
                    if "algorithm" in cfg:
                        loc_entry["algorithm"] = cfg["algorithm"]

                    locators_dict[name] = loc_entry

                if locators_dict:
                    ni_entry["locators"] = locators_dict

            if ni_entry:
                ni_dict = ret_dict["network-instances"].setdefault(inst_name, {})
                srv6_dict = ni_dict.setdefault("srv6", {})
                srv6_dict["config"] = ni_entry

        return ret_dict


class ShowSrv6LocatorSchema(MetaParser):
    """Schema for SRv6 locator operational state.

    Represents SRv6 locator state per network-instance as returned by::

        show network-instance * srv6 locator | display json | nomore
    """

    schema = {
        "network-instances": {
            Any(): {  # network-instance name
                "srv6": {
                    Optional("locators"): {
                        Any(): {  # locator name
                            "name": str,
                            Optional("locator-node-length"): int,
                            Optional("prefix"): str,
                            Optional("micro-segment-behavior-unode"): bool,
                            Optional("function-length"): int,
                            Optional("algorithm"): int,
                        }
                    }
                }
            }
        }
    }


class ShowSrv6Locator(ShowSrv6LocatorSchema):
    """Parser for ArcOS SRv6 locator operational state (JSON)."""

    cli_command = [
        "show network-instance {instance} srv6 locator",
        "show network-instance {instance} srv6 locator {locator_name}",
    ]

    def cli(
        self,
        instance: str = "*",
        locator_name: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(instance, "instance")
            cmd = f"show network-instance {instance} srv6 locator"
            if locator_name:
                validate_input(locator_name, "locator_name")
                cmd += f" {locator_name}"

            log.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        log.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {"network-instances": {}}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse SRv6 locator JSON output: %s", exc)
            return ret_dict
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Unexpected error parsing SRv6 locator JSON: %s", exc)
            return ret_dict

        instances_to_parse = []
        data = parsed_json.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        for ni in ni_container.get("network-instance", []):
            ni_name = ni.get("name")
            if not ni_name:
                continue
            instances_to_parse.append(ni_name)

        if not instances_to_parse:
            instances_to_parse = [DEFAULT_INSTANCE]

        for inst_name in instances_to_parse:
            srv6 = _get_srv6_data(parsed_json, instance=inst_name)
            if not srv6:
                continue

            ni_entry: Dict[str, TypeAny] = {}

            loc_list = srv6.get("locator", []) or []
            if loc_list:
                locators_dict: Dict[str, TypeAny] = {}
                for loc in loc_list:
                    name = loc.get("name")
                    if not name:
                        continue

                    state = loc.get("state", {}) or {}
                    loc_entry: Dict[str, TypeAny] = {"name": name}

                    if "locator-node-length" in state:
                        loc_entry["locator-node-length"] = state["locator-node-length"]
                    if "prefix" in state:
                        loc_entry["prefix"] = state["prefix"]
                    if "micro-segment-behavior-unode" in state:
                        loc_entry["micro-segment-behavior-unode"] = state[
                            "micro-segment-behavior-unode"
                        ]
                    if "function-length" in state:
                        loc_entry["function-length"] = state["function-length"]
                    if "algorithm" in state:
                        loc_entry["algorithm"] = state["algorithm"]

                    locators_dict[name] = loc_entry

                if locators_dict:
                    ni_entry["locators"] = locators_dict

            if ni_entry:
                ni_dict = ret_dict["network-instances"].setdefault(inst_name, {})
                ni_dict["srv6"] = ni_entry

        return ret_dict


class ShowSrv6LocalSidsSchema(MetaParser):
    """Schema for the SRv6 local-SID table operational state.

    Represents per-SID SRv6 local-SID state per network-instance as
    returned by::

        show network-instance * srv6 local-sids | display json | nomore
    """

    schema = {
        "network_instance": {
            Any(): {  # network-instance name
                Optional("local_sids"): {
                    Any(): {  # SID, e.g. "fcbb:bb00:1:1::/64"
                        Optional("behavior"): str,
                        Optional("locator_name"): str,
                        Optional("client_name"): str,
                        Optional("sid_paths"): list,
                    }
                }
            }
        }
    }


class ShowSrv6LocalSids(ShowSrv6LocalSidsSchema):
    """Parser for ArcOS SRv6 local-SID table operational state (JSON)."""

    cli_command = [
        "show network-instance {instance} srv6 local-sids",
    ]

    def cli(
        self,
        instance: str = "*",
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(instance, "instance")
            cmd = f"show network-instance {instance} srv6 local-sids"
            log.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        log.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {"network_instance": {}}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse SRv6 local-sids JSON output: %s", exc)
            return ret_dict
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Unexpected error parsing SRv6 local-sids JSON: %s", exc)
            return ret_dict

        instances_to_parse = []
        data = parsed_json.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        for ni in ni_container.get("network-instance", []):
            ni_name = ni.get("name")
            if not ni_name:
                continue
            instances_to_parse.append(ni_name)

        if not instances_to_parse:
            instances_to_parse = [DEFAULT_INSTANCE]

        for inst_name in instances_to_parse:
            srv6 = _get_srv6_data(parsed_json, instance=inst_name)
            if not srv6:
                continue

            local_sids_container = srv6.get("local-sids", {}) or {}
            sid_list = local_sids_container.get("local-sid", []) or []
            if not sid_list:
                continue

            sids_dict: Dict[str, TypeAny] = {}
            for entry in sid_list:
                sid = entry.get("sid")
                if not sid:
                    continue

                sid_entry: Dict[str, TypeAny] = {}

                behavior = entry.get("behavior")
                if behavior:
                    # Strip the module prefix, e.g.
                    # "arcos-srv6-types:END_PSP_USD" -> "END_PSP_USD"
                    # Generic strip (not hardcoded to a single prefix) so
                    # future behaviors (e.g. uSID flavors) are handled the
                    # same way without special-casing.
                    if ":" in behavior:
                        behavior = behavior.split(":", 1)[1]
                    sid_entry["behavior"] = behavior

                if "locator-name" in entry:
                    sid_entry["locator_name"] = entry["locator-name"]

                if "client-name" in entry:
                    sid_entry["client_name"] = entry["client-name"]

                sid_paths_container = entry.get("sid-paths", {}) or {}
                sid_path_list = sid_paths_container.get("sid-path", []) or []
                # ArcOS may emit a single sid-path as a dict rather than a
                # single-element list.
                if isinstance(sid_path_list, dict):
                    sid_path_list = [sid_path_list]

                if sid_path_list:
                    paths = []
                    for path in sid_path_list:
                        path_entry: Dict[str, TypeAny] = {}
                        if "next-hop-address" in path:
                            path_entry["next_hop_address"] = path[
                                "next-hop-address"
                            ]
                        if "interface" in path:
                            path_entry["interface"] = path["interface"]
                        if path_entry:
                            paths.append(path_entry)
                    if paths:
                        sid_entry["sid_paths"] = paths

                if sid_entry:
                    sids_dict[sid] = sid_entry

            if sids_dict:
                ni_dict = ret_dict["network_instance"].setdefault(inst_name, {})
                ni_dict["local_sids"] = sids_dict

        return ret_dict
