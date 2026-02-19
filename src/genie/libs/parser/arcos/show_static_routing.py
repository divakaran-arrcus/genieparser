"""ArcOS Static Routing parsers.

Parsers for Arrcus ArcOS Static Routing commands using
OpenConfig JSON format.
"""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or

from genie.libs.parser.arcos.constants import (
    DEFAULT_INSTANCE,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input


log = logging.getLogger(__name__)


def _get_static_routing_data(
    json_output: Dict, network_instance: str = DEFAULT_INSTANCE
) -> Dict:
    """Navigate to the Static Routing protocol data for a given network-instance.

    The JSON structure is of the form::

        data[OPENCONFIG_NETWORK_INSTANCES].network-instance[]
            .name == <network_instance>
            .protocols.protocol[]
                .identifier == "STATIC"
                .name == <protocol_instance>

    Returns the inner protocol dictionary or an empty dict if not found.
    """

    data = json_output.get("data", {})
    ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

    for ni in ni_container.get("network-instance", []):
        if ni.get("name") == network_instance:
            protocols = ni.get("protocols", {})
            for protocol in protocols.get("protocol", []):
                if protocol.get("identifier") == "STATIC":
                    return protocol

    return {}


class ShowStaticRoutingConfigSchema(MetaParser):
    """Schema for Static Routing running configuration.

    Represents static routing configuration per network-instance as returned by::

        show running-config network-instance {network_instance} protocol STATIC {protocol_instance} | display json | nomore
    """

    schema = {
        "network_instances": {
            Any(): {  # network-instance name
                "protocols": {
                    Any(): {  # protocol instance name
                        "identifier": str,
                        "name": str,
                        Optional("static_routes"): {
                            Any(): {  # static route prefix
                                "prefix": str,
                                Optional("description"): str,
                                Optional("set_tag"): Or(int, str),
                                Optional("preference"): int,
                                Optional("local_label_index"): int,
                                Optional("bfd"): {
                                    Optional("profile"): str,
                                },
                                Optional("next_hops"): {
                                    Any(): {  # next-hop index
                                        "index": str,
                                        Optional("next_hop"): str,
                                        Optional("interface"): str,
                                        Optional("subinterface"): int,
                                        Optional("metric"): int,
                                        Optional("next_network_instance"): str,
                                        Optional("remote_label_stack"): list,
                                        Optional("bfd"): {
                                            Optional("destination_address"): Or(
                                                str,
                                                {
                                                    Optional("ipv4"): str,
                                                    Optional("ipv6"): str,
                                                },
                                            )
                                        },
                                    }
                                },
                            }
                        },
                    }
                }
            }
        }
    }


class ShowStaticRoutingConfig(ShowStaticRoutingConfigSchema):
    """Parser for ArcOS Static Routing running configuration (JSON).

    Command pattern (before JSON pipe)::

        show running-config network-instance {network_instance} protocol STATIC {protocol_instance}
    """

    cli_command = [
        "show running-config network-instance {network_instance} protocol STATIC {protocol_instance}",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            cmd = f"show running-config network-instance {network_instance} protocol STATIC {protocol_instance}"
            log.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        log.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {"network_instances": {}}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            log.warning("Failed to parse Static Routing config JSON output: %s", exc)
            return ret_dict
        except Exception as exc:
            log.warning("Unexpected error parsing Static Routing config JSON: %s", exc)
            return ret_dict

        # Parse all network instances
        data = parsed_json.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

        for ni in ni_container.get("network-instance", []):
            ni_name = ni.get("name")
            if not ni_name:
                continue

            protocols = ni.get("protocols", {})
            for protocol in protocols.get("protocol", []):
                protocol_id = protocol.get("identifier")
                protocol_name = protocol.get("name")

                # Handle both "STATIC" and "openconfig-policy-types:STATIC"
                if not protocol_id or "STATIC" not in protocol_id or not protocol_name:
                    continue

                # Initialize network instance and protocol entry
                ni_dict = ret_dict["network_instances"].setdefault(ni_name, {})
                protocols_dict = ni_dict.setdefault("protocols", {})
                protocol_dict = protocols_dict.setdefault(protocol_name, {})

                protocol_dict["identifier"] = protocol_id
                protocol_dict["name"] = protocol_name

                # Parse static routes
                static_routes_config = protocol.get("static-routes", {})
                static_route_list = static_routes_config.get("static", [])

                if static_route_list:
                    static_routes_dict: Dict[str, TypeAny] = {}

                    for route in static_route_list:
                        prefix = route.get("prefix")
                        if not prefix:
                            continue

                        config = route.get("config", {})
                        route_entry: Dict[str, TypeAny] = {"prefix": prefix}

                        # Optional static route attributes (handle ARCOS augmented names)
                        desc_key = "arcos-openconfig-local-routing-augments:description"
                        if desc_key in config:
                            route_entry["description"] = config[desc_key]
                        elif "description" in config:
                            route_entry["description"] = config["description"]

                        tag_key = "arcos-openconfig-local-routing-augments:set-tag"
                        if tag_key in config:
                            route_entry["set_tag"] = config[tag_key]
                        elif "set-tag" in config:
                            route_entry["set_tag"] = config["set-tag"]

                        pref_key = "arcos-openconfig-local-routing-augments:preference"
                        if pref_key in config:
                            route_entry["preference"] = config[pref_key]
                        elif "preference" in config:
                            route_entry["preference"] = config["preference"]

                        label_key = "arcos-openconfig-local-routing-augments:local-label-index"
                        if label_key in config:
                            route_entry["local_label_index"] = config[label_key]
                        elif "local-label-index" in config:
                            route_entry["local_label_index"] = config["local-label-index"]

                        # Parse BFD configuration at route level (handle ARCOS augmented)
                        bfd_key = "arcos-openconfig-local-routing-augments:bfd"
                        if bfd_key in config:
                            bfd_cfg = config[bfd_key]
                            if "profile" in bfd_cfg:
                                route_entry["bfd"] = {"profile": bfd_cfg["profile"]}
                        elif "bfd" in config:
                            bfd_cfg = config["bfd"]
                            if "profile" in bfd_cfg:
                                route_entry["bfd"] = {"profile": bfd_cfg["profile"]}

                        # Parse next-hops
                        next_hop_list = route.get("next-hops", {}).get("next-hop", [])
                        if next_hop_list:
                            next_hops_dict: Dict[str, TypeAny] = {}

                            for nh in next_hop_list:
                                nh_index = nh.get("index")
                                if not nh_index:
                                    continue

                                nh_config = nh.get("config", {})
                                nh_entry: Dict[str, TypeAny] = {"index": nh_index}

                                # Next-hop address or DROP
                                if "next-hop" in nh_config:
                                    nh_entry["next_hop"] = nh_config["next-hop"]

                                # Interface configuration
                                interface_ref = nh.get("interface-ref", {})
                                if interface_ref:
                                    if_config = interface_ref.get("config", {})
                                    if "interface" in if_config:
                                        nh_entry["interface"] = if_config["interface"]
                                    if "subinterface" in if_config:
                                        nh_entry["subinterface"] = if_config["subinterface"]

                                # Metric (handle ARCOS augmented)
                                metric_key = "arcos-openconfig-local-routing-augments:metric"
                                if metric_key in nh_config:
                                    nh_entry["metric"] = nh_config[metric_key]
                                elif "metric" in nh_config:
                                    nh_entry["metric"] = nh_config["metric"]

                                # Next network instance (for VRF leaking, handle ARCOS augmented)
                                ni_key = "arcos-openconfig-local-routing-augments:next-network-instance-name"
                                if ni_key in nh_config:
                                    nh_entry["next_network_instance"] = nh_config[ni_key]
                                elif "next-network-instance" in nh_config:
                                    nh_entry["next_network_instance"] = nh_config[
                                        "next-network-instance"
                                    ]

                                # Remote label stack (handle ARCOS augmented)
                                rls_key = "arcos-openconfig-local-routing-augments:remote-label-stack"
                                if rls_key in nh_config:
                                    labels = nh_config[rls_key]
                                    if isinstance(labels, list):
                                        nh_entry["remote_label_stack"] = labels
                                    else:
                                        nh_entry["remote_label_stack"] = [labels]
                                elif "remote-label-stack" in nh_config:
                                    labels = nh_config["remote-label-stack"]
                                    if isinstance(labels, list):
                                        nh_entry["remote_label_stack"] = labels
                                    else:
                                        nh_entry["remote_label_stack"] = [labels]

                                # BFD configuration at next-hop level (handle ARCOS augmented)
                                bfd_nh_key = "arcos-openconfig-local-routing-augments:bfd"
                                if bfd_nh_key in nh_config:
                                    bfd_cfg = nh_config[bfd_nh_key]
                                    if "destination-address" in bfd_cfg:
                                        dest_addr = bfd_cfg["destination-address"]
                                        # ARCOS uses simple string for destination address
                                        nh_entry["bfd"] = {"destination_address": dest_addr}
                                else:
                                    nh_bfd = nh.get("bfd", {})
                                    if nh_bfd:
                                        nh_bfd_config = nh_bfd.get("config", {})
                                        bfd_entry: Dict[str, TypeAny] = {}

                                        dest_addr = nh_bfd_config.get("destination-address", {})
                                        if dest_addr:
                                            dest_entry: Dict[str, TypeAny] = {}
                                            if "ipv4" in dest_addr:
                                                dest_entry["ipv4"] = dest_addr["ipv4"]
                                            if "ipv6" in dest_addr:
                                                dest_entry["ipv6"] = dest_addr["ipv6"]
                                            if dest_entry:
                                                bfd_entry["destination_address"] = dest_entry

                                        if bfd_entry:
                                            nh_entry["bfd"] = bfd_entry

                                next_hops_dict[nh_index] = nh_entry

                            if next_hops_dict:
                                route_entry["next_hops"] = next_hops_dict

                        static_routes_dict[prefix] = route_entry

                    if static_routes_dict:
                        protocol_dict["static_routes"] = static_routes_dict

        return ret_dict
