"""ArcOS Segment Routing parsers.

Parsers for Arrcus ArcOS Segment Routing commands including SRMS
(Segment Routing Mapping Server) using OpenConfig JSON format.
"""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import (
    ARCOS_SR_AUGMENTS,
    DEFAULT_INSTANCE,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input


log = logging.getLogger(__name__)


def _get_segment_routing_data(
    json_output: Dict, instance: str = DEFAULT_INSTANCE
) -> Dict:
    """Navigate to the segment-routing data for a given network-instance.

    Returns the inner ``segment-routing`` dictionary or an empty dict.
    """
    data = json_output.get("data", {})
    ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

    for ni in ni_container.get("network-instance", []):
        if ni.get("name") == instance and "segment-routing" in ni:
            return ni.get("segment-routing", {}) or {}

    return {}


class ShowSrmsMappingsConfigSchema(MetaParser):
    """Schema for SRMS mappings running configuration.

    Represents SRMS mapping configuration per network-instance as returned by::

        show running-config network-instance * segment-routing | display json | nomore
    """

    schema = {
        "network-instances": {
            Any(): {  # network-instance name
                Optional("srms"): {
                    Optional("mappings"): {
                        Any(): {  # mapping local-id
                            "local-id": str,
                            Optional("ipv4-prefixes"): list,
                            Optional("ipv6-prefixes"): list,
                        }
                    }
                }
            }
        }
    }


class ShowSrmsMappingsConfig(ShowSrmsMappingsConfigSchema):
    """Parser for ArcOS SRMS mappings running configuration (JSON)."""

    cli_command = [
        "show running-config network-instance {instance} segment-routing",
    ]

    def cli(
        self,
        instance: str = "*",
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(instance, "instance")
            cmd = f"show running-config network-instance {instance} segment-routing"
            log.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSrmsMappingsConfig: empty output")

        log.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {"network-instances": {}}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse SRMS config JSON output: %s", exc)
            return ret_dict
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Unexpected error parsing SRMS config JSON: %s", exc)
            return ret_dict

        # Parse all network instances
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
            sr_data = _get_segment_routing_data(parsed_json, instance=inst_name)
            if not sr_data:
                continue

            # Get SRMS data
            srms_root = sr_data.get(f"{ARCOS_SR_AUGMENTS}:srms", {})
            mappings_root = srms_root.get("mappings", {})
            mapping_list = mappings_root.get("mapping", [])

            if not mapping_list:
                continue

            mappings_dict: Dict[str, TypeAny] = {}
            for mapping in mapping_list:
                local_id = mapping.get("local-id")
                if not local_id:
                    continue

                mapping_entry: Dict[str, TypeAny] = {"local-id": local_id}

                # IPv4 prefixes
                ipv4_root = mapping.get("ipv4", {})
                ipv4_prefixes = ipv4_root.get("prefixes", {}).get("prefix", [])
                if ipv4_prefixes:
                    ipv4_list = []
                    for prefix_entry in ipv4_prefixes:
                        prefix_str = prefix_entry.get("ipv4-prefix")
                        if not prefix_str:
                            continue
                        cfg = prefix_entry.get("config", {})
                        p_entry: Dict[str, TypeAny] = {"prefix": prefix_str}
                        if "sid" in cfg:
                            p_entry["sid"] = cfg["sid"]
                        if "range" in cfg:
                            p_entry["range"] = cfg["range"]
                        ipv4_list.append(p_entry)
                    if ipv4_list:
                        mapping_entry["ipv4-prefixes"] = ipv4_list

                # IPv6 prefixes
                ipv6_root = mapping.get("ipv6", {})
                ipv6_prefixes = ipv6_root.get("prefixes", {}).get("prefix", [])
                if ipv6_prefixes:
                    ipv6_list = []
                    for prefix_entry in ipv6_prefixes:
                        prefix_str = prefix_entry.get("ipv6-prefix")
                        if not prefix_str:
                            continue
                        cfg = prefix_entry.get("config", {})
                        p_entry = {"prefix": prefix_str}
                        if "sid" in cfg:
                            p_entry["sid"] = cfg["sid"]
                        if "range" in cfg:
                            p_entry["range"] = cfg["range"]
                        ipv6_list.append(p_entry)
                    if ipv6_list:
                        mapping_entry["ipv6-prefixes"] = ipv6_list

                mappings_dict[local_id] = mapping_entry

            if mappings_dict:
                ni_dict = ret_dict["network-instances"].setdefault(inst_name, {})
                ni_dict["srms"] = {"mappings": mappings_dict}

        return ret_dict
