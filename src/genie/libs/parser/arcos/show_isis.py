"""ArcOS ISIS parsers.

Parsers for Arrcus ArcOS ISIS OpenConfig-based JSON commands.

Initially this module provides adjacency and LSP database parsers,
mirroring the behavior of the local Arrcus pyATS implementation.
"""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or

from genie.libs.parser.arcos.constants import (
    ARCOS_ISIS_AUGMENTS,
    DEFAULT_INSTANCE,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input


logger = logging.getLogger(__name__)


def get_isis_data(json_output: Dict, instance: str = DEFAULT_INSTANCE) -> Dict:
    """Navigate to the ISIS protocol data in the standard ArcOS JSON structure.

    The expected layout is::

        data[OPENCONFIG_NETWORK_INSTANCES].network-instance[]
            .name == instance
            .protocols.protocol[]
                .name == DEFAULT_INSTANCE and contains "isis"

    Returns the inner ``isis`` dictionary or an empty dict if not found.
    """

    data = json_output.get("data", {})
    ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

    for ni in ni_container.get("network-instance", []):
        if ni.get("name") == instance:
            for protocol in ni.get("protocols", {}).get("protocol", []):
                if protocol.get("name") == DEFAULT_INSTANCE and "isis" in protocol:
                    return protocol["isis"]
    return {}


class ShowIsisAdjacencySchema(MetaParser):
    """Schema for ArcOS ISIS adjacency JSON output.
    
    New hierarchical structure: interface → level → adjacency
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("interface"): {
                            Any(): {  # interface name (e.g., "swp1")
                                "level": {
                                    Any(): {  # level number (1 or 2)
                                        "adjacency": {
                                            Any(): {  # neighbor system-id
                                                "state": str,
                                                Optional("holdtime"): int,
                                                Optional("adjacency-type"): str,
                                                Optional("neighbor-ipv4-address"): str,
                                                Optional("neighbor-ipv6-address"): str,
                                                Optional("up-time"): Or(int, str),
                                                Optional("num-state-changes"): int,
                                                Optional("last-state-change-timestamp"): str,
                                                Optional("last-down-reason"): str,
                                                Optional("neighbor-circuit-type"): str,
                                                Optional("local-extended-circuit-id"): int,
                                                Optional("neighbor-extended-circuit-id"): int,
                                                Optional("restart-support"): bool,
                                                Optional("restart-suppress"): bool,
                                                Optional("restart-status"): bool,
                                                Optional("nlpid"): list,
                                                Optional("usable"): bool,
                                                Optional("restart-ack"): bool,
                                                Optional("restart-request"): bool,
                                                Optional("received-multi-topology-ids"): list,
                                                Optional("active-multi-topology-ids"): list,
                                                Optional("bfd"): {
                                                    Optional("bfd-required"): bool,
                                                    Optional("topologies"): {
                                                        Any(): {  # mt-id
                                                            "mt-id": int,
                                                            Optional("ipv4-bfd-required"): bool,
                                                            Optional("ipv6-bfd-required"): bool,
                                                            Optional("bfd-required"): bool,
                                                            Optional("ipv4-bfd-up"): bool,
                                                            Optional("ipv6-bfd-up"): bool,
                                                            Optional("ipv4-up"): bool,
                                                            Optional("ipv6-up"): bool,
                                                            Optional("usable"): bool,
                                                        }
                                                    },
                                                },
                                                Optional("dynamic-delay-measurement"): {
                                                    Optional("enabled"): bool,
                                                    Optional("num-advertisements-sent"): int,
                                                    Optional("last-sampled-avg-delay-value"): int,
                                                    Optional("last-advertised-min-delay-value"): int,
                                                    Optional("last-advertised-max-delay-value"): int,
                                                    Optional("last-advertised-timestamp"): str,
                                                    Optional("last-advertisement-reason"): str,
                                                },
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisAdjacency(ShowIsisAdjacencySchema):
    """Parser for ArcOS ISIS adjacency command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level} adjacency [<adj_router>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level} adjacency",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        interface: str = "*",
        level: str = "*",
        adj_router: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(interface, "interface")
            validate_input(level, "level")
            
            # For L1/L2 routers, wildcard level doesn't work correctly
            # Query each level separately and merge results
            if level == "*":
                all_outputs = []
                for level_num in [1, 2]:
                    cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level_num} adjacency"
                    if adj_router:
                        validate_input(adj_router, "adj_router")
                        cmd += f" {adj_router}"
                    logger.debug(f"Executing command: {cmd}")
                    try:
                        level_output = self.device.execute(f"{cmd} | display json | nomore")
                        
                        # WORKAROUND: Router bug - LEVEL output may be missing "data" wrapper and start with comma
                        # Fix malformed JSON by wrapping it properly
                        if level_output.strip().startswith(','):
                            logger.debug(f"Detected malformed JSON for level {level_num}, fixing structure")
                            # Remove leading comma and whitespace, wrap in proper structure
                            fixed_output = level_output.strip()[1:].strip()  # Remove leading comma
                            # Check if it starts with array of interfaces
                            if fixed_output.startswith('{') and '"interface-id"' in fixed_output[:100]:
                                # Wrap the interface array in proper structure
                                level_output = f'''{{
  "data": {{
    "openconfig-network-instance:network-instances": {{
      "network-instance": [
        {{
          "name": "default",
          "protocols": {{
            "protocol": [
              {{
                "identifier": "openconfig-policy-types:ISIS",
                "name": "default",
                "isis": {{
                  "interfaces": {{
                    "interface": [
                      {fixed_output}
                    ]
                  }}
                }}
              }}
            ]
          }}
        }}
      ]
    }}
  }}
}}'''
                        
                        # Validate JSON before adding to list
                        try:
                            test_parse = load_json_robust(level_output)
                            # Check if contains valid ISIS adjacency data
                            has_data = False
                            if test_parse and "data" in test_parse:
                                # Validate that ISIS adjacency structure exists
                                isis_data = get_isis_data(test_parse)
                                interfaces = isis_data.get("interfaces", {}).get("interface", [])
                                # Check if any interface has adjacencies
                                for intf in interfaces:
                                    levels = intf.get("levels", {}).get("level", [])
                                    for lvl in levels:
                                        adjacencies = lvl.get("adjacencies", {}).get("adjacency", [])
                                        if adjacencies:
                                            has_data = True
                                            break
                                    if has_data:
                                        break
                            
                            if has_data:
                                all_outputs.append(level_output)
                            else:
                                logger.debug(f"No adjacencies found for level {level_num}")
                        except json.JSONDecodeError as je:
                            logger.debug(f"Level {level_num} JSON decode error: {je}")
                            continue
                    except Exception as e:
                        logger.debug(f"Level {level_num} query failed: {e}")
                        continue
                
                # Merge outputs by combining the parsed results
                output = None  # Will parse each output separately and merge
            else:
                cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level} adjacency"
                if adj_router:
                    validate_input(adj_router, "adj_router")
                    cmd += f" {adj_router}"
                logger.debug("Executing command: %s", cmd)
                output = self.device.execute(f"{cmd} | display json | nomore")
                all_outputs = [output]

        else:
            all_outputs = [output]

        logger.debug("Parsing output")
        # Initialize return dictionary with new hierarchical structure
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]

        try:
            # Process each output (one per level when wildcard is used)
            for output_data in all_outputs:
                parsed_json = load_json_robust(output_data)

                isis_data = get_isis_data(parsed_json)
                interfaces_data = isis_data.get("interfaces", {}).get("interface", [])

                if not interfaces_data:
                    logger.debug("No interfaces data found in this ISIS output")
                    continue

                logger.debug(f"Processing {len(interfaces_data)} interfaces")
                
                # Extract adjacencies from each interface and level
                for intf in interfaces_data:
                    intf_id = intf.get("interface-id")
                    if not intf_id:
                        continue

                    levels_data = intf.get("levels", {}).get("level", [])
                    for level in levels_data:
                        level_num = level.get("level-number")
                        if level_num is None:
                            continue
                        
                        adjacencies_data = level.get("adjacencies", {}).get("adjacency", [])
                        if not adjacencies_data:
                            continue  # Skip empty levels

                        for adj in adjacencies_data:
                            sys_id = adj.get("system-id")
                            if not sys_id:
                                continue

                            adj_state = adj.get("state", {})

                            # Build adjacency entry without redundant interface/level fields
                            adjacency_entry: Dict[str, TypeAny] = {
                                "state": adj_state.get("adjacency-state", "UNKNOWN"),
                            }

                            # Hold time
                            hold_time = adj_state.get("remaining-hold-time")
                            if hold_time is not None:
                                adjacency_entry["holdtime"] = hold_time

                            # Adjacency type (keep this field as it indicates L1/L2/L1_2)
                            adj_type = adj_state.get("adjacency-type", "")
                            if adj_type:
                                adjacency_entry["adjacency-type"] = adj_type

                            # Neighbor IPv4 / IPv6 addresses
                            neighbor_ipv4 = adj_state.get("neighbor-ipv4-address")
                            if neighbor_ipv4:
                                adjacency_entry["neighbor-ipv4-address"] = neighbor_ipv4

                            neighbor_ipv6 = adj_state.get("neighbor-ipv6-address")
                            if neighbor_ipv6:
                                adjacency_entry["neighbor-ipv6-address"] = neighbor_ipv6

                            # Up-time: prefer human-readable format if available
                            adj_up_time = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:adjacency-up-time"
                            )
                            if adj_up_time:
                                adjacency_entry["up-time"] = adj_up_time
                            else:
                                up_time = adj_state.get("up-time")
                                if up_time is not None:
                                    adjacency_entry["up-time"] = up_time

                            # State change tracking
                            num_state_changes = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:num-state-changes"
                            )
                            if num_state_changes is not None:
                                adjacency_entry["num-state-changes"] = num_state_changes

                            last_state_ts = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:last-state-change-timestamp"
                            )
                            if last_state_ts:
                                adjacency_entry["last-state-change-timestamp"] = last_state_ts

                            last_down_reason = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:last-down-reason"
                            )
                            if last_down_reason:
                                adjacency_entry["last-down-reason"] = last_down_reason

                            # Circuit IDs
                            local_cid = adj_state.get("local-extended-circuit-id")
                            if local_cid is not None:
                                adjacency_entry["local-extended-circuit-id"] = local_cid

                            neighbor_cid = adj_state.get("neighbor-extended-circuit-id")
                            if neighbor_cid is not None:
                                adjacency_entry["neighbor-extended-circuit-id"] = (
                                    neighbor_cid
                                )

                            # Neighbor circuit type
                            neighbor_ct = adj_state.get("neighbor-circuit-type")
                            if neighbor_ct:
                                adjacency_entry["neighbor-circuit-type"] = neighbor_ct

                            # Restart support / suppress / status
                            restart_support = adj_state.get("restart-support")
                            if restart_support is not None:
                                adjacency_entry["restart-support"] = restart_support

                            restart_suppress = adj_state.get("restart-suppress")
                            if restart_suppress is not None:
                                adjacency_entry["restart-suppress"] = restart_suppress

                            restart_status = adj_state.get("restart-status")
                            if restart_status is not None:
                                adjacency_entry["restart-status"] = restart_status

                            # NLPID
                            nlpid = adj_state.get("nlpid")
                            if nlpid:
                                adjacency_entry["nlpid"] = nlpid

                            # ArcOS augments
                            usable = adj_state.get(f"{ARCOS_ISIS_AUGMENTS}:usable")
                            if usable is not None:
                                adjacency_entry["usable"] = usable

                            restart_ack = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:restart-ack"
                            )
                            if restart_ack is not None:
                                adjacency_entry["restart-ack"] = restart_ack

                            restart_req = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:restart-request"
                            )
                            if restart_req is not None:
                                adjacency_entry["restart-request"] = restart_req

                            recv_mt_ids = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:received-multi-topology-ids"
                            )
                            if recv_mt_ids:
                                adjacency_entry["received-multi-topology-ids"] = recv_mt_ids

                            active_mt_ids = adj_state.get(
                                f"{ARCOS_ISIS_AUGMENTS}:active-multi-topology-ids"
                            )
                            if active_mt_ids:
                                adjacency_entry["active-multi-topology-ids"] = active_mt_ids

                            # BFD information
                            bfd_data = adj.get(f"{ARCOS_ISIS_AUGMENTS}:bfd", {})
                            if bfd_data:
                                bfd_info: Dict[str, TypeAny] = {}
                                bfd_state = bfd_data.get("state", {})
                                if bfd_state.get("bfd-required") is not None:
                                    bfd_info["bfd-required"] = bfd_state["bfd-required"]

                                topologies_data = bfd_data.get("topologies", {}).get(
                                    "topology", []
                                )
                                if topologies_data:
                                    topologies: Dict[TypeAny, TypeAny] = {}
                                    for topo in topologies_data:
                                        mt_id = topo.get("mt-id")
                                        if mt_id is None:
                                            continue

                                        topo_state = topo.get("state", {})
                                        topologies[mt_id] = {"mt-id": mt_id}
                                        for key in [
                                            "ipv4-bfd-required",
                                            "ipv6-bfd-required",
                                            "bfd-required",
                                            "ipv4-bfd-up",
                                            "ipv6-bfd-up",
                                            "ipv4-up",
                                            "ipv6-up",
                                            "usable",
                                        ]:
                                            if key in topo_state:
                                                topologies[mt_id][key] = topo_state[key]

                                    if topologies:
                                        bfd_info["topologies"] = topologies

                                if bfd_info:
                                    adjacency_entry["bfd"] = bfd_info

                            # Dynamic delay measurement
                            ddm_data = adj.get(
                                f"{ARCOS_ISIS_AUGMENTS}:dynamic-delay-measurement", {}
                            )
                            if ddm_data:
                                ddm_state = ddm_data.get("state", {})
                                if ddm_state:
                                    ddm_info: Dict[str, TypeAny] = {}
                                    for key in [
                                        "enabled",
                                        "num-advertisements-sent",
                                        "last-sampled-avg-delay-value",
                                        "last-advertised-min-delay-value",
                                        "last-advertised-max-delay-value",
                                        "last-advertised-timestamp",
                                        "last-advertisement-reason",
                                    ]:
                                        if key in ddm_state:
                                            ddm_info[key] = ddm_state[key]

                                    if ddm_info:
                                        adjacency_entry["dynamic-delay-measurement"] = (
                                            ddm_info
                                        )

                            # Build hierarchical structure: interface -> level -> adjacency
                            if "interface" not in ni_isis:
                                ni_isis["interface"] = {}
                            if intf_id not in ni_isis["interface"]:
                                ni_isis["interface"][intf_id] = {}
                            if "level" not in ni_isis["interface"][intf_id]:
                                ni_isis["interface"][intf_id]["level"] = {}
                            if level_num not in ni_isis["interface"][intf_id]["level"]:
                                ni_isis["interface"][intf_id]["level"][level_num] = {}
                            if "adjacency" not in ni_isis["interface"][intf_id]["level"][level_num]:
                                ni_isis["interface"][intf_id]["level"][level_num]["adjacency"] = {}
                            
                            ni_isis["interface"][intf_id]["level"][level_num]["adjacency"][sys_id] = adjacency_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            import traceback
            logger.error("Error parsing ISIS adjacency data: %s", exc)
            logger.error("Traceback: %s", traceback.format_exc())

        return ret_dict


class ShowIsisLspSchema(MetaParser):
    """Schema for ArcOS ISIS LSP database JSON output."""

    schema = {
        "network-instance": {
            Any(): {
                "isis": {
                    Any(): {
                        Optional("database"): {
                            Any(): {  # LSP ID
                                "lsp-id": str,
                                Optional("sequence"): int,
                                Optional("checksum"): int,
                                Optional("remaining-lifetime"): int,
                                Optional("received-timestamp"): str,
                                Optional("maximum-area-addresses"): int,
                                Optional("pdu-length"): int,
                                Optional("system-id"): str,
                                Optional("overload-bit"): bool,
                                Optional("attached-bit"): bool,
                                Optional("is-type"): str,
                                Optional("received-remaining-lifetime"): int,
                                Optional("last-update-ifindex"): int,
                                Optional("last-update-time"): str,
                                Optional("srm-count"): int,
                                Optional("ssn-count"): int,
                                Optional("tlvs"): {
                                    Optional("area-addresses"): list,
                                    Optional("hostname"): str,
                                    Optional("nlpid"): list,
                                    Optional("ipv4-interface-addresses"): list,
                                    Optional("ipv6-interface-addresses"): list,
                                    Optional("ipv4-te-router-id"): str,
                                    Optional("ipv6-te-router-id"): str,
                                    Optional("srv6-locators"): list,
                                    Optional("router-capabilities"): dict,
                                },
                                Optional("extended-ipv4-reachability"): dict,
                                Optional("ipv6-reachability"): dict,
                                Optional("mt-ipv6-reachability"): dict,
                                Optional("extended-is-neighbor"): dict,
                                Optional("mt-is-neighbor"): dict,
                                Optional("attributes"): dict,
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisLsp(ShowIsisLspSchema):
    """Parser for ArcOS ISIS LSP database (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} link-state-database [<lsp_id>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} link-state-database lsp",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        level: str = "*",
        lsp_id: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(level, "level")
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} link-state-database lsp"
            if lsp_id:
                validate_input(lsp_id, "lsp_id")
                cmd += f" {lsp_id}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis_data = get_isis_data(parsed_json)
            levels_data = isis_data.get("levels", {}).get("level", [])

            database_dict: Dict[str, TypeAny] = {}
            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]

            for level in levels_data:
                lsdb_data = level.get("link-state-database", {}).get("lsp", [])

                for lsp in lsdb_data:
                    lsp_id_val = lsp.get("lsp-id")
                    if not lsp_id_val:
                        continue

                    state = lsp.get("state", {})

                    db_entry: Dict[str, TypeAny] = {
                        "lsp-id": lsp_id_val,
                    }

                    # Basic state
                    sequence = state.get("sequence-number")
                    if sequence is not None:
                        db_entry["sequence"] = sequence

                    checksum = state.get("checksum")
                    if checksum is not None:
                        db_entry["checksum"] = checksum

                    lifetime = state.get("remaining-lifetime")
                    if lifetime is not None:
                        db_entry["remaining-lifetime"] = lifetime

                    timestamp = state.get("received-timestamp")
                    if timestamp:
                        db_entry["received-timestamp"] = timestamp

                    max_area = state.get("maximum-area-addresses")
                    if max_area is not None:
                        db_entry["maximum-area-addresses"] = max_area

                    pdu_len = state.get("pdu-length")
                    if pdu_len is not None:
                        db_entry["pdu-length"] = pdu_len

                    # ArcOS augments
                    system_id = state.get(f"{ARCOS_ISIS_AUGMENTS}:system-id")
                    if system_id:
                        db_entry["system-id"] = system_id

                    overload = state.get(f"{ARCOS_ISIS_AUGMENTS}:overload-bit")
                    if overload is not None:
                        db_entry["overload-bit"] = overload

                    attached = state.get(f"{ARCOS_ISIS_AUGMENTS}:attached-bit")
                    if attached is not None:
                        db_entry["attached-bit"] = attached

                    is_type = state.get(f"{ARCOS_ISIS_AUGMENTS}:is-type")
                    if is_type:
                        db_entry["is-type"] = is_type

                    recv_lifetime = state.get(
                        f"{ARCOS_ISIS_AUGMENTS}:received-remaining-lifetime"
                    )
                    if recv_lifetime is not None:
                        db_entry["received-remaining-lifetime"] = recv_lifetime

                    update_ifindex = state.get(
                        f"{ARCOS_ISIS_AUGMENTS}:last-update-ifindex"
                    )
                    if update_ifindex is not None:
                        db_entry["last-update-ifindex"] = update_ifindex

                    update_time = state.get(f"{ARCOS_ISIS_AUGMENTS}:last-update-time")
                    if update_time:
                        db_entry["last-update-time"] = update_time

                    srm_count = state.get(f"{ARCOS_ISIS_AUGMENTS}:srm-count")
                    if srm_count is not None:
                        db_entry["srm-count"] = srm_count

                    ssn_count = state.get(f"{ARCOS_ISIS_AUGMENTS}:ssn-count")
                    if ssn_count is not None:
                        db_entry["ssn-count"] = ssn_count

                    # TLVs
                    tlvs_data = lsp.get("tlvs", {}).get("tlv", [])
                    if tlvs_data:
                        tlv_info: Dict[str, TypeAny] = {}

                        for tlv in tlvs_data:
                            tlv_type = tlv.get("type", "")

                            # Area addresses
                            if "AREA_ADDRESSES" in tlv_type:
                                area_addrs = (
                                    tlv.get("area-addresses", {})
                                    .get("state", {})
                                    .get("address")
                                )
                                if area_addrs:
                                    tlv_info["area-addresses"] = area_addrs

                            # Hostname
                            elif "DYNAMIC_NAME" in tlv_type:
                                hostname = (
                                    tlv.get("hostname", {})
                                    .get("state", {})
                                    .get("hostname")
                                )
                                if hostname:
                                    tlv_info["hostname"] = hostname

                            # NLPID
                            elif "NLPID" in tlv_type:
                                nlpid = (
                                    tlv.get("nlpid", {}).get("state", {}).get("nlpid")
                                )
                                if nlpid:
                                    tlv_info["nlpid"] = nlpid

                            # IPv4 interface addresses
                            elif "IPV4_INTERFACE_ADDRESSES" in tlv_type:
                                ipv4_addrs = (
                                    tlv.get("ipv4-interface-addresses", {})
                                    .get("state", {})
                                    .get("address")
                                )
                                if ipv4_addrs:
                                    tlv_info["ipv4-interface-addresses"] = ipv4_addrs

                            # IPv6 interface addresses
                            elif "IPV6_INTERFACE_ADDRESSES" in tlv_type:
                                ipv6_addrs = (
                                    tlv.get("ipv6-interface-addresses", {})
                                    .get("state", {})
                                    .get("address")
                                )
                                if ipv6_addrs:
                                    tlv_info["ipv6-interface-addresses"] = ipv6_addrs

                            # IPv4 TE Router ID
                            elif "IPV4_TE_ROUTER_ID" in tlv_type:
                                router_id = (
                                    tlv.get("ipv4-te-router-id", {})
                                    .get("state", {})
                                    .get("router-id")
                                )
                                if router_id:
                                    tlv_info["ipv4-te-router-id"] = router_id

                            # IPv6 TE Router ID
                            elif "IPV6_TE_ROUTER_ID" in tlv_type:
                                router_id = (
                                    tlv.get("ipv6-te-router-id", {})
                                    .get("state", {})
                                    .get("router-id")
                                )
                                if router_id:
                                    tlv_info["ipv6-te-router-id"] = router_id

                            # SRv6 Locators (ArcOS augment)
                            elif "SRV6_LOCATOR" in tlv_type:
                                locators_data = tlv.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:srv6-locators", {}
                                ).get("locator", [])
                                if locators_data:
                                    locators = []
                                    for loc in locators_data:
                                        loc_state = loc.get("state", {})
                                        algo = loc_state.get("algorithm")
                                        # Handle algorithm - can be string or numeric
                                        if algo and ":" in str(algo):
                                            algo = str(algo).split(":")[-1]

                                        loc_info: Dict[str, TypeAny] = {
                                            "locator": loc_state.get("locator"),
                                            "mt-id": loc_state.get("mt-id"),
                                            "metric": loc_state.get("metric"),
                                            "algorithm": algo,
                                        }
                                        if loc_state.get("flags"):
                                            loc_info["flags"] = loc_state["flags"]

                                        # Parse locator subTLVs (End SID, prefix flags)
                                        loc_subtlvs = loc.get("subtlvs", {}).get("subtlv", [])
                                        for loc_sub in loc_subtlvs:
                                            loc_sub_type = loc_sub.get("type", "")

                                            # Prefix Flags
                                            if "PREFIX_FLAGS" in loc_sub_type:
                                                flags = (
                                                    loc_sub.get("prefix-attribute-flags", {})
                                                    .get("state", {})
                                                    .get("flags")
                                                )
                                                if flags:
                                                    loc_info["flags"] = flags

                                            # SRv6 End SID
                                            elif "END_SID" in loc_sub_type:
                                                end_sids_data = loc_sub.get(
                                                    "srv6-end-sids", {}
                                                ).get("end-sid", [])
                                                if end_sids_data:
                                                    end_sids = []
                                                    for end_sid in end_sids_data:
                                                        es_state = end_sid.get("state", {})
                                                        es_info: Dict[str, TypeAny] = {
                                                            "sid": es_state.get("sid"),
                                                        }

                                                        func = es_state.get("endpoint-func")
                                                        if func:
                                                            if ":" in str(func):
                                                                func = str(func).split(":")[-1]
                                                            es_info["endpoint-func"] = func

                                                        # Parse SID structure
                                                        es_subtlvs = end_sid.get(
                                                            "subsubtlvs", {}
                                                        ).get("subsubtlv", [])
                                                        for es_sub in es_subtlvs:
                                                            if "SID_STRUCTURE" in es_sub.get("type", ""):
                                                                struct = (
                                                                    es_sub.get("srv6-sid-structure", {})
                                                                    .get("state", {})
                                                                )
                                                                if struct:
                                                                    es_info["sid-structure"] = {
                                                                        "lb": struct.get("lb-length"),
                                                                        "ln": struct.get("ln-length"),
                                                                        "fun": struct.get("fun-length"),
                                                                        "arg": struct.get("arg-length"),
                                                                    }

                                                        end_sids.append(es_info)

                                                    if end_sids:
                                                        loc_info["end-sids"] = end_sids

                                        locators.append(loc_info)
                                    if locators:
                                        tlv_info["srv6-locators"] = locators

                            # Router capabilities
                            elif "ROUTER_CAPABILITY" in tlv_type:
                                cap_list = tlv.get("router-capabilities", {}).get(
                                    "capability", []
                                )
                                if cap_list:
                                    cap = cap_list[0]
                                    cap_state = cap.get("state", {})
                                    cap_info: Dict[str, TypeAny] = {}

                                    # Basic capability info
                                    if "instance-number" in cap_state:
                                        cap_info["instance-number"] = cap_state["instance-number"]
                                    if "router-id" in cap_state:
                                        cap_info["router-id"] = cap_state["router-id"]

                                    # Parse Router Capability subTLVs
                                    subtlvs = cap.get("subtlvs", {}).get("subtlvs", [])
                                    for subtlv in subtlvs:
                                        subtlv_type = subtlv.get("subtlv-type", "")

                                        # SR Algorithm
                                        if "SR_ALGORITHM" in subtlv_type:
                                            algos = (
                                                subtlv.get("segment-routing-algorithms", {})
                                                .get("state", {})
                                                .get("algorithm")
                                            )
                                            if algos:
                                                cap_info["sr-algorithms"] = algos

                                        # SR Capability (SRGB)
                                        elif "SR_CAPABILITY" in subtlv_type and "SRV6" not in subtlv_type:
                                            sr_state = (
                                                subtlv.get("segment-routing-capability", {})
                                                .get("state", {})
                                            )
                                            if sr_state:
                                                sr_cap: Dict[str, TypeAny] = {}
                                                if "flags" in sr_state:
                                                    sr_cap["flags"] = sr_state["flags"]
                                                if "range" in sr_state:
                                                    sr_cap["range"] = sr_state["range"]
                                                if "label" in sr_state:
                                                    sr_cap["label"] = sr_state["label"]
                                                if sr_cap:
                                                    cap_info["sr-capability"] = sr_cap

                                        # SRLB
                                        elif "SRLB" in subtlv_type:
                                            srlb_state = (
                                                subtlv.get(f"{ARCOS_ISIS_AUGMENTS}:node-srlb", {})
                                                .get("state", {})
                                            )
                                            if srlb_state:
                                                srlb: Dict[str, TypeAny] = {}
                                                if "range" in srlb_state:
                                                    srlb["range"] = srlb_state["range"]
                                                if "label" in srlb_state:
                                                    srlb["label"] = srlb_state["label"]
                                                if srlb:
                                                    cap_info["srlb"] = srlb

                                        # IPv6 TE Router ID
                                        elif "IPV6_TE_ROUTER_ID" in subtlv_type:
                                            ipv6_rid = (
                                                subtlv.get(f"{ARCOS_ISIS_AUGMENTS}:ipv6-te-router-id", {})
                                                .get("state", {})
                                                .get("router-id")
                                            )
                                            if ipv6_rid:
                                                cap_info["ipv6-te-router-id"] = ipv6_rid

                                        # Node MSD
                                        elif "NODE_MSD" in subtlv_type:
                                            msds = (
                                                subtlv.get(f"{ARCOS_ISIS_AUGMENTS}:node-msds", {})
                                                .get("msd", [])
                                            )
                                            if msds:
                                                msd_info: Dict[str, TypeAny] = {}
                                                for msd in msds:
                                                    msd_state = msd.get("state", {})
                                                    msd_type = msd_state.get("type", "")
                                                    msd_val = msd_state.get("value")
                                                    if msd_val is not None:
                                                        # Strip namespace prefix and convert to snake_case
                                                        key = msd_type.split(":")[-1].lower()
                                                        msd_info[key] = msd_val
                                                if msd_info:
                                                    cap_info["node-msd"] = msd_info

                                        # Flex-Algo Definition (FAD)
                                        elif "FLEX_ALGO_DEFINITION" in subtlv_type:
                                            fads = (
                                                subtlv.get(f"{ARCOS_ISIS_AUGMENTS}:flex-algo-definitions", {})
                                                .get("flex-algo-definition", [])
                                            )
                                            if fads:
                                                fad_info: Dict[str, TypeAny] = {}
                                                for fad in fads:
                                                    fad_id = fad.get("id")
                                                    if fad_id is None:
                                                        continue
                                                    fad_state = fad.get("state", {})
                                                    fad_entry: Dict[str, TypeAny] = {}
                                                    if "priority" in fad_state:
                                                        fad_entry["priority"] = fad_state["priority"]
                                                    metric_type = fad_state.get("metric-type")
                                                    if metric_type:
                                                        # Strip namespace prefix
                                                        fad_entry["metric-type"] = metric_type.split(":")[-1]
                                                    if fad_entry:
                                                        fad_info[str(fad_id)] = fad_entry
                                                if fad_info:
                                                    cap_info["flex-algo-definitions"] = fad_info

                                    if cap_info:
                                        tlv_info["router-capabilities"] = cap_info

                            # Extended IPv4 reachability
                            elif "EXTENDED_IPV4_REACHABILITY" in tlv_type:
                                prefixes_data = (
                                    tlv.get("extended-ipv4-reachability", {})
                                    .get("prefixes", {})
                                    .get("prefix", [])
                                )
                                if prefixes_data:
                                    ext4 = db_entry.setdefault(
                                        "extended-ipv4-reachability", {}
                                    )
                                    for pfx in prefixes_data:
                                        prefix_str = pfx.get("prefix")
                                        state_pfx = pfx.get("state", {})

                                        if not prefix_str:
                                            prefix_str = state_pfx.get("ipv4-prefix")
                                        if not prefix_str:
                                            continue

                                        parts = prefix_str.split("/")
                                        ip_prefix = parts[0]
                                        prefix_len = (
                                            parts[1] if len(parts) > 1 else None
                                        )

                                        metric = state_pfx.get("metric")
                                        up_down = state_pfx.get("up-down")

                                        pfx_info: Dict[str, TypeAny] = {
                                            "ip-prefix": ip_prefix,
                                        }

                                        if prefix_len is not None:
                                            try:
                                                pfx_info["prefix-len"] = int(prefix_len)
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix-len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if up_down is not None:
                                            pfx_info["up-down"] = bool(up_down)

                                        # Parse prefix subTLVs
                                        sub_tlvs = pfx.get("subTLVs", {}).get(
                                            "subTLVs", []
                                        )
                                        for sub in sub_tlvs:
                                            stype = sub.get("subtlv-type", "")

                                            # Prefix Flags
                                            if "TLV135_PREFIX_FLAGS" in stype:
                                                flags_state = sub.get("flags", {}).get(
                                                    "state", {}
                                                )
                                                flags = flags_state.get("flags")
                                                if flags is not None:
                                                    pfx_info["flags"] = flags

                                            # Prefix Tag
                                            elif "TLV135_TAG" in stype:
                                                tag_state = sub.get("tag", {}).get(
                                                    "state", {}
                                                )
                                                tag32 = tag_state.get("tag32")
                                                if tag32:
                                                    pfx_info["tag"] = tag32

                                            # Prefix SID (SR-MPLS)
                                            elif "PREFIX_SID" in stype:
                                                psids_data = sub.get(
                                                    f"{ARCOS_ISIS_AUGMENTS}:prefix-sids", {}
                                                ).get("prefix-sid", [])
                                                if psids_data:
                                                    prefix_sids = []
                                                    for psid in psids_data:
                                                        psid_state = psid.get("state", {})
                                                        psid_info: Dict[str, TypeAny] = {}

                                                        algo = psid_state.get("algorithm")
                                                        if algo:
                                                            # Strip namespace prefix
                                                            if ":" in str(algo):
                                                                algo = str(algo).split(":")[-1]
                                                            psid_info["algorithm"] = algo

                                                        sid_val = psid_state.get("sid")
                                                        if sid_val is not None:
                                                            psid_info["sid"] = sid_val

                                                        sid_flags = psid_state.get("flags")
                                                        if sid_flags:
                                                            psid_info["flags"] = sid_flags

                                                        if psid_info:
                                                            prefix_sids.append(psid_info)

                                                    if prefix_sids:
                                                        pfx_info["prefix-sids"] = prefix_sids

                                        ext4[prefix_str] = pfx_info

                            # MT IPv6 reachability
                            elif "MT_IPV6_REACHABILITY" in tlv_type:
                                prefixes_data = (
                                    tlv.get("mt-ipv6-reachability", {})
                                    .get("prefixes", {})
                                    .get("prefix", [])
                                )
                                if prefixes_data:
                                    mt6 = db_entry.setdefault(
                                        "mt-ipv6-reachability", {}
                                    )
                                    for pfx in prefixes_data:
                                        prefix_str = pfx.get("prefix")
                                        state_pfx = pfx.get("state", {})

                                        if not prefix_str:
                                            prefix_str = state_pfx.get("prefix")
                                        if not prefix_str:
                                            continue

                                        parts = prefix_str.split("/")
                                        ip_prefix = parts[0]
                                        prefix_len = (
                                            parts[1] if len(parts) > 1 else None
                                        )

                                        metric = state_pfx.get("metric")
                                        mt_id = state_pfx.get("mt-id") or pfx.get(
                                            "mt-id"
                                        )
                                        up_down = state_pfx.get("up-down")

                                        pfx_info: Dict[str, TypeAny] = {
                                            "ip-prefix": ip_prefix,
                                        }

                                        if prefix_len is not None:
                                            try:
                                                pfx_info["prefix-len"] = int(prefix_len)
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix-len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if mt_id is not None:
                                            pfx_info["mt-id"] = mt_id

                                        if up_down is not None:
                                            pfx_info["up-down"] = bool(up_down)

                                        # Parse MT IPv6 prefix subTLVs (Prefix SID)
                                        sub_tlvs = pfx.get("subTLVs", {}).get(
                                            "subTLVs", []
                                        )
                                        self._parse_prefix_subtlvs(sub_tlvs, pfx_info)

                                        mt6[prefix_str] = pfx_info

                            # IPv6 Reachability (non-MT, TLV 236)
                            elif "IPV6_REACHABILITY" in tlv_type and "MT_" not in tlv_type:
                                prefixes_data = (
                                    tlv.get("ipv6-reachability", {})
                                    .get("prefixes", {})
                                    .get("prefix", [])
                                )
                                if prefixes_data:
                                    ipv6_reach = db_entry.setdefault(
                                        "ipv6-reachability", {}
                                    )
                                    for pfx in prefixes_data:
                                        prefix_str = pfx.get("prefix")
                                        state_pfx = pfx.get("state", {})

                                        if not prefix_str:
                                            prefix_str = state_pfx.get("prefix")
                                        if not prefix_str:
                                            continue

                                        parts = prefix_str.split("/")
                                        ip_prefix = parts[0]
                                        prefix_len = (
                                            parts[1] if len(parts) > 1 else None
                                        )

                                        metric = state_pfx.get("metric")
                                        up_down = state_pfx.get("up-down")

                                        pfx_info: Dict[str, TypeAny] = {
                                            "ip-prefix": ip_prefix,
                                        }

                                        if prefix_len is not None:
                                            try:
                                                pfx_info["prefix-len"] = int(prefix_len)
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix-len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if up_down is not None:
                                            pfx_info["up-down"] = bool(up_down)

                                        # Parse IPv6 prefix subTLVs (Prefix SID)
                                        sub_tlvs = pfx.get("subTLVs", {}).get(
                                            "subTLVs", []
                                        )
                                        self._parse_prefix_subtlvs(sub_tlvs, pfx_info)

                                        ipv6_reach[prefix_str] = pfx_info

                            # Extended IS Reachability (neighbors/links)
                            elif "EXTENDED_IS_REACHABILITY" in tlv_type:
                                neighbors_data = (
                                    tlv.get("extended-is-reachability", {})
                                    .get("neighbors", {})
                                    .get("neighbor", [])
                                )
                                if neighbors_data:
                                    ext_is = db_entry.setdefault(
                                        "extended-is-neighbor", {}
                                    )
                                    for neighbor in neighbors_data:
                                        sys_id = neighbor.get("system-id")
                                        if not sys_id:
                                            continue

                                        instance_id = neighbor.get("instance-id")
                                        nbr_state = neighbor.get("state", {})

                                        # Use system-id + instance-id as key for uniqueness
                                        nbr_key = f"{sys_id}"
                                        if instance_id:
                                            nbr_key = f"{sys_id}:{instance_id}"

                                        nbr_info: Dict[str, TypeAny] = {
                                            "system-id": sys_id,
                                            "metric": nbr_state.get("metric"),
                                        }

                                        if instance_id:
                                            nbr_info["instance-id"] = instance_id

                                        two_way = nbr_state.get(
                                            f"{ARCOS_ISIS_AUGMENTS}:two-way-connectivity"
                                        )
                                        if two_way is not None:
                                            nbr_info["two-way"] = two_way

                                        # Parse neighbor subTLVs
                                        sub_tlvs = neighbor.get("subTLVs", {}).get(
                                            "subTLVs", []
                                        )
                                        self._parse_is_neighbor_subtlvs(sub_tlvs, nbr_info)

                                        ext_is[nbr_key] = nbr_info

                            # MT IS Neighbors (MT_ISN TLV)
                            elif "MT_ISN" in tlv_type:
                                mt_neighbors_data = (
                                    tlv.get("mt-isn", {})
                                    .get("neighbors", {})
                                    .get("neighbor", [])
                                )
                                if mt_neighbors_data:
                                    mt_is = db_entry.setdefault("mt-is-neighbor", {})
                                    for neighbor in mt_neighbors_data:
                                        sys_id = neighbor.get("system-id")
                                        mt_id = neighbor.get("mt-id")
                                        if not sys_id:
                                            continue

                                        # MT_ISN has instances under each neighbor
                                        instances = (
                                            neighbor.get("instances", {}).get("instance", [])
                                        )

                                        for instance in instances:
                                            inst_id = instance.get("id")
                                            inst_state = instance.get("state", {})

                                            # Use system-id + mt-id + instance-id as key
                                            nbr_key = f"{sys_id}"
                                            if mt_id is not None:
                                                nbr_key = f"{sys_id}:mt{mt_id}"
                                            if inst_id:
                                                nbr_key = f"{nbr_key}:{inst_id}"

                                            nbr_info: Dict[str, TypeAny] = {
                                                "system-id": sys_id,
                                                "metric": inst_state.get("metric"),
                                            }

                                            if mt_id is not None:
                                                nbr_info["mt-id"] = mt_id

                                            if inst_id:
                                                nbr_info["instance-id"] = inst_id

                                            two_way = inst_state.get(
                                                f"{ARCOS_ISIS_AUGMENTS}:two-way-connectivity"
                                            )
                                            if two_way is not None:
                                                nbr_info["two-way"] = two_way

                                            # Parse instance subTLVs (same as Extended IS)
                                            sub_tlvs = instance.get("subTLVs", {}).get(
                                                "subTLVs", []
                                            )
                                            self._parse_is_neighbor_subtlvs(sub_tlvs, nbr_info)

                                            mt_is[nbr_key] = nbr_info

                        if tlv_info:
                            db_entry["tlvs"] = tlv_info

                    database_dict[lsp_id_val] = db_entry

            if database_dict:
                ni_isis["database"] = database_dict

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS LSP data: %s", exc)

        return ret_dict

    def _parse_is_neighbor_subtlvs(
        self, sub_tlvs: list, nbr_info: Dict[str, TypeAny]
    ) -> None:
        """Parse Extended IS Reachability neighbor subTLVs.

        Handles: Link ID, IPv4/IPv6 addresses, Adjacency SID, ASLA, SRv6 End.X SID.
        """
        for sub in sub_tlvs:
            stype = sub.get("subtlv-type", "")

            # Link ID (local/remote)
            if "TLV22_LINK_ID" in stype:
                link_state = sub.get("link-id", {}).get("state", {})
                if link_state:
                    nbr_info["link-id"] = {
                        "local": link_state.get("local"),
                        "remote": link_state.get("remote"),
                    }

            # IPv4 Interface Address
            elif "TLV22_IPV4_INTERFACE_ADDRESS" in stype:
                addrs = (
                    sub.get("ipv4-interface-address", {})
                    .get("state", {})
                    .get("ipv4-interface-address")
                )
                if addrs:
                    nbr_info["ipv4-interface-address"] = addrs

            # IPv4 Neighbor Address
            elif "TLV22_IPV4_NEIGHBOR_ADDRESS" in stype:
                addrs = (
                    sub.get("ipv4-neighbor-address", {})
                    .get("state", {})
                    .get("ipv4-neighbor-address")
                )
                if addrs:
                    nbr_info["ipv4-neighbor-address"] = addrs

            # IPv6 Interface Address
            elif "TLV22_IPV6_INTERFACE_ADDRESS" in stype:
                addrs = (
                    sub.get("ipv6-interface-address", {})
                    .get("state", {})
                    .get("ipv6-interface-address")
                )
                if addrs:
                    nbr_info["ipv6-interface-address"] = addrs

            # SR-MPLS Adjacency SID
            elif "ADJACENCY_SID" in stype:
                adj_sids_data = sub.get(
                    f"{ARCOS_ISIS_AUGMENTS}:adjacency-sids", {}
                ).get("adjacency-sid", [])
                if adj_sids_data:
                    adj_sids = []
                    for adj_sid in adj_sids_data:
                        sid_state = adj_sid.get("state", {})
                        sid_info: Dict[str, TypeAny] = {
                            "sid": sid_state.get("value"),
                        }
                        if "flags" in sid_state:
                            sid_info["flags"] = sid_state["flags"]
                        if "weight" in sid_state:
                            sid_info["weight"] = sid_state["weight"]
                        adj_sids.append(sid_info)
                    if adj_sids:
                        nbr_info["adjacency-sids"] = adj_sids

            # ASLA (Application-Specific Link Attributes)
            elif "ASLA" in stype:
                aslas_data = sub.get(
                    f"{ARCOS_ISIS_AUGMENTS}:aslas", {}
                ).get("asla", [])
                if aslas_data:
                    for asla in aslas_data:
                        asla_state = asla.get("state", {})
                        asla_info: Dict[str, TypeAny] = {}

                        app = asla_state.get("standard-applications")
                        if app:
                            asla_info["application"] = app

                        # Parse ASLA subsubTLVs
                        subsubtlvs = asla.get("subsubtlvs", {}).get("subsubtlv", [])
                        for subsub in subsubtlvs:
                            subsub_type = subsub.get("type", "")

                            # Admin Groups
                            if "ADMIN_GROUP_TYPE" in subsub_type:
                                groups = (
                                    subsub.get("admin-groups", {})
                                    .get("state", {})
                                    .get("admin-group")
                                )
                                if groups:
                                    asla_info["admin-groups"] = groups

                            # Extended Admin Groups
                            elif "EXTENDED_ADMIN_GROUP_TYPE" in subsub_type:
                                groups = (
                                    subsub.get("extended-admin-groups", {})
                                    .get("state", {})
                                    .get("extended-admin-group")
                                )
                                if groups:
                                    asla_info["extended-admin-groups"] = groups

                            # TE Default Metric
                            elif "TE_DEFAULT_METRIC_TYPE" in subsub_type:
                                metric = (
                                    subsub.get("te-default-metric", {})
                                    .get("state", {})
                                    .get("metric")
                                )
                                if metric is not None:
                                    asla_info["te-metric"] = metric

                            # Min/Max Delay
                            elif "MIN_MAX_DELAY_METRIC_TYPE" in subsub_type:
                                delay_state = subsub.get("min-max-delay", {}).get(
                                    "state", {}
                                )
                                if "min-delay" in delay_state:
                                    asla_info["min-delay"] = delay_state["min-delay"]
                                if "max-delay" in delay_state:
                                    asla_info["max-delay"] = delay_state["max-delay"]

                        if asla_info:
                            nbr_info["asla"] = asla_info

            # SRv6 End.X SID
            elif "SRV6_END_X_SID" in stype:
                end_x_data = sub.get(
                    f"{ARCOS_ISIS_AUGMENTS}:end-x-sids", {}
                ).get("end-x-sid", [])
                if end_x_data:
                    end_x_sids = []
                    for end_x in end_x_data:
                        end_x_state = end_x.get("state", {})
                        end_x_info: Dict[str, TypeAny] = {
                            "sid": end_x_state.get("sid"),
                        }

                        algo = end_x_state.get("algorithm")
                        if algo:
                            # Strip namespace prefix
                            if ":" in str(algo):
                                algo = str(algo).split(":")[-1]
                            end_x_info["algorithm"] = algo

                        if "weight" in end_x_state:
                            end_x_info["weight"] = end_x_state["weight"]

                        func = end_x_state.get("endpoint-func")
                        if func:
                            # Strip namespace prefix
                            if ":" in str(func):
                                func = str(func).split(":")[-1]
                            end_x_info["endpoint-func"] = func

                        # Parse SID structure subsubTLV
                        subsubtlvs = end_x.get("subsubtlvs", {}).get("subsubtlv", [])
                        for subsub in subsubtlvs:
                            if "SRV6_SID_STRUCTURE" in subsub.get("type", ""):
                                struct_state = (
                                    subsub.get("srv6-sid-structure", {})
                                    .get("state", {})
                                )
                                if struct_state:
                                    end_x_info["sid-structure"] = {
                                        "lb": struct_state.get("lb-length"),
                                        "ln": struct_state.get("ln-length"),
                                        "fun": struct_state.get("fun-length"),
                                        "arg": struct_state.get("arg-length"),
                                    }

                        end_x_sids.append(end_x_info)

                    if end_x_sids:
                        nbr_info["end-x-sids"] = end_x_sids

    def _parse_prefix_subtlvs(
        self, sub_tlvs: list, pfx_info: Dict[str, TypeAny]
    ) -> None:
        """Parse prefix subTLVs for IPv4/IPv6 reachability.

        Handles: Prefix Flags, Prefix Tag, Prefix SID (SR-MPLS).
        """
        for sub in sub_tlvs:
            stype = sub.get("subtlv-type", "")

            # Prefix Flags (TLV135/TLV236)
            if "PREFIX_FLAGS" in stype:
                flags_state = sub.get("flags", {}).get("state", {})
                flags = flags_state.get("flags")
                if flags is not None:
                    pfx_info["flags"] = flags

            # Prefix Tag
            elif "TAG" in stype and "TAG64" not in stype:
                tag_state = sub.get("tag", {}).get("state", {})
                tag32 = tag_state.get("tag32")
                if tag32:
                    pfx_info["tag"] = tag32

            # Prefix SID (SR-MPLS)
            elif "PREFIX_SID" in stype:
                psids_data = sub.get(
                    f"{ARCOS_ISIS_AUGMENTS}:prefix-sids", {}
                ).get("prefix-sid", [])
                if psids_data:
                    prefix_sids = []
                    for psid in psids_data:
                        psid_state = psid.get("state", {})
                        psid_info: Dict[str, TypeAny] = {}

                        algo = psid_state.get("algorithm")
                        if algo:
                            # Strip namespace prefix
                            if ":" in str(algo):
                                algo = str(algo).split(":")[-1]
                            psid_info["algorithm"] = algo

                        sid_val = psid_state.get("sid")
                        if sid_val is not None:
                            psid_info["sid"] = sid_val

                        sid_flags = psid_state.get("flags")
                        if sid_flags:
                            psid_info["flags"] = sid_flags

                        if psid_info:
                            prefix_sids.append(psid_info)

                    if prefix_sids:
                        pfx_info["prefix-sids"] = prefix_sids


class ShowIsisInterfaceSchema(MetaParser):
    """Schema for ArcOS ISIS per-interface operational state and counters.

    Convention-compliant: underscored keys, flattened state/config,
    ALL fields Optional, ALL prefixes stripped.
    """

    schema = {
        "network-instance": {
            Any(): {
                Optional("isis"): {
                    Any(): {
                        Optional("interfaces"): {
                            Any(): {
                                # Interface state (flattened from state{})
                                Optional("enabled"): bool,
                                Optional("interface_id"): str,
                                Optional("passive"): bool,
                                Optional("hello_padding"): str,
                                Optional("circuit_type"): str,
                                Optional("network_type"): str,
                                Optional("protocol_up"): bool,
                                Optional("snpa"): str,
                                Optional("mtu"): int,
                                Optional("ifindex"): int,
                                Optional("update_index"): int,
                                Optional("speed"): int,
                                # Circuit counters
                                Optional("circuit_counters"): {
                                    Optional("adj_changes"): int,
                                    Optional("init_fails"): int,
                                    Optional("rejected_adj"): int,
                                    Optional("id_field_len_mismatches"): int,
                                    Optional("max_area_address_mismatches"): int,
                                    Optional("auth_type_fails"): int,
                                    Optional("auth_fails"): int,
                                    Optional("lan_dis_changes"): int,
                                    Optional("adj_number"): int,
                                    Optional("subnet_mismatches"): int,
                                    Optional("duplicate_addresses"): int,
                                    Optional("martian_addresses"): int,
                                    Optional("missing_addresses"): int,
                                },
                                # Authentication
                                Optional("authentication"): {
                                    Optional("hello_authentication"): bool,
                                    Optional("auth_type"): str,
                                    Optional("crypto_algorithm"): str,
                                },
                                # AFI-SAFI
                                Optional("afi_safi"): {
                                    Any(): {
                                        Optional("afi_name"): str,
                                        Optional("safi_name"): str,
                                        Optional("enabled"): bool,
                                        Optional("ipv4_unnumbered"): bool,
                                        Optional("fast_reroute"): {
                                            Optional("ip_enabled"): bool,
                                            Optional("ti_lfa_srv6_enabled"): bool,
                                            Optional("ti_lfa_sr_mpls_enabled"): bool,
                                        },
                                    }
                                },
                                # Timers
                                Optional("timers"): {
                                    Optional("csnp_interval"): int,
                                    Optional("lsp_pacing_interval"): int,
                                    Optional("hello_interval"): int,
                                    Optional("hello_multiplier"): int,
                                },
                                # BFD
                                Optional("bfd"): {
                                    Optional("bfd_tlv"): bool,
                                    Optional("profile"): str,
                                },
                                # Fast-reroute
                                Optional("fast_reroute"): {
                                    Optional("srv6_enabled"): bool,
                                    Optional("tiebreakers"): {
                                        Optional("srlg_disjoint"): {
                                            Optional("priority"): int,
                                        },
                                        Optional("node_protecting"): {
                                            Optional("priority"): int,
                                        },
                                    },
                                },
                                # Flexible algorithm
                                Optional("flexible_algorithm"): {
                                    Optional("admin_groups"): list,
                                },
                                # CSNP
                                Optional("csnp_enabled"): bool,
                                # MPLS LDP sync
                                Optional("mpls_ldp_sync_enabled"): bool,
                                # Levels
                                Optional("levels"): {
                                    Any(): {
                                        Optional("enabled"): bool,
                                        Optional("priority"): int,
                                        Optional("metric"): int,
                                        Optional("flexible_algorithm"): {
                                            Optional("te_metric"): int,
                                            Optional("delay_metric"): int,
                                        },
                                        Optional("packet_counters"): {
                                            Any(): {
                                                Optional("received"): int,
                                                Optional("processed"): int,
                                                Optional("dropped"): int,
                                                Optional("sent"): int,
                                                Optional("retransmit"): int,
                                                Optional("no_memory"): int,
                                            }
                                        },
                                        Optional("hello_authentication"): {
                                            Optional("hello_authentication"): bool,
                                            Optional("auth_type"): str,
                                            Optional("crypto_algorithm"): str,
                                        },
                                        Optional("adjacencies"): {
                                            Any(): {
                                                Optional("system_id"): str,
                                                Optional("neighbor_ipv4_address"): str,
                                                Optional("neighbor_ipv6_address"): str,
                                                Optional("local_extended_circuit_id"): int,
                                                Optional("neighbor_extended_circuit_id"): int,
                                                Optional("neighbor_circuit_type"): str,
                                                Optional("adjacency_type"): str,
                                                Optional("adjacency_state"): str,
                                                Optional("remaining_hold_time"): int,
                                                Optional("up_time"): int,
                                                Optional("adjacency_up_time"): str,
                                                Optional("num_state_changes"): int,
                                                Optional("last_state_change_timestamp"): str,
                                                Optional("last_down_reason"): str,
                                                Optional("restart_support"): bool,
                                                Optional("restart_suppress"): bool,
                                                Optional("restart_status"): bool,
                                                Optional("nlpid"): list,
                                                Optional("usable"): bool,
                                                Optional("restart_ack"): bool,
                                                Optional("restart_request"): bool,
                                                Optional("received_multi_topology_ids"): list,
                                                Optional("active_multi_topology_ids"): list,
                                                Optional("bfd"): {
                                                    Optional("bfd_required"): bool,
                                                    Optional("topologies"): {
                                                        Any(): {
                                                            Optional("mt_id"): int,
                                                            Optional("ipv4_bfd_required"): bool,
                                                            Optional("ipv6_bfd_required"): bool,
                                                            Optional("bfd_required"): bool,
                                                            Optional("ipv4_bfd_up"): bool,
                                                            Optional("ipv6_bfd_up"): bool,
                                                            Optional("ipv4_up"): bool,
                                                            Optional("ipv6_up"): bool,
                                                            Optional("usable"): bool,
                                                        }
                                                    },
                                                },
                                                Optional("dynamic_delay_measurement"): {
                                                    Optional("enabled"): bool,
                                                    Optional("num_advertisements_sent"): int,
                                                    Optional("last_sampled_avg_delay_value"): int,
                                                    Optional("last_advertised_min_delay_value"): int,
                                                    Optional("last_advertised_max_delay_value"): int,
                                                    Optional("last_advertised_timestamp"): str,
                                                    Optional("last_advertisement_reason"): str,
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
        }
    }


# ---------------------------------------------------------------------------
# Prefix-stripping helpers for ShowIsisInterface
# ---------------------------------------------------------------------------

# Key prefixes: augment namespace prefixes on JSON keys
_KEY_PREFIXES = [
    f"{ARCOS_ISIS_AUGMENTS}:",
]

# Value prefixes: namespace prefixes on JSON values
_VALUE_PREFIXES = [
    "arcos-isis-types:",
    "openconfig-isis-types:",
    "oc-isis-types:",
    f"{ARCOS_ISIS_AUGMENTS}:",
    "openconfig-keychain-types:",
    "oc-pol-types:",
]


def _strip_key(key: str) -> str:
    """Strip known augment namespace prefix from a JSON key."""
    for prefix in _KEY_PREFIXES:
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def _strip_value(value: str) -> str:
    """Strip known namespace prefix from a JSON value string."""
    if not isinstance(value, str):
        return value
    for prefix in _VALUE_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value




def _get_str(d: Dict, key: str) -> TypeOptional[str]:
    """Get a string value, stripping value prefix. Returns None if absent."""
    val = d.get(key)
    if val is None:
        # Try with augment prefix
        val = d.get(f"{ARCOS_ISIS_AUGMENTS}:{key}")
    if val is None:
        return None
    return _strip_value(str(val))


class ShowIsisInterface(ShowIsisInterfaceSchema):
    """Parser for ArcOS ISIS interface command (JSON format).

    Convention-compliant rewrite: underscored keys, flattened state/config,
    all fields Optional, all prefixes stripped.

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS
            {protocol_instance} interface [<interface>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS "
        "{protocol_instance} interface",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        interface: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            cmd = (
                f"show network-instance {network_instance} "
                f"protocol ISIS {protocol_instance} interface"
            )
            if interface:
                validate_input(interface, "interface")
                cmd += f" {interface}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        parsed_json = load_json_robust(output)

        # Navigate to network-instance list
        data = parsed_json.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        result: Dict[str, TypeAny] = {"network-instance": {}}

        for ni in ni_list:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            for protocol in ni.get("protocols", {}).get("protocol", []):
                if "isis" not in protocol:
                    continue
                proto_name = protocol.get("name", DEFAULT_INSTANCE)

                isis_data = protocol["isis"]
                interfaces_list = (
                    isis_data.get("interfaces", {}).get("interface", [])
                )
                if not interfaces_list:
                    continue

                interfaces_dict: Dict[str, TypeAny] = {}

                for intf in interfaces_list:
                    intf_id = intf.get("interface-id")
                    if not intf_id:
                        continue

                    intf_entry = self._parse_interface(intf)
                    if intf_entry:
                        interfaces_dict[intf_id] = intf_entry

                if interfaces_dict:
                    result["network-instance"].setdefault(ni_name, {})
                    result["network-instance"][ni_name].setdefault("isis", {})
                    result["network-instance"][ni_name]["isis"][proto_name] = {
                        "interfaces": interfaces_dict
                    }

        return result

    # ------------------------------------------------------------------
    # Interface-level extraction
    # ------------------------------------------------------------------

    def _parse_interface(self, intf: Dict) -> Dict[str, TypeAny]:
        """Parse a single interface entry."""
        entry: Dict[str, TypeAny] = {}
        aug = ARCOS_ISIS_AUGMENTS

        # --- Interface state (flatten state{}) ---
        state = intf.get("state", {})
        self._set(entry, "enabled", state.get("enabled"))
        self._set(entry, "interface_id", state.get("interface-id"))
        self._set(entry, "passive", state.get("passive"))
        self._set(entry, "hello_padding", state.get("hello-padding"))

        circuit_type = state.get("circuit-type")
        if circuit_type:
            entry["circuit_type"] = _strip_value(circuit_type)

        self._set(entry, "network_type", state.get(f"{aug}:network-type"))
        self._set(entry, "protocol_up", state.get(f"{aug}:protocol-up"))
        self._set(entry, "snpa", state.get(f"{aug}:snpa"))
        self._set(entry, "mtu", state.get(f"{aug}:mtu"))
        self._set(entry, "ifindex", state.get(f"{aug}:ifindex"))
        self._set(entry, "update_index", state.get(f"{aug}:update-index"))
        self._set(entry, "speed", state.get(f"{aug}:speed"))

        # --- Circuit counters ---
        cc = self._parse_circuit_counters(
            intf.get("circuit-counters", {}).get("state", {})
        )
        if cc:
            entry["circuit_counters"] = cc

        # --- Authentication ---
        auth = self._parse_authentication(intf.get("authentication", {}))
        if auth:
            entry["authentication"] = auth

        # --- AFI-SAFI ---
        afi_safi = self._parse_afi_safi(intf.get("afi-safi", {}))
        if afi_safi:
            entry["afi_safi"] = afi_safi

        # --- Timers ---
        timers = self._parse_timers(intf.get("timers", {}).get("state", {}))
        if timers:
            entry["timers"] = timers

        # --- BFD ---
        bfd = self._parse_interface_bfd(intf.get("bfd", {}))
        if bfd:
            entry["bfd"] = bfd

        # --- Fast-reroute ---
        frr = self._parse_fast_reroute(intf.get(f"{aug}:fast-reroute", {}))
        if frr:
            entry["fast_reroute"] = frr

        # --- Flexible algorithm ---
        flex = intf.get(f"{aug}:flexible-algorithm", {}).get("state", {})
        admin_groups = flex.get("admin-groups")
        if admin_groups:
            entry["flexible_algorithm"] = {"admin_groups": admin_groups}

        # --- CSNP ---
        csnp_state = intf.get(f"{aug}:csnp", {}).get("state", {})
        if "enabled" in csnp_state:
            entry["csnp_enabled"] = csnp_state["enabled"]

        # --- MPLS LDP sync ---
        mpls_state = (
            intf.get(f"{aug}:mpls", {})
            .get("igp-ldp-sync", {})
            .get("state", {})
        )
        if "enabled" in mpls_state:
            entry["mpls_ldp_sync_enabled"] = mpls_state["enabled"]

        # --- Levels ---
        levels = self._parse_levels(intf.get("levels", {}).get("level", []))
        if levels:
            entry["levels"] = levels

        return entry

    # ------------------------------------------------------------------
    # Circuit counters
    # ------------------------------------------------------------------

    def _parse_circuit_counters(self, state: Dict) -> Dict[str, TypeAny]:
        """Parse circuit-counters.state{}, flatten and strip prefixes."""
        if not state:
            return {}

        aug = ARCOS_ISIS_AUGMENTS
        cc: Dict[str, TypeAny] = {}

        # Standard OC fields — JSON key → output key
        _CC_STD_FIELDS = {
            "adj-changes": "adj_changes",
            "init-fails": "init_fails",
            "rejected-adj": "rejected_adj",
            "id-field-len-mismatches": "id_field_len_mismatches",
            "max-area-address-mismatches": "max_area_address_mismatches",
            "auth-type-fails": "auth_type_fails",
            "auth-fails": "auth_fails",
            "lan-dis-changes": "lan_dis_changes",
            "adj-number": "adj_number",
        }
        for json_key, out_key in _CC_STD_FIELDS.items():
            if json_key in state:
                cc[out_key] = state[json_key]

        # Augmented fields
        _CC_AUG_FIELDS = {
            "subnet-mismatches": "subnet_mismatches",
            "duplicate-addresses": "duplicate_addresses",
            "martian-addresses": "martian_addresses",
            "missing-addresses": "missing_addresses",
        }
        for json_key, out_key in _CC_AUG_FIELDS.items():
            aug_key = f"{aug}:{json_key}"
            if aug_key in state:
                cc[out_key] = state[aug_key]

        return cc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _parse_authentication(self, auth_data: Dict) -> Dict[str, TypeAny]:
        """Parse authentication block, flatten state + key.state."""
        if not auth_data:
            return {}

        aug = ARCOS_ISIS_AUGMENTS
        auth: Dict[str, TypeAny] = {}

        auth_state = auth_data.get("state", {})
        if "hello-authentication" in auth_state:
            auth["hello_authentication"] = auth_state["hello-authentication"]

        auth_type = auth_state.get("auth-type")
        if auth_type:
            auth["auth_type"] = _strip_value(auth_type)

        crypto = (
            auth_data.get("key", {})
            .get("state", {})
            .get(f"{aug}:crypto-algorithm")
        )
        if crypto:
            auth["crypto_algorithm"] = _strip_value(crypto)

        return auth

    # ------------------------------------------------------------------
    # AFI-SAFI
    # ------------------------------------------------------------------

    def _parse_afi_safi(self, afi_safi_data: Dict) -> Dict[str, TypeAny]:
        """Parse afi-safi.af[] list, flatten state, strip prefixes."""
        af_list = afi_safi_data.get("af", [])
        if not af_list:
            return {}

        aug = ARCOS_ISIS_AUGMENTS
        result: Dict[str, TypeAny] = {}

        for af in af_list:
            af_state = af.get("state", {})
            afi_name_raw = af_state.get("afi-name", "")
            safi_name_raw = af_state.get("safi-name", "")
            if not afi_name_raw:
                continue

            afi_name = _strip_value(afi_name_raw)
            safi_name = _strip_value(safi_name_raw)
            af_key = f"{afi_name}_{safi_name}" if safi_name else afi_name

            af_entry: Dict[str, TypeAny] = {
                "afi_name": afi_name,
                "safi_name": safi_name,
            }
            self._set(af_entry, "enabled", af_state.get("enabled"))

            # ipv4-unnumbered augment
            ipv4_unnum = af_state.get(f"{aug}:ipv4-unnumbered")
            if ipv4_unnum is not None:
                af_entry["ipv4_unnumbered"] = ipv4_unnum

            # Fast-reroute config per AFI-SAFI
            af_frr = af_state.get(f"{aug}:fast-reroute", {})
            if af_frr:
                frr_entry: Dict[str, TypeAny] = {}
                ip_enabled = (
                    af_frr.get("ip", {}).get("config", {}).get("enabled")
                )
                if ip_enabled is not None:
                    frr_entry["ip_enabled"] = ip_enabled

                ti_lfa_cfg = af_frr.get("ti-lfa", {}).get("config", {})
                srv6_en = ti_lfa_cfg.get("srv6", {}).get("enabled")
                if srv6_en is not None:
                    frr_entry["ti_lfa_srv6_enabled"] = srv6_en
                sr_mpls_en = ti_lfa_cfg.get("sr-mpls", {}).get("enabled")
                if sr_mpls_en is not None:
                    frr_entry["ti_lfa_sr_mpls_enabled"] = sr_mpls_en

                if frr_entry:
                    af_entry["fast_reroute"] = frr_entry

            result[af_key] = af_entry

        return result

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _parse_timers(self, state: Dict) -> Dict[str, TypeAny]:
        """Parse timers.state{}, flatten and strip prefixes."""
        if not state:
            return {}

        aug = ARCOS_ISIS_AUGMENTS
        timers: Dict[str, TypeAny] = {}

        if "csnp-interval" in state:
            timers["csnp_interval"] = int(state["csnp-interval"])
        if "lsp-pacing-interval" in state:
            timers["lsp_pacing_interval"] = int(state["lsp-pacing-interval"])

        hello_int = state.get(f"{aug}:hello-interval")
        if hello_int is not None:
            timers["hello_interval"] = int(hello_int)
        hello_mult = state.get(f"{aug}:hello-multiplier")
        if hello_mult is not None:
            timers["hello_multiplier"] = int(hello_mult)

        return timers

    # ------------------------------------------------------------------
    # Interface-level BFD
    # ------------------------------------------------------------------

    def _parse_interface_bfd(self, bfd_data: Dict) -> Dict[str, TypeAny]:
        """Parse bfd block at interface level."""
        if not bfd_data:
            return {}

        aug = ARCOS_ISIS_AUGMENTS
        bfd: Dict[str, TypeAny] = {}

        bfd_state = bfd_data.get("state", {})
        if "bfd-tlv" in bfd_state:
            bfd["bfd_tlv"] = bfd_state["bfd-tlv"]

        aug_state = bfd_data.get(f"{aug}:state", {})
        if "profile" in aug_state:
            bfd["profile"] = aug_state["profile"]

        return bfd

    # ------------------------------------------------------------------
    # Fast-reroute (interface level)
    # ------------------------------------------------------------------

    def _parse_fast_reroute(self, frr_data: Dict) -> Dict[str, TypeAny]:
        """Parse augmented fast-reroute block at interface level."""
        if not frr_data:
            return {}

        frr: Dict[str, TypeAny] = {}

        ti_lfa_state = frr_data.get("ti-lfa", {}).get("state", {})
        if "srv6-enabled" in ti_lfa_state:
            frr["srv6_enabled"] = ti_lfa_state["srv6-enabled"]

        tiebreaker_data = frr_data.get("tiebreaker", {})
        if tiebreaker_data:
            tiebreakers: Dict[str, TypeAny] = {}
            _TB_TYPES = {
                "srlg-disjoint": "srlg_disjoint",
                "node-protecting": "node_protecting",
            }
            for json_key, out_key in _TB_TYPES.items():
                tb_state = tiebreaker_data.get(json_key, {}).get("state", {})
                if "priority" in tb_state:
                    tiebreakers[out_key] = {
                        "priority": tb_state["priority"]
                    }
            if tiebreakers:
                frr["tiebreakers"] = tiebreakers

        return frr

    # ------------------------------------------------------------------
    # Levels
    # ------------------------------------------------------------------

    def _parse_levels(
        self, levels_list: list
    ) -> Dict[str, TypeAny]:
        """Parse levels.level[] list."""
        if not levels_list:
            return {}

        levels_dict: Dict[str, TypeAny] = {}

        for level in levels_list:
            level_num = level.get("level-number")
            if level_num is None:
                continue

            level_entry = self._parse_single_level(level)
            if level_entry:
                levels_dict[str(level_num)] = level_entry

        return levels_dict

    def _parse_single_level(self, level: Dict) -> Dict[str, TypeAny]:
        """Parse a single level entry."""
        aug = ARCOS_ISIS_AUGMENTS
        entry: Dict[str, TypeAny] = {}

        # Level state (flatten)
        state = level.get("state", {})
        self._set(entry, "enabled", state.get("enabled"))
        self._set(entry, "priority", state.get("priority"))

        metric = state.get(f"{aug}:metric")
        if metric is not None:
            entry["metric"] = metric

        flex_alg = state.get(f"{aug}:flexible-algorithm")
        if flex_alg and isinstance(flex_alg, dict):
            fa_entry: Dict[str, TypeAny] = {}
            if "te-metric" in flex_alg:
                fa_entry["te_metric"] = flex_alg["te-metric"]
            if "delay-metric" in flex_alg:
                fa_entry["delay_metric"] = flex_alg["delay-metric"]
            if fa_entry:
                entry["flexible_algorithm"] = fa_entry

        # Packet counters
        pkt_counters = self._parse_packet_counters(
            level.get("packet-counters", {})
        )
        if pkt_counters:
            entry["packet_counters"] = pkt_counters

        # Level hello-authentication
        hello_auth = self._parse_authentication(
            level.get("hello-authentication", {})
        )
        if hello_auth:
            entry["hello_authentication"] = hello_auth

        # Adjacencies
        adjacencies = self._parse_adjacencies(
            level.get("adjacencies", {}).get("adjacency", [])
        )
        if adjacencies:
            entry["adjacencies"] = adjacencies

        return entry

    # ------------------------------------------------------------------
    # Packet counters
    # ------------------------------------------------------------------

    def _parse_packet_counters(
        self, pkt_data: Dict
    ) -> Dict[str, TypeAny]:
        """Parse packet-counters for a level."""
        if not pkt_data:
            return {}

        aug = ARCOS_ISIS_AUGMENTS
        counters: Dict[str, TypeAny] = {}

        for pkt_type in ("lsp", "iih", "psnp", "csnp", "unknown"):
            pkt_state = pkt_data.get(pkt_type, {}).get("state", {})
            if not pkt_state:
                continue

            pkt_entry: Dict[str, TypeAny] = {}
            for key in (
                "received", "processed", "dropped", "sent", "retransmit",
            ):
                if key in pkt_state:
                    pkt_entry[key] = pkt_state[key]

            # Augment: no-memory
            no_mem = pkt_state.get(f"{aug}:no-memory")
            if no_mem is not None:
                pkt_entry["no_memory"] = no_mem

            if pkt_entry:
                counters[pkt_type] = pkt_entry

        return counters

    # ------------------------------------------------------------------
    # Adjacencies
    # ------------------------------------------------------------------

    def _parse_adjacencies(
        self, adj_list: list
    ) -> Dict[str, TypeAny]:
        """Parse adjacencies.adjacency[] list."""
        if not adj_list:
            return {}

        result: Dict[str, TypeAny] = {}

        for adj in adj_list:
            sys_id = adj.get("system-id")
            if not sys_id:
                continue

            adj_entry = self._parse_single_adjacency(adj)
            if adj_entry:
                result[sys_id] = adj_entry

        return result

    def _parse_single_adjacency(self, adj: Dict) -> Dict[str, TypeAny]:
        """Parse a single adjacency entry."""
        aug = ARCOS_ISIS_AUGMENTS
        entry: Dict[str, TypeAny] = {}

        state = adj.get("state", {})

        # Standard fields
        self._set(entry, "system_id", state.get("system-id"))
        self._set(entry, "neighbor_ipv4_address",
                  state.get("neighbor-ipv4-address"))
        self._set(entry, "neighbor_ipv6_address",
                  state.get("neighbor-ipv6-address"))
        self._set(entry, "local_extended_circuit_id",
                  state.get("local-extended-circuit-id"))
        self._set(entry, "neighbor_extended_circuit_id",
                  state.get("neighbor-extended-circuit-id"))
        self._set(entry, "neighbor_circuit_type",
                  state.get("neighbor-circuit-type"))
        self._set(entry, "adjacency_type", state.get("adjacency-type"))
        self._set(entry, "adjacency_state", state.get("adjacency-state"))
        self._set(entry, "remaining_hold_time",
                  state.get("remaining-hold-time"))
        self._set(entry, "up_time", state.get("up-time"))
        self._set(entry, "restart_support", state.get("restart-support"))
        self._set(entry, "restart_suppress", state.get("restart-suppress"))
        self._set(entry, "restart_status", state.get("restart-status"))
        self._set(entry, "nlpid", state.get("nlpid"))

        # Augmented fields
        adj_up_time = state.get(f"{aug}:adjacency-up-time")
        if adj_up_time:
            entry["adjacency_up_time"] = adj_up_time

        num_sc = state.get(f"{aug}:num-state-changes")
        if num_sc is not None:
            entry["num_state_changes"] = num_sc

        last_ts = state.get(f"{aug}:last-state-change-timestamp")
        if last_ts:
            entry["last_state_change_timestamp"] = last_ts

        last_down = state.get(f"{aug}:last-down-reason")
        if last_down:
            entry["last_down_reason"] = last_down

        self._set(entry, "usable", state.get(f"{aug}:usable"))
        self._set(entry, "restart_ack", state.get(f"{aug}:restart-ack"))
        self._set(entry, "restart_request",
                  state.get(f"{aug}:restart-request"))

        # Multi-topology IDs (strip value prefixes from list items)
        recv_mt = state.get(f"{aug}:received-multi-topology-ids")
        if recv_mt:
            entry["received_multi_topology_ids"] = [
                _strip_value(v) for v in recv_mt
            ]

        active_mt = state.get(f"{aug}:active-multi-topology-ids")
        if active_mt:
            entry["active_multi_topology_ids"] = [
                _strip_value(v) for v in active_mt
            ]

        # Adjacency BFD
        bfd = self._parse_adjacency_bfd(adj.get(f"{aug}:bfd", {}))
        if bfd:
            entry["bfd"] = bfd

        # Dynamic delay measurement
        ddm = self._parse_ddm(
            adj.get(f"{aug}:dynamic-delay-measurement", {})
        )
        if ddm:
            entry["dynamic_delay_measurement"] = ddm

        return entry

    # ------------------------------------------------------------------
    # Adjacency BFD
    # ------------------------------------------------------------------

    def _parse_adjacency_bfd(self, bfd_data: Dict) -> Dict[str, TypeAny]:
        """Parse adjacency-level BFD block."""
        if not bfd_data:
            return {}

        bfd: Dict[str, TypeAny] = {}

        bfd_state = bfd_data.get("state", {})
        if bfd_state.get("bfd-required") is not None:
            bfd["bfd_required"] = bfd_state["bfd-required"]

        topologies_list = (
            bfd_data.get("topologies", {}).get("topology", [])
        )
        if topologies_list:
            _BFD_TOPO_FIELDS = {
                "ipv4-bfd-required": "ipv4_bfd_required",
                "ipv6-bfd-required": "ipv6_bfd_required",
                "bfd-required": "bfd_required",
                "ipv4-bfd-up": "ipv4_bfd_up",
                "ipv6-bfd-up": "ipv6_bfd_up",
                "ipv4-up": "ipv4_up",
                "ipv6-up": "ipv6_up",
                "usable": "usable",
            }
            topologies: Dict[TypeAny, TypeAny] = {}
            for topo in topologies_list:
                mt_id = topo.get("mt-id")
                if mt_id is None:
                    continue

                topo_state = topo.get("state", {})
                topo_entry: Dict[str, TypeAny] = {}
                self._set(topo_entry, "mt_id", topo_state.get("mt-id"))

                for json_key, out_key in _BFD_TOPO_FIELDS.items():
                    if json_key in topo_state:
                        topo_entry[out_key] = topo_state[json_key]

                if topo_entry:
                    topologies[mt_id] = topo_entry

            if topologies:
                bfd["topologies"] = topologies

        return bfd

    # ------------------------------------------------------------------
    # Dynamic delay measurement
    # ------------------------------------------------------------------

    def _parse_ddm(self, ddm_data: Dict) -> Dict[str, TypeAny]:
        """Parse dynamic-delay-measurement block."""
        if not ddm_data:
            return {}

        ddm_state = ddm_data.get("state", {})
        if not ddm_state:
            return {}

        _DDM_FIELDS = {
            "enabled": "enabled",
            "num-advertisements-sent": "num_advertisements_sent",
            "last-sampled-avg-delay-value": "last_sampled_avg_delay_value",
            "last-advertised-min-delay-value": "last_advertised_min_delay_value",
            "last-advertised-max-delay-value": "last_advertised_max_delay_value",
            "last-advertised-timestamp": "last_advertised_timestamp",
            "last-advertisement-reason": "last_advertisement_reason",
        }
        ddm: Dict[str, TypeAny] = {}
        for json_key, out_key in _DDM_FIELDS.items():
            if json_key in ddm_state:
                ddm[out_key] = ddm_state[json_key]

        return ddm

    # ------------------------------------------------------------------
    # Helper: set key only if value is not None
    # ------------------------------------------------------------------

    @staticmethod
    def _set(d: Dict, key: str, value: TypeAny) -> None:
        """Set *key* in *d* only when *value* is not ``None``."""
        if value is not None:
            d[key] = value



class ShowIsisConfigSchema(MetaParser):
    """Schema for ArcOS ISIS running configuration.

    Structured like :class:`ShowIsisInterfaceSchema`, with configuration
    data nested under ``isis[instance]['config']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("config"): {
                            Optional("global"): {
                                Optional("net"): list,
                                Optional("level-capability"): str,
                                Optional("max-ecmp-paths"): int,
                                Optional("graceful-restart-enabled"): bool,
                                Optional("lsp-mtu-size"): int,
                                Optional("segment-routing-enabled"): bool,
                                Optional("auto-cost-reference-bandwidth"): int,
                                Optional("mpls-igp-ldp-sync-enabled"): bool,
                                Optional("hello-authentication"): {
                                    Optional("enabled"): bool,
                                    Optional("keychain"): str,
                                    Optional("auth-type"): str,
                                },
                                Optional("srms"): {
                                    Optional("mapping"): str,
                                    Optional("receive-enabled"): bool,
                                    Optional("advertise-enabled"): bool,
                                },
                                Optional("srv6"): {
                                    Optional("enabled"): bool,
                                    Optional("locators"): list,  # list of locator names
                                },
                                Optional("traffic-engineering"): {
                                    Optional("ipv4-router-id"): str,
                                    Optional("ipv6-router-id"): str,
                                },
                                Optional("micro-loop-avoidance"): {
                                    Optional("srv6-enabled"): bool,
                                    Optional("rib-update-delay"): int,
                                },
                                Optional("lsp-bit"): {
                                    Optional("overload-bit"): {
                                        Optional("set-bit-on-boot"): bool,
                                        Optional("set-bit"): bool,
                                        Optional("advertise-high-metric"): bool,
                                        Optional("reset-triggers"): list,
                                    },
                                    Optional("attached-bit"): {
                                        Optional("ignore-bit"): bool,
                                        Optional("suppress-bit"): bool,
                                    },
                                },
                                Optional("flexible-algorithms"): {
                                    Any(): {  # algorithm ID
                                        "id": int,
                                        Optional("advertise-definition-enabled"): bool,
                                        Optional("metric-type"): str,
                                    }
                                },
                                Optional("dynamic-delay-measurement"): {
                                    Optional("probe-interval"): int,
                                    Optional("advertisement-interval"): int,
                                },
                                Optional("inter-level-policies"): {
                                    Optional("level1-to-level2"): {
                                        Optional("import-policy"): list,
                                    },
                                    Optional("level2-to-level1"): {
                                        Optional("import-policy"): list,
                                    },
                                },
                            },
                            Optional("levels"): {
                                Any(): {  # level number
                                    "level-number": int,
                                    Optional("enabled"): bool,
                                    Optional("authentication"): {
                                        Optional("lsp-authentication"): bool,
                                        Optional("csnp-authentication"): bool,
                                        Optional("psnp-authentication"): bool,
                                        Optional("auth-password"): str,
                                        Optional("crypto-algorithm"): str,
                                        Optional("auth-type"): str,
                                        Optional("keychain"): str,
                                    },
                                    Optional("labeled-preference"): int,
                                    Optional("traffic-engineering-enabled"): bool,
                                }
                            },
                            Optional("afi-safi"): {
                                Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                    "afi-name": str,
                                    "safi-name": str,
                                    "enabled": bool,
                                    Optional("multi-topology-enabled"): bool,
                                    Optional("summary-prefixes"): {
                                        Any(): {  # prefix
                                            "prefix": str,
                                            Optional("level"): str,
                                            Optional("algorithm"): int,
                                            Optional("tag"): int,
                                            Optional("adv-unreachable"): bool,
                                        }
                                    },
                                    Optional("prefix-unreachable"): {
                                        Optional("adv-lifetime"): int,
                                        Optional("adv-metric"): int,
                                        Optional("adv-maximum"): int,
                                        Optional("rx-process"): bool,
                                    },
                                    Optional("default-information"): {
                                        Optional("enabled"): bool,
                                        Optional("export-policy"): list,
                                    },
                                }
                            },
                            Optional("interfaces"): {
                                Any(): {  # interface name
                                    "interface-id": str,
                                    "enabled": bool,
                                    Optional("network-type"): str,
                                    Optional("tag"): list,  # list of integers
                                    Optional("authentication"): {
                                        Optional("hello-authentication"): bool,
                                        Optional("auth-password"): str,
                                        Optional("crypto-algorithm"): str,
                                        Optional("auth-type"): str,
                                        Optional("keychain"): str,
                                    },
                                    Optional("mpls-igp-ldp-sync-enabled"): bool,
                                    Optional("timers"): {
                                        Optional("hello-interval"): int,
                                        Optional("hello-multiplier"): int,
                                    },
                                    Optional("afi-safi"): {
                                        Any(): {  # AFI-SAFI key
                                            "afi-name": str,
                                            "safi-name": str,
                                            "enabled": bool,
                                            Optional("fast-reroute"): {
                                                Optional("ip-enabled"): bool,
                                                Optional("ti-lfa-srv6-enabled"): bool,
                                                Optional("ti-lfa-sr-mpls-enabled"): bool,
                                            },
                                            Optional("adjacency-sids"): list,
                                            Optional("prefix-sids"): list,
                                        }
                                    },
                                    Optional("levels"): {
                                        Any(): {  # level number
                                            "level-number": int,
                                            Optional("enabled"): bool,
                                            Optional("metric"): int,
                                            Optional("flexible-algorithm"): {
                                                Optional("delay-metric"): Or(int, str),
                                                Optional("te-metric"): Or(int, str),
                                            },
                                        }
                                    },
                                    Optional("interface-ref"): {
                                        Optional("interface"): str,
                                        Optional("subinterface"): int,
                                    },
                                }
                            },
                        }
                    }
                }
            }
        }
    }


class ShowIsisConfig(ShowIsisConfigSchema):
    """Parser for ArcOS ISIS running configuration (JSON format).

    Command pattern (before JSON pipe)::

        show running-config network-instance {network_instance} protocol ISIS {protocol_instance}
    """

    cli_command = [
        "show running-config network-instance {network_instance} protocol ISIS {protocol_instance}",
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
            cmd = f"show running-config network-instance {network_instance} protocol ISIS {protocol_instance}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]
            cfg_root = ni_isis.setdefault("config", {})

            # Global configuration
            global_config = isis.get("global", {})
            config = global_config.get("config", {})
            if config:
                global_entry: Dict[str, TypeAny] = {}
                if "net" in config:
                    global_entry["net"] = config["net"]
                if "level-capability" in config:
                    global_entry["level-capability"] = config["level-capability"]
                if "max-ecmp-paths" in config:
                    global_entry["max-ecmp-paths"] = config["max-ecmp-paths"]

                if global_entry:
                    cfg_root["global"] = global_entry

            # Auto-cost reference-bandwidth
            ref_bw_root = global_config.get("reference-bandwidth", {})
            ref_bw_cfg = ref_bw_root.get("config", {})
            if "reference-bandwidth" in ref_bw_cfg:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"][
                    "auto-cost-reference-bandwidth"
                ] = ref_bw_cfg["reference-bandwidth"]

            # Global MPLS IGP-LDP sync
            mpls_root = global_config.get("mpls", {})
            igp_ldp_cfg = mpls_root.get("igp-ldp-sync", {}).get("config", {})
            if "enabled" in igp_ldp_cfg:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["mpls-igp-ldp-sync-enabled"] = igp_ldp_cfg[
                    "enabled"
                ]

            # Global hello-authentication (augmented)
            hello_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:hello-authentication", {}
            )
            hello_cfg = hello_root.get("config", {})
            if hello_cfg:
                hello_entry: Dict[str, TypeAny] = {}
                if "hello-authentication" in hello_cfg:
                    hello_entry["enabled"] = hello_cfg["hello-authentication"]
                if "keychain" in hello_cfg:
                    hello_entry["keychain"] = hello_cfg["keychain"]
                if "auth-type" in hello_cfg:
                    hello_entry["auth-type"] = hello_cfg["auth-type"]

                if hello_entry:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["hello-authentication"] = hello_entry

            # Graceful restart
            gr_root = global_config.get("graceful-restart", {}) or {}
            gr_cfg = gr_root.get("config", {}) or {}
            gr_state = gr_root.get("state", {}) or {}

            gr_val = None
            if "enabled" in gr_cfg:
                gr_val = gr_cfg["enabled"]
            elif "enabled" in gr_state:
                gr_val = gr_state["enabled"]

            if gr_val is not None:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["graceful-restart-enabled"] = gr_val

            # Transport (LSP MTU)
            transport_config = global_config.get("transport", {}).get("config", {})
            if transport_config and "lsp-mtu-size" in transport_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["lsp-mtu-size"] = transport_config["lsp-mtu-size"]

            # Segment Routing
            sr_root = global_config.get("segment-routing", {})
            sr_config = sr_root.get("config", {})
            if sr_config and "enabled" in sr_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["segment-routing-enabled"] = sr_config["enabled"]

            # SRMS (Segment Routing Mapping Server)
            srms_root = sr_root.get(f"{ARCOS_ISIS_AUGMENTS}:srms", {})
            srms_config = srms_root.get("config", {})
            if srms_config:
                srms_dict: Dict[str, TypeAny] = {}
                if "mapping" in srms_config:
                    srms_dict["mapping"] = srms_config["mapping"]
                if "receive-enabled" in srms_config:
                    srms_dict["receive-enabled"] = srms_config["receive-enabled"]
                if "advertise-enabled" in srms_config:
                    srms_dict["advertise-enabled"] = srms_config["advertise-enabled"]
                if srms_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["srms"] = srms_dict

            # SRv6
            srv6_root = global_config.get(f"{ARCOS_ISIS_AUGMENTS}:srv6", {})
            srv6_config = srv6_root.get("config", {})
            if srv6_config and "enabled" in srv6_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                srv6_dict = {"enabled": srv6_config["enabled"]}

                # SRv6 locators
                locators_root = srv6_root.get("locators", {}).get("config", {})
                locator_list = locators_root.get("locator", [])
                if locator_list:
                    srv6_dict["locators"] = [
                        loc.get("name") for loc in locator_list if loc.get("name")
                    ]

                cfg_root["global"]["srv6"] = srv6_dict

            # Traffic Engineering
            te_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:traffic-engineering", {}
            )
            te_config = te_root.get("config", {})
            if te_config:
                te_dict = {}
                if "ipv4-router-id" in te_config:
                    te_dict["ipv4-router-id"] = te_config["ipv4-router-id"]
                if "ipv6-router-id" in te_config:
                    te_dict["ipv6-router-id"] = te_config["ipv6-router-id"]
                if te_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["traffic-engineering"] = te_dict

            # Micro Loop Avoidance
            mla_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:micro-loop-avoidance", {}
            )
            mla_config = mla_root.get("config", {})
            if mla_config:
                mla_dict = {}
                if "srv6-enabled" in mla_config:
                    mla_dict["srv6-enabled"] = mla_config["srv6-enabled"]
                if "rib-update-delay" in mla_config:
                    mla_dict["rib-update-delay"] = mla_config["rib-update-delay"]
                if mla_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["micro-loop-avoidance"] = mla_dict

            # Flexible Algorithms
            flexalgo_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithms", {}
            )
            flexalgo_list = flexalgo_root.get("flexible-algorithm", [])
            if flexalgo_list:
                flexalgo_dict = {}
                for algo in flexalgo_list:
                    algo_id = algo.get("id")
                    if algo_id is not None:
                        algo_config = algo.get("config", {})
                        algo_entry = {"id": algo_id}

                        adv_def = algo_config.get("advertise-definition", {})
                        if "enabled" in adv_def:
                            algo_entry["advertise-definition-enabled"] = adv_def[
                                "enabled"
                            ]

                        if "metric-type" in algo_config:
                            algo_entry["metric-type"] = algo_config["metric-type"]

                        flexalgo_dict[str(algo_id)] = algo_entry

                if flexalgo_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["flexible-algorithms"] = flexalgo_dict

            # Dynamic Delay Measurement
            ddm_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:dynamic-delay-measurement", {}
            )
            ddm_config = ddm_root.get("config", {})
            if ddm_config:
                ddm_dict = {}
                if "probe-interval" in ddm_config:
                    ddm_dict["probe-interval"] = ddm_config["probe-interval"]
                if "advertisement-interval" in ddm_config:
                    ddm_dict["advertisement-interval"] = ddm_config[
                        "advertisement-interval"
                    ]
                if ddm_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["dynamic-delay-measurement"] = ddm_dict

            # LSP-bit settings (overload/attached bits + reset triggers)
            lsp_root = global_config.get("lsp-bit", {})
            if lsp_root:
                lsp_dict: Dict[str, TypeAny] = {}

                # Overload bit
                ov_root = lsp_root.get("overload-bit", {})
                ov_cfg = ov_root.get("config", {})
                ov_entry: Dict[str, TypeAny] = {}
                if "set-bit-on-boot" in ov_cfg:
                    ov_entry["set-bit-on-boot"] = ov_cfg["set-bit-on-boot"]
                # Permanent overload-bit set-bit (config or state)
                if "set-bit" in ov_cfg:
                    ov_entry["set-bit"] = ov_cfg["set-bit"]
                ov_state = ov_root.get("state", {})
                if "set-bit" in ov_state and "set-bit" not in ov_entry:
                    ov_entry["set-bit"] = ov_state["set-bit"]
                if "advertise-high-metric" in ov_cfg:
                    ov_entry["advertise-high-metric"] = ov_cfg["advertise-high-metric"]

                rt_root = ov_root.get("reset-triggers", {})
                rt_list = rt_root.get("reset-trigger", [])
                if rt_list:
                    resets: list = []
                    for rt in rt_list:
                        rt_entry: Dict[str, TypeAny] = {}
                        # Prefer the configured trigger name, fall back to top-level
                        rt_cfg = rt.get("config", {})
                        trigger = rt_cfg.get("reset-trigger") or rt.get("reset-trigger")
                        if trigger is not None:
                            rt_entry["reset-trigger"] = trigger
                        if "delay" in rt_cfg:
                            rt_entry["delay"] = rt_cfg["delay"]
                        if rt_entry:
                            resets.append(rt_entry)
                    if resets:
                        ov_entry["reset-triggers"] = resets

                if ov_entry:
                    lsp_dict["overload-bit"] = ov_entry

                # Attached bit
                att_root = lsp_root.get("attached-bit", {})
                att_cfg = att_root.get("config", {})
                att_entry: Dict[str, TypeAny] = {}
                if "ignore-bit" in att_cfg:
                    att_entry["ignore-bit"] = att_cfg["ignore-bit"]
                if "suppress-bit" in att_cfg:
                    att_entry["suppress-bit"] = att_cfg["suppress-bit"]

                if att_entry:
                    lsp_dict["attached-bit"] = att_entry

                if lsp_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["lsp-bit"] = lsp_dict

            # Inter-level propagation policies
            inter_root = global_config.get("inter-level-propagation-policies", {})
            if inter_root:
                inter_policies: Dict[str, TypeAny] = {}

                l1_root = inter_root.get("level1-to-level2", {})
                l1_cfg = l1_root.get("config", {})
                if "import-policy" in l1_cfg:
                    inter_policies["level1-to-level2"] = {
                        "import-policy": l1_cfg["import-policy"]
                    }

                l2_root = inter_root.get("level2-to-level1", {})
                l2_cfg = l2_root.get("config", {})
                if "import-policy" in l2_cfg:
                    inter_policies["level2-to-level1"] = {
                        "import-policy": l2_cfg["import-policy"]
                    }

                if inter_policies:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["inter-level-policies"] = inter_policies

            # Global ISIS levels
            levels_root = isis.get("levels", {})
            level_list = levels_root.get("level", [])
            if level_list:
                levels_dict: Dict[str, TypeAny] = {}
                for level in level_list:
                    level_num = level.get("level-number")
                    if level_num is None:
                        continue

                    level_config = level.get("config", {})
                    lvl_entry: Dict[str, TypeAny] = {"level-number": level_num}
                    if "enabled" in level_config:
                        lvl_entry["enabled"] = level_config["enabled"]

                    # Per-level authentication
                    auth_root = level.get("authentication", {})
                    auth_cfg = auth_root.get("config", {})
                    auth_entry: Dict[str, TypeAny] = {}
                    if "lsp-authentication" in auth_cfg:
                        auth_entry["lsp-authentication"] = auth_cfg["lsp-authentication"]
                    if "csnp-authentication" in auth_cfg:
                        auth_entry["csnp-authentication"] = auth_cfg[
                            "csnp-authentication"
                        ]
                    if "psnp-authentication" in auth_cfg:
                        auth_entry["psnp-authentication"] = auth_cfg[
                            "psnp-authentication"
                        ]
                    if "auth-type" in auth_cfg:
                        auth_entry["auth-type"] = auth_cfg["auth-type"]
                    if "keychain" in auth_cfg:
                        auth_entry["keychain"] = auth_cfg["keychain"]

                    key_cfg = auth_root.get("key", {}).get("config", {})
                    if "auth-password" in key_cfg:
                        auth_entry["auth-password"] = key_cfg["auth-password"]
                    crypto_key = key_cfg.get(f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm")
                    if crypto_key is not None:
                        auth_entry["crypto-algorithm"] = crypto_key

                    if auth_entry:
                        lvl_entry["authentication"] = auth_entry

                    # Labeled preference (for SR/LDP coexistence)
                    labeled_pref_root = level.get(
                        f"{ARCOS_ISIS_AUGMENTS}:labeled-preference", {}
                    )
                    labeled_pref_cfg = labeled_pref_root.get("config", {})
                    if "labeled-preference" in labeled_pref_cfg:
                        lvl_entry["labeled-preference"] = labeled_pref_cfg[
                            "labeled-preference"
                        ]

                    # Per-level traffic engineering enabled
                    # Some releases use plain "traffic-engineering" under levels,
                    # others may use the augmented namespace.
                    lvl_te_root = level.get("traffic-engineering", {})
                    if not lvl_te_root:
                        lvl_te_root = level.get(
                            f"{ARCOS_ISIS_AUGMENTS}:traffic-engineering", {}
                        )
                    lvl_te_cfg = lvl_te_root.get("config", {})
                    if "enabled" in lvl_te_cfg:
                        lvl_entry["traffic-engineering-enabled"] = lvl_te_cfg[
                            "enabled"
                        ]

                    levels_dict[str(level_num)] = lvl_entry

                if levels_dict:
                    cfg_root["levels"] = levels_dict

            # AFI-SAFI configuration
            afi_safi_config = global_config.get("afi-safi", {})
            af_list = afi_safi_config.get("af", [])
            if af_list:
                afi_safi_dict: Dict[str, TypeAny] = {}
                for af in af_list:
                    afi_name = af.get("afi-name", "")
                    afi_name = afi_name.replace("openconfig-isis-types:", "").replace(
                        "oc-isis-types:", ""
                    )

                    safi_name = af.get("safi-name", "")
                    safi_name = safi_name.replace("openconfig-isis-types:", "").replace(
                        "oc-isis-types:", ""
                    )

                    af_key = f"{afi_name}-{safi_name}"
                    af_config = af.get("config", {})
                    af_entry: Dict[str, TypeAny] = {
                        "afi-name": afi_name,
                        "safi-name": safi_name,
                        "enabled": af_config.get("enabled", False),
                    }

                    mt = af.get(f"{ARCOS_ISIS_AUGMENTS}:multi-topology", {})
                    mt_config = mt.get("config", {})
                    if "enabled" in mt_config:
                        af_entry["multi-topology-enabled"] = mt_config["enabled"]

                    # Summary prefixes
                    summary_root = af.get(f"{ARCOS_ISIS_AUGMENTS}:summary-prefixes", {})
                    summary_list = summary_root.get("summary-prefix", [])
                    if summary_list:
                        summary_dict = {}
                        for summary in summary_list:
                            prefix = summary.get("prefix")
                            if prefix:
                                sum_config = summary.get("config", {})
                                sum_entry = {"prefix": prefix}
                                if "level" in sum_config:
                                    sum_entry["level"] = sum_config["level"]
                                if "algorithm" in sum_config:
                                    sum_entry["algorithm"] = sum_config["algorithm"]
                                if "tag" in sum_config:
                                    sum_entry["tag"] = sum_config["tag"]
                                if "adv-unreachable" in sum_config:
                                    sum_entry["adv-unreachable"] = sum_config[
                                        "adv-unreachable"
                                    ]
                                summary_dict[prefix] = sum_entry
                        if summary_dict:
                            af_entry["summary-prefixes"] = summary_dict

                    # Prefix unreachable
                    prefix_unreach_root = af.get(
                        f"{ARCOS_ISIS_AUGMENTS}:prefix-unreachable", {}
                    )
                    prefix_unreach_config = prefix_unreach_root.get("config", {})
                    if prefix_unreach_config:
                        unreach_dict = {}
                        if "adv-lifetime" in prefix_unreach_config:
                            unreach_dict["adv-lifetime"] = prefix_unreach_config[
                                "adv-lifetime"
                            ]
                        if "adv-metric" in prefix_unreach_config:
                            unreach_dict["adv-metric"] = prefix_unreach_config[
                                "adv-metric"
                            ]
                        if "adv-maximum" in prefix_unreach_config:
                            unreach_dict["adv-maximum"] = prefix_unreach_config[
                                "adv-maximum"
                            ]
                        if "rx-process" in prefix_unreach_config:
                            unreach_dict["rx-process"] = prefix_unreach_config[
                                "rx-process"
                            ]
                        if unreach_dict:
                            af_entry["prefix-unreachable"] = unreach_dict

                    # Default-information originate per AF
                    default_info_root = af.get(
                        f"{ARCOS_ISIS_AUGMENTS}:default-information", {}
                    )
                    originate_root = default_info_root.get("originate", {})
                    originate_cfg = originate_root.get("config", {})
                    if originate_cfg:
                        default_info: Dict[str, TypeAny] = {}
                        if "enabled" in originate_cfg:
                            default_info["enabled"] = originate_cfg["enabled"]
                        if "export-policy" in originate_cfg:
                            default_info["export-policy"] = originate_cfg[
                                "export-policy"
                            ]
                        if default_info:
                            af_entry["default-information"] = default_info

                    afi_safi_dict[af_key] = af_entry

                if afi_safi_dict:
                    cfg_root["afi-safi"] = afi_safi_dict

            # Interface configurations
            interfaces_config = isis.get("interfaces", {})
            interface_list = interfaces_config.get("interface", [])
            if interface_list:
                interfaces_dict: Dict[str, TypeAny] = {}
                for intf in interface_list:
                    intf_id = intf.get("interface-id")
                    if not intf_id:
                        continue

                    intf_config = intf.get("config", {})
                    intf_entry: Dict[str, TypeAny] = {
                        "interface-id": intf_id,
                        "enabled": intf_config.get("enabled", False),
                    }

                    network_type = intf_config.get(
                        f"{ARCOS_ISIS_AUGMENTS}:network-type"
                    )
                    if network_type:
                        intf_entry["network-type"] = network_type

                    # Interface tag list
                    tag_list = intf_config.get(f"{ARCOS_ISIS_AUGMENTS}:tag")
                    if tag_list:
                        intf_entry["tag"] = tag_list

                    # Authentication
                    auth_root = intf.get("authentication", {})
                    auth_config = auth_root.get("config", {})
                    if auth_config:
                        auth_dict = {}
                        if "hello-authentication" in auth_config:
                            auth_dict["hello-authentication"] = auth_config[
                                "hello-authentication"
                            ]

                        if "keychain" in auth_config:
                            auth_dict["keychain"] = auth_config["keychain"]
                        if "auth-type" in auth_config:
                            auth_dict["auth-type"] = auth_config["auth-type"]

                        auth_key = auth_root.get("key", {}).get("config", {})
                        if "auth-password" in auth_key:
                            auth_dict["auth-password"] = auth_key["auth-password"]
                        if f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm" in auth_key:
                            auth_dict["crypto-algorithm"] = auth_key[
                                f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm"
                            ]

                        if auth_dict:
                            intf_entry["authentication"] = auth_dict

                    # Timers
                    timers_root = intf.get("timers", {}).get("config", {})
                    if timers_root:
                        timers_dict = {}
                        if f"{ARCOS_ISIS_AUGMENTS}:hello-interval" in timers_root:
                            timers_dict["hello-interval"] = timers_root[
                                f"{ARCOS_ISIS_AUGMENTS}:hello-interval"
                            ]
                        if f"{ARCOS_ISIS_AUGMENTS}:hello-multiplier" in timers_root:
                            timers_dict["hello-multiplier"] = timers_root[
                                f"{ARCOS_ISIS_AUGMENTS}:hello-multiplier"
                            ]
                        if timers_dict:
                            intf_entry["timers"] = timers_dict

                    # MPLS IGP-LDP sync (interface level)
                    intf_mpls_root = intf.get(f"{ARCOS_ISIS_AUGMENTS}:mpls", {})
                    igp_ldp_cfg = intf_mpls_root.get("igp-ldp-sync", {}).get(
                        "config", {}
                    )
                    if "enabled" in igp_ldp_cfg:
                        intf_entry["mpls-igp-ldp-sync-enabled"] = igp_ldp_cfg[
                            "enabled"
                        ]

                    intf_afi_safi = intf.get("afi-safi", {})
                    intf_af_list = intf_afi_safi.get("af", [])
                    if intf_af_list:
                        intf_entry["afi-safi"] = {}
                        for af in intf_af_list:
                            afi_name = af.get("afi-name", "")
                            afi_name = afi_name.replace(
                                "openconfig-isis-types:", ""
                            ).replace("oc-isis-types:", "")

                            safi_name = af.get("safi-name", "")
                            safi_name = safi_name.replace(
                                "openconfig-isis-types:", ""
                            ).replace("oc-isis-types:", "")

                            af_key = f"{afi_name}-{safi_name}"
                            af_config = af.get("config", {})
                            intf_af_entry = {
                                "afi-name": afi_name,
                                "safi-name": safi_name,
                                "enabled": af_config.get("enabled", False),
                            }

                            # Fast Reroute (TI-LFA SRv6 and SR-MPLS)
                            frr_root = af_config.get(
                                f"{ARCOS_ISIS_AUGMENTS}:fast-reroute", {}
                            )
                            tilfa_root = frr_root.get("ti-lfa", {}).get("config", {})
                            frr_entry: Dict[str, TypeAny] = {}
                            ip_root = frr_root.get("ip", {}).get("config", {})
                            if "enabled" in ip_root:
                                frr_entry["ip-enabled"] = ip_root["enabled"]
                            srv6_root = tilfa_root.get("srv6", {})
                            if "enabled" in srv6_root:
                                frr_entry["ti-lfa-srv6-enabled"] = srv6_root["enabled"]
                            sr_mpls_root = tilfa_root.get("sr-mpls", {})
                            if "enabled" in sr_mpls_root:
                                frr_entry["ti-lfa-sr-mpls-enabled"] = sr_mpls_root[
                                    "enabled"
                                ]
                            if frr_entry:
                                intf_af_entry["fast-reroute"] = frr_entry

                            # Adjacency SIDs
                            adj_sids_root = af_config.get(
                                f"{ARCOS_ISIS_AUGMENTS}:adjacency-sids", {}
                            )
                            adj_sid_list = adj_sids_root.get("adjacency-sid", [])
                            if adj_sid_list:
                                adjacency_sids = []
                                for adj_sid in adj_sid_list:
                                    adj_config = adj_sid.get("config", {})
                                    neighbor = adj_sid.get("neighbor", "")
                                    # Strip namespace prefix
                                    if ":" in neighbor:
                                        neighbor = neighbor.split(":")[-1]
                                    adj_entry = {
                                        "neighbor": neighbor,
                                        "sid-type": adj_config.get("sid-type"),
                                        "value": adj_config.get("value"),
                                    }
                                    adjacency_sids.append(adj_entry)
                                if adjacency_sids:
                                    intf_af_entry["adjacency-sids"] = adjacency_sids

                            # Prefix SIDs
                            prefix_sids_root = af_config.get(
                                f"{ARCOS_ISIS_AUGMENTS}:prefix-sids", {}
                            )
                            prefix_sid_list = prefix_sids_root.get("prefix-sid", [])
                            if prefix_sid_list:
                                prefix_sids = []
                                for prefix_sid in prefix_sid_list:
                                    pfx_config = prefix_sid.get("config", {})
                                    algorithm = prefix_sid.get("algorithm", "")
                                    # Strip namespace prefix
                                    if ":" in algorithm:
                                        algorithm = algorithm.split(":")[-1]
                                    pfx_entry: Dict[str, TypeAny] = {
                                        "algorithm": algorithm,
                                        "sid-type": pfx_config.get("sid-type"),
                                        "value": pfx_config.get("value"),
                                    }
                                    label_option = pfx_config.get("label-option")
                                    if label_option:
                                        pfx_entry["label-option"] = label_option
                                    prefix_sids.append(pfx_entry)
                                if prefix_sids:
                                    intf_af_entry["prefix-sids"] = prefix_sids

                            intf_entry["afi-safi"][af_key] = intf_af_entry

                    intf_levels = intf.get("levels", {})
                    level_list = intf_levels.get("level", [])
                    if level_list:
                        intf_entry["levels"] = {}
                        for level in level_list:
                            level_num = level.get("level-number")
                            if level_num is not None:
                                level_config = level.get("config", {})
                                level_entry = {
                                    "level-number": level_num,
                                }
                                if "enabled" in level_config:
                                    level_entry["enabled"] = level_config["enabled"]
                                if f"{ARCOS_ISIS_AUGMENTS}:metric" in level_config:
                                    level_entry["metric"] = level_config[
                                        f"{ARCOS_ISIS_AUGMENTS}:metric"
                                    ]

                                # Flexible algorithm metrics (delay + TE metric)
                                flexalgo_root = level_config.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithm", {}
                                )
                                if flexalgo_root:
                                    flex_entry: Dict[str, TypeAny] = {}
                                    if "delay-metric" in flexalgo_root:
                                        flex_entry["delay-metric"] = flexalgo_root[
                                            "delay-metric"
                                        ]
                                    if "te-metric" in flexalgo_root:
                                        flex_entry["te-metric"] = flexalgo_root[
                                            "te-metric"
                                        ]
                                    if flex_entry:
                                        level_entry["flexible-algorithm"] = flex_entry

                                intf_entry["levels"][str(level_num)] = level_entry

                    # Interface-ref mapping back to the physical interface
                    iface_ref_root = intf.get("interface-ref", {}).get("config", {})
                    if iface_ref_root:
                        iface_ref: Dict[str, TypeAny] = {}
                        if "interface" in iface_ref_root:
                            iface_ref["interface"] = iface_ref_root["interface"]
                        if "subinterface" in iface_ref_root:
                            iface_ref["subinterface"] = iface_ref_root["subinterface"]
                        if iface_ref:
                            intf_entry["interface-ref"] = iface_ref

                    interfaces_dict[intf_id] = intf_entry

                if interfaces_dict:
                    cfg_root["interfaces"] = interfaces_dict

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS config data: %s", exc)

        return ret_dict


class ShowIsisRouteSchema(MetaParser):
    """Schema for ArcOS ISIS routes per AF and prefix.

    NOTE: Structured like :class:`ShowIsisInterfaceSchema`, with routes
    nested under ``isis[instance]['routes']`` instead of a top-level
    ``isis_routes`` key.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("routes"): {
                            Any(): {  # AFI-SAFI key like "IPV4-UNICAST" or "IPV6-UNICAST"
                                "afi-name": str,
                                "safi-name": str,
                                "routes": {
                                    Any(): {  # prefix
                                        "prefix": str,
                                        "best-level-number": int,
                                        Optional("levels"): dict,
                                    }
                                },
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisRoute(ShowIsisRouteSchema):
    """Parser for ArcOS ISIS routes command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route [<prefix>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route",
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route {prefix}",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        afi: str = "*",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(afi, "afi")
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Align with other ISIS parsers: nest under isis["default"]["routes"].
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]
            routes_dict: Dict[str, TypeAny] = ni_isis.setdefault("routes", {})

            for af in af_list:
                afi_name = af.get("afi-name", "")
                afi_name = afi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                safi_name = af.get("safi-name", "")
                safi_name = safi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                af_key = f"{afi_name}-{safi_name}"

                routes_obj = af.get(f"{ARCOS_ISIS_AUGMENTS}:routes", {})
                route_list = routes_obj.get("route", [])

                if not route_list:
                    continue

                af_entry: Dict[str, TypeAny] = {
                    "afi-name": afi_name,
                    "safi-name": safi_name,
                    "routes": {},
                }

                for route in route_list:
                    prefix_val = route.get("prefix")
                    if not prefix_val:
                        continue

                    state = route.get("state", {})
                    route_entry: Dict[str, TypeAny] = {
                        "prefix": prefix_val,
                        "best-level-number": state.get("best-level-number", 0),
                    }

                    levels_obj = route.get("levels", {})
                    level_list = levels_obj.get("level", [])

                    if level_list:
                        route_entry["levels"] = {}
                        for level in level_list:
                            level_num = level.get("level-number")
                            if level_num is None:
                                continue

                            level_state = level.get("state", {})
                            level_entry: Dict[str, TypeAny] = {
                                "level-number": level_num,
                                "metric": level_state.get("metric", 0),
                            }

                            flags = level_state.get("flags", [])
                            if flags:
                                level_entry["flags"] = [
                                    f.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                    for f in flags
                                ]

                            if "next-hop-id" in level_state:
                                level_entry["next-hop-id"] = str(
                                    level_state["next-hop-id"]
                                )
                            if "prefix-origin-count" in level_state:
                                level_entry["prefix-origin-count"] = level_state[
                                    "prefix-origin-count"
                                ]
                            if "route-tag" in level_state:
                                level_entry["route-tag"] = level_state["route-tag"]
                            if "last-updated-time" in level_state:
                                level_entry["last-updated-time"] = level_state[
                                    "last-updated-time"
                                ]

                            next_hops_obj = level.get("next-hops", {})
                            next_hop_list = next_hops_obj.get("next-hop", [])

                            if next_hop_list:
                                level_entry["next-hops"] = []
                                for nh in next_hop_list:
                                    nh_entry: Dict[str, TypeAny] = {}

                                    if "next-hop-address" in nh:
                                        nh_entry["next-hop-address"] = nh[
                                            "next-hop-address"
                                        ]

                                    if "outgoing-interface" in nh:
                                        nh_entry["outgoing-interface"] = nh[
                                            "outgoing-interface"
                                        ]

                                    nh_state = nh.get("state", {})
                                    if nh_state:
                                        if "tunnel-id" in nh_state:
                                            nh_entry["tunnel-id"] = nh_state[
                                                "tunnel-id"
                                            ]
                                        if "backup" in nh_state:
                                            nh_entry["backup"] = nh_state["backup"]

                                    level_entry["next-hops"].append(nh_entry)

                            route_entry["levels"][str(level_num)] = level_entry

                    af_entry["routes"][prefix_val] = route_entry

                if af_entry["routes"]:
                    routes_dict[af_key] = af_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS routes data: %s", exc)

        return ret_dict


class ShowIsisRedistributeRouteSchema(MetaParser):
    """Schema for ArcOS ISIS redistributed routes per AF and prefix.

    Structured like :class:`ShowIsisInterfaceSchema` and
    :class:`ShowIsisRouteSchema`, with data nested under
    ``isis[instance]['redistribute-routes']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("redistribute-routes"): {
                            Any(): {  # AF key (e.g., "IPV4-UNICAST")
                                "afi-name": str,
                                "safi-name": str,
                                "routes": {
                                    Any(): {  # prefix
                                        "prefix": str,
                                        "levels": dict,
                                    }
                                },
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisRedistributeRoute(ShowIsisRedistributeRouteSchema):
    """Parser for ArcOS ISIS redistribute routes command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST redistribute-route [<prefix>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST redistribute-route",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        afi: str = "*",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(afi, "afi")
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST redistribute-route"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Align with other ISIS parsers: nest under isis["default"]["redistribute-routes"].
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]
            redist_dict: Dict[str, TypeAny] = ni_isis.setdefault(
                "redistribute-routes", {}
            )

            for af in af_list:
                afi_name = af.get("afi-name", "")
                afi_name = afi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                safi_name = af.get("safi-name", "")
                safi_name = safi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                af_key = f"{afi_name}-{safi_name}"

                redist_obj = af.get(f"{ARCOS_ISIS_AUGMENTS}:redistribute-routes", {})
                redist_list = redist_obj.get("redistribute-route", [])

                if not redist_list:
                    continue

                af_entry: Dict[str, TypeAny] = {
                    "afi-name": afi_name,
                    "safi-name": safi_name,
                    "routes": {},
                }

                for route in redist_list:
                    prefix_val = route.get("prefix")
                    if not prefix_val:
                        continue

                    route_entry: Dict[str, TypeAny] = {
                        "prefix": prefix_val,
                        "levels": {},
                    }

                    levels_obj = route.get("levels", {})
                    level_list = levels_obj.get("level", [])

                    for level in level_list:
                        level_num = level.get("level-number")
                        if level_num is None:
                            continue

                        state = level.get("state", {})

                        level_entry: Dict[str, TypeAny] = {
                            "level-number": level_num,
                            "metric": state.get("metric", 0),
                        }

                        if "route-tag" in state:
                            level_entry["route-tag"] = state["route-tag"]

                        if "flags" in state:
                            flags = state["flags"]
                            cleaned_flags = [
                                f.replace(f"{ARCOS_ISIS_AUGMENTS}:", "") for f in flags
                            ]
                            level_entry["flags"] = cleaned_flags

                        source = level.get("source", {})
                        source_state = source.get("state", {})
                        if "identifier" in source_state:
                            identifier = source_state["identifier"]
                            level_entry["source-identifier"] = identifier.replace(
                                "openconfig-policy-types:", ""
                            )
                        if "name" in source_state:
                            level_entry["source-name"] = source_state["name"]

                        route_entry["levels"][str(level_num)] = level_entry

                    af_entry["routes"][prefix_val] = route_entry

                redist_dict[af_key] = af_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS redistribute routes data: %s", exc)

        return ret_dict


class ShowIsisGlobalSchema(MetaParser):
    """Schema for ArcOS ISIS global state JSON output."""

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("global"): {
                            Optional("net"): list,
                            Optional("level-capability"): str,
                            Optional("max-ecmp-paths"): int,
                            Optional("is-type"): str,
                            Optional("table-id"): int,
                            Optional("area-address"): list,
                            Optional("system-id"): str,
                        }
                    }
                }
            }
        }
    }


class ShowIsisGlobal(ShowIsisGlobalSchema):
    """Parser for ArcOS ISIS global state command (JSON format).

    Supports::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global state | display json | nomore
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global state",
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
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global state"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing output: %s", output)
        # Initialize return dictionary
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            # Parse JSON output robustly
            parsed_json = load_json_robust(output)

            # Navigate to ISIS data
            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            state = global_config.get("state", {})

            if state:
                global_entry: Dict[str, TypeAny] = {}

                # Standard fields
                if "net" in state:
                    global_entry["net"] = state["net"]

                level_cap = state.get("level-capability")
                if level_cap is not None:
                    # Clean up known prefixes
                    level_cap = level_cap.replace("openconfig-isis-types:", "")
                    level_cap = level_cap.replace("oc-isis-types:", "")
                    global_entry["level-capability"] = level_cap

                if "max-ecmp-paths" in state:
                    global_entry["max-ecmp-paths"] = state["max-ecmp-paths"]

                # ArcOS augments
                is_type_key = f"{ARCOS_ISIS_AUGMENTS}:is-type"
                if is_type_key in state:
                    is_type = state[is_type_key]
                    is_type = is_type.replace("arcos-isis-types:", "")
                    is_type = is_type.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                    global_entry["is-type"] = is_type

                table_id_key = f"{ARCOS_ISIS_AUGMENTS}:table-id"
                if table_id_key in state:
                    global_entry["table-id"] = state[table_id_key]

                area_addr_key = f"{ARCOS_ISIS_AUGMENTS}:area-address"
                if area_addr_key in state:
                    global_entry["area-address"] = state[area_addr_key]

                system_id_key = f"{ARCOS_ISIS_AUGMENTS}:system-id"
                if system_id_key in state:
                    global_entry["system-id"] = state[system_id_key]

                # For now, always use DEFAULT_INSTANCE key
                ret_dict["network-instance"]["default"]["isis"]["default"]["global"] = (
                    global_entry
                )

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS global data: %s", exc)

        return ret_dict


class ShowIsisFastRerouteSchema(MetaParser):
    """Schema for ArcOS ISIS fast-reroute information per AF and prefix.

    Structured like :class:`ShowIsisInterfaceSchema`, with data nested
    under ``isis[instance]['fast-reroute']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("fast-reroute"): {
                            Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                "afi-name": str,
                                "safi-name": str,
                                "prefixes": {
                                    Any(): {  # prefix string
                                        "prefix": str,
                                        "levels": {
                                            Any(): {  # level number as string
                                                "level-number": int,
                                                "reroute-type": str,
                                                "metric": int,
                                                "nexthop-address": str,
                                                "nexthop-interface": str,
                                                "flags": list,
                                                "last-updated-time": str,
                                                "origin-system-id": str,
                                                Optional("protection-types"): list,
                                                # arcOS emits one of two node-field shapes
                                                # depending on the flag value:
                                                #   PQ_IS_ADJACENT / PQ_IS_REMOTE  → pq-node only
                                                #   P_AND_Q_ARE_ADJACENT            → p-node + q-node
                                                # All three fields are Optional; the parser
                                                # extracts whichever the device populates. On
                                                # docker, an unresolved Q renders as
                                                # "0000.0000.0000.00" — parser passes it through.
                                                Optional("pq-node-system-id"): str,
                                                Optional("p-node-system-id"): str,
                                                Optional("q-node-system-id"): str,
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisFastReroute(ShowIsisFastRerouteSchema):
    """Parser for ArcOS ISIS fast-reroute command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST fast-reroute [<prefix>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST fast-reroute",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        afi: str = "*",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(afi, "afi")
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST fast-reroute"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["fast-reroute"].
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]
            fast_dict: Dict[str, TypeAny] = ni_isis.setdefault("fast-reroute", {})

            for af in af_list:
                afi_name = af.get("afi-name", "")
                afi_name = afi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                safi_name = af.get("safi-name", "")
                safi_name = safi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                af_key = f"{afi_name}-{safi_name}"

                frr_container = af.get(f"{ARCOS_ISIS_AUGMENTS}:fast-reroutes", {})
                frr_list = frr_container.get("fast-reroute", [])

                if not frr_list:
                    continue

                af_entry: Dict[str, TypeAny] = {
                    "afi-name": afi_name,
                    "safi-name": safi_name,
                    "prefixes": {},
                }

                for frr in frr_list:
                    prefix_str = frr.get("prefix")
                    if not prefix_str:
                        continue

                    prefix_entry: Dict[str, TypeAny] = {
                        "prefix": prefix_str,
                        "levels": {},
                    }

                    levels_obj = frr.get("levels", {})
                    level_list = levels_obj.get("level", [])

                    for level in level_list:
                        level_num = level.get("level-number")
                        if level_num is None:
                            continue

                        state = level.get("state", {})
                        level_entry: Dict[str, TypeAny] = {
                            "level-number": level_num,
                            "reroute-type": state.get("reroute-type", ""),
                            "metric": state.get("metric", 0),
                            "nexthop-address": state.get("nexthop-address", ""),
                            "nexthop-interface": state.get("nexthop-interface", ""),
                            "flags": state.get("flags", []),
                            "last-updated-time": state.get("last-updated-time", ""),
                            "origin-system-id": state.get("origin-system-id", ""),
                        }

                        prot_types = state.get("protection-types", [])
                        if prot_types:
                            level_entry["protection-types"] = [
                                p.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                for p in prot_types
                            ]

                        # JSON shape depends on the level's flag:
                        #   PQ_IS_ADJACENT / PQ_IS_REMOTE → pq-node.state.system-id
                        #   P_AND_Q_ARE_ADJACENT          → p-node + q-node (separate)
                        # All three keys are Optional; we extract whichever are present.
                        pq_node = level.get("pq-node", {}).get("state", {})
                        if "system-id" in pq_node:
                            level_entry["pq-node-system-id"] = pq_node["system-id"]

                        p_node = level.get("p-node", {}).get("state", {})
                        if "system-id" in p_node:
                            level_entry["p-node-system-id"] = p_node["system-id"]

                        q_node = level.get("q-node", {}).get("state", {})
                        if "system-id" in q_node:
                            level_entry["q-node-system-id"] = q_node["system-id"]

                        prefix_entry["levels"][str(level_num)] = level_entry

                    af_entry["prefixes"][prefix_str] = prefix_entry

                if af_entry["prefixes"]:
                    fast_dict[af_key] = af_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS fast-reroute data: %s", exc)

        return ret_dict


class ShowIsisFlexAlgoFastRerouteSchema(MetaParser):
    """Schema for ArcOS ISIS flexible-algorithm fast-reroute per AF, algorithm, and prefix.

    Nested under ``isis[instance]['flex-algo-fast-reroute']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("flex-algo-fast-reroute"): {
                            Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                "afi-name": str,
                                "safi-name": str,
                                "algorithms": {
                                    Any(): {  # flexible-algorithm id as string
                                        "id": int,
                                        "prefixes": {
                                            Any(): {  # prefix string
                                                "prefix": str,
                                                "levels": {
                                                    Any(): {  # level number as string
                                                        "level-number": int,
                                                        "reroute-type": str,
                                                        "metric": int,
                                                        "nexthop-address": str,
                                                        "nexthop-interface": str,
                                                        "flags": list,
                                                        "last-updated-time": str,
                                                        "origin-system-id": str,
                                                        Optional(
                                                            "protection-types"
                                                        ): list,
                                                        # Same flag-driven shape as the
                                                        # regular FastReroute parser — see
                                                        # comments there.
                                                        Optional(
                                                            "pq-node-system-id"
                                                        ): str,
                                                        Optional(
                                                            "p-node-system-id"
                                                        ): str,
                                                        Optional(
                                                            "q-node-system-id"
                                                        ): str,
                                                    }
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
        }
    }


class ShowIsisFlexAlgoFastReroute(ShowIsisFlexAlgoFastRerouteSchema):
    """Parser for ArcOS ISIS flexible-algorithm fast-reroute (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} fast-reroute [<prefix>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} fast-reroute",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        afi: str = "*",
        algo: str = "*",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(afi, "afi")
            validate_input(algo, "algo")
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} fast-reroute"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["flex-algo-fast-reroute"].
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]
            flex_frr_dict: Dict[str, TypeAny] = ni_isis.setdefault(
                "flex-algo-fast-reroute", {}
            )

            for af in af_list:
                afi_name = af.get("afi-name", "")
                afi_name = afi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                safi_name = af.get("safi-name", "")
                safi_name = safi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                af_key = f"{afi_name}-{safi_name}"

                fa_container = af.get(f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithms", {})
                fa_list = fa_container.get("flexible-algorithm", [])

                if not fa_list:
                    continue

                af_entry: Dict[str, TypeAny] = {
                    "afi-name": afi_name,
                    "safi-name": safi_name,
                    "algorithms": {},
                }

                for fa in fa_list:
                    algo_id = fa.get("id")
                    if algo_id is None:
                        continue

                    algo_key = str(algo_id)
                    algo_entry: Dict[str, TypeAny] = {"id": algo_id, "prefixes": {}}

                    frr_container = fa.get("fast-reroutes", {})
                    frr_list = frr_container.get("fast-reroute", [])

                    for frr in frr_list:
                        prefix_str = frr.get("prefix")
                        if not prefix_str:
                            continue

                        prefix_entry: Dict[str, TypeAny] = {
                            "prefix": prefix_str,
                            "levels": {},
                        }

                        levels_obj = frr.get("levels", {})
                        level_list = levels_obj.get("level", [])

                        for level in level_list:
                            level_num = level.get("level-number")
                            if level_num is None:
                                continue

                            state = level.get("state", {})
                            level_entry: Dict[str, TypeAny] = {
                                "level-number": level_num,
                                "reroute-type": state.get("reroute-type", ""),
                                "metric": state.get("metric", 0),
                                "nexthop-address": state.get("nexthop-address", ""),
                                "nexthop-interface": state.get("nexthop-interface", ""),
                                "flags": state.get("flags", []),
                                "last-updated-time": state.get("last-updated-time", ""),
                                "origin-system-id": state.get("origin-system-id", ""),
                            }

                            prot_types = state.get("protection-types", [])
                            if prot_types:
                                level_entry["protection-types"] = [
                                    p.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                    for p in prot_types
                                ]

                            # Flag-driven shape — see ShowIsisFastReroute for details.
                            pq_node = level.get("pq-node", {}).get("state", {})
                            if "system-id" in pq_node:
                                level_entry["pq-node-system-id"] = pq_node["system-id"]

                            p_node = level.get("p-node", {}).get("state", {})
                            if "system-id" in p_node:
                                level_entry["p-node-system-id"] = p_node["system-id"]

                            q_node = level.get("q-node", {}).get("state", {})
                            if "system-id" in q_node:
                                level_entry["q-node-system-id"] = q_node["system-id"]

                            prefix_entry["levels"][str(level_num)] = level_entry

                        algo_entry["prefixes"][prefix_str] = prefix_entry

                    if algo_entry["prefixes"]:
                        af_entry["algorithms"][algo_key] = algo_entry

                if af_entry["algorithms"]:
                    flex_frr_dict[af_key] = af_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Error parsing ISIS flexible-algorithm fast-reroute data: %s", exc
            )

        return ret_dict


class ShowIsisFlexAlgoRouteSchema(MetaParser):
    """Schema for ArcOS ISIS flexible-algorithm routes per AF, algorithm, and prefix.

    Nested under ``isis[instance]['flex-algo-routes']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("flex-algo-routes"): {
                            Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                "afi-name": str,
                                "safi-name": str,
                                "algorithms": {
                                    Any(): {  # flexible-algorithm id as string
                                        "id": int,
                                        "routes": {
                                            Any(): {  # prefix
                                                "prefix": str,
                                                "best-level-number": int,
                                                Optional("levels"): dict,
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisFlexAlgoRoute(ShowIsisFlexAlgoRouteSchema):
    """Parser for ArcOS ISIS flexible-algorithm routes (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} route [<prefix>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} route",
    ]

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        afi: str = "*",
        algo: str = "*",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            validate_input(afi, "afi")
            validate_input(algo, "algo")
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} route"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["flex-algo-routes"].
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]
            flex_routes_dict: Dict[str, TypeAny] = ni_isis.setdefault(
                "flex-algo-routes", {}
            )

            for af in af_list:
                afi_name = af.get("afi-name", "")
                afi_name = afi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                safi_name = af.get("safi-name", "")
                safi_name = safi_name.replace("openconfig-isis-types:", "").replace(
                    "oc-isis-types:", ""
                )

                af_key = f"{afi_name}-{safi_name}"

                fa_container = af.get(f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithms", {})
                fa_list = fa_container.get("flexible-algorithm", [])

                if not fa_list:
                    continue

                af_entry: Dict[str, TypeAny] = {
                    "afi-name": afi_name,
                    "safi-name": safi_name,
                    "algorithms": {},
                }

                for fa in fa_list:
                    algo_id = fa.get("id")
                    if algo_id is None:
                        continue

                    algo_key = str(algo_id)
                    algo_entry: Dict[str, TypeAny] = {"id": algo_id, "routes": {}}

                    routes_obj = fa.get("routes", {})
                    route_list = routes_obj.get("route", [])

                    for route in route_list:
                        prefix_val = route.get("prefix")
                        if not prefix_val:
                            continue

                        state = route.get("state", {})
                        route_entry: Dict[str, TypeAny] = {
                            "prefix": prefix_val,
                            "best-level-number": state.get("best-level-number", 0),
                        }

                        levels_obj = route.get("levels", {})
                        level_list = levels_obj.get("level", [])

                        if level_list:
                            route_entry["levels"] = {}

                            for level in level_list:
                                level_num = level.get("level-number")
                                if level_num is None:
                                    continue

                                level_state = level.get("state", {})
                                level_entry: Dict[str, TypeAny] = {
                                    "level-number": level_num,
                                    "metric": level_state.get("metric", 0),
                                }

                                flags = level_state.get("flags", [])
                                if flags:
                                    level_entry["flags"] = [
                                        f.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                        for f in flags
                                    ]

                                if "next-hop-id" in level_state:
                                    level_entry["next-hop-id"] = str(
                                        level_state["next-hop-id"]
                                    )
                                if "prefix-origin-count" in level_state:
                                    level_entry["prefix-origin-count"] = level_state[
                                        "prefix-origin-count"
                                    ]
                                if "route-tag" in level_state:
                                    level_entry["route-tag"] = level_state["route-tag"]
                                if "last-updated-time" in level_state:
                                    level_entry["last-updated-time"] = level_state[
                                        "last-updated-time"
                                    ]

                                next_hops_obj = level.get("next-hops", {})
                                next_hop_list = next_hops_obj.get("next-hop", [])

                                if next_hop_list:
                                    level_entry["next-hops"] = []
                                    for nh in next_hop_list:
                                        nh_entry: Dict[str, TypeAny] = {}

                                        if "next-hop-address" in nh:
                                            nh_entry["next-hop-address"] = nh[
                                                "next-hop-address"
                                            ]

                                        if "outgoing-interface" in nh:
                                            nh_entry["outgoing-interface"] = nh[
                                                "outgoing-interface"
                                            ]

                                        nh_state = nh.get("state", {})
                                        if nh_state:
                                            if "tunnel-id" in nh_state:
                                                nh_entry["tunnel-id"] = nh_state[
                                                    "tunnel-id"
                                                ]
                                            if "backup" in nh_state:
                                                nh_entry["backup"] = nh_state["backup"]

                                        level_entry["next-hops"].append(nh_entry)

                                route_entry["levels"][str(level_num)] = level_entry

                        algo_entry["routes"][prefix_val] = route_entry

                    if algo_entry["routes"]:
                        af_entry["algorithms"][algo_key] = algo_entry

                if af_entry["algorithms"]:
                    flex_routes_dict[af_key] = af_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS flexible-algorithm routes data: %s", exc)

        return ret_dict


# =============================================================================
# ShowIsisMplsLabelDb - ISIS MPLS Label Database
# =============================================================================


class ShowIsisMplsLabelDbSchema(MetaParser):
    """Schema for ArcOS ISIS MPLS label database.

    CLI Command::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global mpls
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        "mpls": {
                            Optional("igp-ldp-sync-enabled"): bool,
                            Optional("label-db"): {
                                "state": {
                                    Optional("protocol-identifier"): str,
                                    Optional("protocol-name"): str,
                                    Optional("configured-blocks"): int,
                                    Optional("active-blocks"): int,
                                    Optional("active-usages"): int,
                                },
                                Optional("statistics"): {
                                    Optional("label-space"): int,
                                    Optional("labels"): int,
                                    Optional("allocs"): str,
                                    Optional("frees"): str,
                                    Optional("alloc-errors"): str,
                                    Optional("free-errors"): str,
                                },
                                Optional("usages"): {
                                    Any(): {  # usage type (ISIS_SRGB, ISIS_SRLB)
                                        "usage": str,
                                        Optional("blocks-count"): int,
                                        Optional("opaque-flags"): str,
                                        Optional("statistics"): {
                                            Optional("label-space"): int,
                                            Optional("labels"): int,
                                            Optional("allocs"): str,
                                            Optional("frees"): str,
                                            Optional("alloc-errors"): str,
                                            Optional("free-errors"): str,
                                        },
                                        Optional("blocks"): {
                                            Any(): {  # lower-bound as key
                                                "lower-bound": int,
                                                "upper-bound": int,
                                                Optional("block-name"): str,
                                                Optional("opaque-flags"): str,
                                                Optional("statistics"): {
                                                    Optional("label-space"): int,
                                                    Optional("labels"): int,
                                                    Optional("allocs"): str,
                                                    Optional("frees"): str,
                                                    Optional("alloc-errors"): str,
                                                    Optional("free-errors"): str,
                                                },
                                            }
                                        },
                                        Optional("labels"): {
                                            Any(): {  # label value as key
                                                "label": int,
                                                Optional("block-name"): str,
                                                Optional("label-key"): {
                                                    Optional("type"): str,
                                                    Optional("sub-type"): int,
                                                    Optional("table-id"): int,
                                                    Optional("ip-prefix"): str,
                                                    Optional("nh-address"): str,
                                                    Optional("ifindex"): str,
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
        }
    }


class ShowIsisMplsLabelDb(ShowIsisMplsLabelDbSchema):
    """Parser for ArcOS ISIS MPLS label database (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global mpls
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global mpls",
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
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} global mpls"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        ret_dict: Dict[str, TypeAny] = {"network-instance": {}}

        try:
            parsed_json = load_json_robust(output)

            data = parsed_json.get("data", {})
            network_instances = data.get(
                "openconfig-network-instance:network-instances", {}
            )
            ni_list = network_instances.get("network-instance", [])

            for ni in ni_list:
                ni_name = ni.get("name")
                if not ni_name:
                    continue

                protocols = ni.get("protocols", {})
                protocol_list = protocols.get("protocol", [])

                for protocol in protocol_list:
                    identifier = protocol.get("identifier", "")
                    if "ISIS" not in identifier:
                        continue

                    proto_name = protocol.get("name", "default")
                    isis = protocol.get("isis", {})
                    global_config = isis.get("global", {})
                    mpls = global_config.get("mpls", {})

                    if not mpls:
                        continue

                    # Initialize structure
                    if ni_name not in ret_dict["network-instance"]:
                        ret_dict["network-instance"][ni_name] = {"isis": {}}
                    if proto_name not in ret_dict["network-instance"][ni_name]["isis"]:
                        ret_dict["network-instance"][ni_name]["isis"][proto_name] = {
                            "mpls": {}
                        }

                    mpls_entry = ret_dict["network-instance"][ni_name]["isis"][
                        proto_name
                    ]["mpls"]

                    # IGP-LDP sync
                    igp_ldp_sync = mpls.get("igp-ldp-sync", {})
                    sync_state = igp_ldp_sync.get("state", {})
                    if "enabled" in sync_state:
                        mpls_entry["igp-ldp-sync-enabled"] = sync_state["enabled"]

                    # Label database
                    label_db = mpls.get("arcos-mpls:label-db", {})
                    if not label_db:
                        continue

                    mpls_entry["label-db"] = {"state": {}}

                    # Label DB state
                    db_state = label_db.get("state", {})
                    state_entry = mpls_entry["label-db"]["state"]

                    proto_id = db_state.get("protocol-identifier", "")
                    if proto_id:
                        state_entry["protocol-identifier"] = proto_id.replace(
                            "openconfig-policy-types:", ""
                        )

                    if "protocol-name" in db_state:
                        state_entry["protocol-name"] = db_state["protocol-name"]
                    if "configured-blocks" in db_state:
                        state_entry["configured-blocks"] = db_state["configured-blocks"]
                    if "active-blocks" in db_state:
                        state_entry["active-blocks"] = db_state["active-blocks"]
                    if "active-usages" in db_state:
                        state_entry["active-usages"] = db_state["active-usages"]

                    # Label DB statistics
                    db_stats = label_db.get("statistics", {})
                    if db_stats:
                        mpls_entry["label-db"]["statistics"] = self._parse_statistics(
                            db_stats
                        )

                    # Usages
                    usages_container = label_db.get("usages", {})
                    usage_list = usages_container.get("usage", [])

                    if usage_list:
                        mpls_entry["label-db"]["usages"] = {}
                        for usage in usage_list:
                            usage_key = usage.get("usage", "")
                            usage_key_clean = usage_key.replace("arcos-mpls:", "")

                            usage_entry: Dict[str, TypeAny] = {"usage": usage_key_clean}

                            usage_state = usage.get("state", {})
                            if "blocks" in usage_state:
                                usage_entry["blocks-count"] = usage_state["blocks"]
                            if "opaque-flags" in usage_state:
                                usage_entry["opaque-flags"] = usage_state["opaque-flags"]

                            # Usage statistics
                            usage_stats = usage.get("statistics", {})
                            if usage_stats:
                                usage_entry["statistics"] = self._parse_statistics(
                                    usage_stats
                                )

                            # Blocks
                            blocks_container = usage.get("blocks", {})
                            block_list = blocks_container.get("block", [])
                            if block_list:
                                usage_entry["blocks"] = {}
                                for block in block_list:
                                    lower = block.get("lower-bound")
                                    if lower is None:
                                        continue

                                    block_state = block.get("state", {})
                                    block_entry: Dict[str, TypeAny] = {
                                        "lower-bound": lower,
                                        "upper-bound": block_state.get("upper-bound", 0),
                                    }

                                    if "block-name" in block_state:
                                        block_entry["block-name"] = block_state[
                                            "block-name"
                                        ]
                                    if "opaque-flags" in block_state:
                                        block_entry["opaque-flags"] = block_state[
                                            "opaque-flags"
                                        ]

                                    block_stats = block.get("statistics", {})
                                    if block_stats:
                                        block_entry["statistics"] = (
                                            self._parse_statistics(block_stats)
                                        )

                                    usage_entry["blocks"][str(lower)] = block_entry

                            # Labels
                            labels_container = usage.get("labels", {})
                            label_list = labels_container.get("label", [])
                            if label_list:
                                usage_entry["labels"] = {}
                                for label in label_list:
                                    label_val = label.get("label")
                                    if label_val is None:
                                        continue

                                    label_state = label.get("state", {})
                                    label_entry: Dict[str, TypeAny] = {
                                        "label": label_val,
                                    }

                                    if "block-name" in label_state:
                                        label_entry["block-name"] = label_state[
                                            "block-name"
                                        ]

                                    # Label key
                                    label_key_obj = label.get("label-key", {})
                                    key_state = label_key_obj.get("state", {})
                                    if key_state:
                                        key_entry: Dict[str, TypeAny] = {}

                                        key_type = key_state.get("type", "")
                                        if key_type:
                                            key_entry["type"] = key_type.replace(
                                                "arcos-mpls:", ""
                                            )
                                        if "sub-type" in key_state:
                                            key_entry["sub-type"] = key_state["sub-type"]
                                        if "table-id" in key_state:
                                            key_entry["table-id"] = key_state["table-id"]
                                        if "ip-prefix" in key_state:
                                            key_entry["ip-prefix"] = key_state[
                                                "ip-prefix"
                                            ]
                                        if "nh-address" in key_state:
                                            key_entry["nh-address"] = key_state[
                                                "nh-address"
                                            ]
                                        if "ifindex" in key_state:
                                            key_entry["ifindex"] = key_state["ifindex"]

                                        if key_entry:
                                            label_entry["label-key"] = key_entry

                                    usage_entry["labels"][str(label_val)] = label_entry

                            mpls_entry["label-db"]["usages"][usage_key_clean] = (
                                usage_entry
                            )

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS MPLS label database: %s", exc)

        return ret_dict

    def _parse_statistics(self, stats: Dict) -> Dict[str, TypeAny]:
        """Parse statistics section."""
        result: Dict[str, TypeAny] = {}
        if "label-space" in stats:
            result["label-space"] = stats["label-space"]
        if "labels" in stats:
            result["labels"] = stats["labels"]
        if "allocs" in stats:
            result["allocs"] = stats["allocs"]
        if "frees" in stats:
            result["frees"] = stats["frees"]
        if "alloc-errors" in stats:
            result["alloc-errors"] = stats["alloc-errors"]
        if "free-errors" in stats:
            result["free-errors"] = stats["free-errors"]
        return result


# =============================================================================
# ShowIsisLevelState
# =============================================================================


class ShowIsisLevelStateSchema(MetaParser):
    """Schema for 'show isis level state'."""

    schema = {
        "network-instance": {
            Any(): {
                "isis": {
                    Any(): {
                        "levels": {
                            Any(): {
                                "level": int,
                                Optional("enabled"): bool,
                                Optional("metric-style"): str,
                                Optional("lsp-count"): int,
                                Optional("dynamic-hostname"): {
                                    Any(): str,  # system-id -> hostname
                                },
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisLevelState(ShowIsisLevelStateSchema):
    """Parser for 'show isis level state'.

    CLI: show network-instance {network_instance} protocol ISIS {protocol_instance}
         level {level} state
    """

    cli_command = (
        "show network-instance {network_instance} protocol ISIS "
        "{protocol_instance} level {level} state"
    )

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        level: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        """Parse ISIS level state output."""

        ret_dict: Dict[str, TypeAny] = {}

        if output is None:
            cmd = self.cli_command.format(
                network_instance=network_instance,
                protocol_instance=protocol_instance,
                level=level,
            )
            output = self.device.execute(f"{cmd} | display json | nomore")

        if not output or not output.strip():
            return ret_dict

        try:
            parsed_json = load_json_robust(output)
            root = (
                parsed_json.get("data", {})
                .get("openconfig-network-instance:network-instances", {})
                .get("network-instance", [])
            )

            if not root:
                return ret_dict

            ret_dict["network-instance"] = {}

            for ni in root:
                ni_name = ni.get("name", "")
                if not ni_name:
                    continue

                # Filter by network_instance if specified
                if network_instance != "*" and ni_name != network_instance:
                    continue

                protocols = ni.get("protocols", {}).get("protocol", [])
                for proto in protocols:
                    ident = proto.get("identifier", "")
                    if "ISIS" not in ident:
                        continue

                    proto_name = proto.get("name", "")
                    if not proto_name:
                        continue

                    # Filter by protocol_instance if specified
                    if protocol_instance != "*" and proto_name != protocol_instance:
                        continue

                    isis_data = proto.get("isis", {})
                    levels_data = isis_data.get("levels", {}).get("level", [])

                    if not levels_data:
                        continue

                    # Initialize nested dicts
                    if ni_name not in ret_dict["network-instance"]:
                        ret_dict["network-instance"][ni_name] = {"isis": {}}
                    if proto_name not in ret_dict["network-instance"][ni_name]["isis"]:
                        ret_dict["network-instance"][ni_name]["isis"][proto_name] = {
                            "levels": {}
                        }

                    levels_dict = ret_dict["network-instance"][ni_name]["isis"][
                        proto_name
                    ]["levels"]

                    for lvl in levels_data:
                        level_num = lvl.get("level-number")
                        if level_num is None:
                            continue

                        # Filter by level if specified
                        if level != "*" and str(level_num) != str(level):
                            continue

                        lvl_state = lvl.get("state", {})
                        level_entry: Dict[str, TypeAny] = {
                            "level": level_num,
                        }

                        if "enabled" in lvl_state:
                            level_entry["enabled"] = lvl_state["enabled"]

                        if "metric-style" in lvl_state:
                            level_entry["metric-style"] = lvl_state["metric-style"]

                        # Level stats summary
                        stats_summary = lvl_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:level-stats-summary", {}
                        )
                        lsp_count = stats_summary.get("lsp-count")
                        if lsp_count is not None:
                            # Convert string to int if needed
                            level_entry["lsp-count"] = (
                                int(lsp_count) if isinstance(lsp_count, str) else lsp_count
                            )

                        # Dynamic hostname - convert list to dict
                        dyn_hostname_list = lvl_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:dynamic-hostname", []
                        )
                        if dyn_hostname_list:
                            hostname_dict: Dict[str, str] = {}
                            for entry in dyn_hostname_list:
                                sys_id = entry.get("system-id")
                                hostname = entry.get("hostname")
                                if sys_id and hostname:
                                    hostname_dict[sys_id] = hostname
                            if hostname_dict:
                                level_entry["dynamic-hostname"] = hostname_dict

                        levels_dict[str(level_num)] = level_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS level state: %s", exc)

        return ret_dict


# =============================================================================
# ShowIsisLevelCounters
# =============================================================================


class ShowIsisLevelCountersSchema(MetaParser):
    """Schema for 'show isis level counters'."""

    schema = {
        "network-instance": {
            Any(): {
                "isis": {
                    Any(): {
                        "levels": {
                            Any(): {
                                Optional("corrupted-lsps"): int,
                                Optional("database-overloads"): int,
                                Optional("manual-address-drop-from-areas"): int,
                                Optional("exceed-max-seq-nums"): int,
                                Optional("seq-num-skips"): int,
                                Optional("own-lsp-purges"): int,
                                Optional("id-len-mismatch"): int,
                                Optional("part-changes"): int,
                                Optional("max-area-address-mismatches"): int,
                                Optional("auth-fails"): int,
                                Optional("auth-type-fails"): int,
                                Optional("spf-runs"): int,
                                Optional("lsp-errors"): int,
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisLevelCounters(ShowIsisLevelCountersSchema):
    """Parser for 'show isis level system-level-counters'.

    CLI: show network-instance {network_instance} protocol ISIS {protocol_instance}
         level {level} system-level-counters
    """

    cli_command = (
        "show network-instance {network_instance} protocol ISIS "
        "{protocol_instance} level {level} system-level-counters"
    )

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        level: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        """Parse ISIS level counters output."""

        ret_dict: Dict[str, TypeAny] = {}

        if output is None:
            cmd = self.cli_command.format(
                network_instance=network_instance,
                protocol_instance=protocol_instance,
                level=level,
            )
            output = self.device.execute(f"{cmd} | display json | nomore")

        if not output or not output.strip():
            return ret_dict

        try:
            parsed_json = load_json_robust(output)
            root = (
                parsed_json.get("data", {})
                .get("openconfig-network-instance:network-instances", {})
                .get("network-instance", [])
            )

            if not root:
                return ret_dict

            ret_dict["network-instance"] = {}

            for ni in root:
                ni_name = ni.get("name", "")
                if not ni_name:
                    continue

                # Filter by network_instance if specified
                if network_instance != "*" and ni_name != network_instance:
                    continue

                protocols = ni.get("protocols", {}).get("protocol", [])
                for proto in protocols:
                    ident = proto.get("identifier", "")
                    if "ISIS" not in ident:
                        continue

                    proto_name = proto.get("name", "")
                    if not proto_name:
                        continue

                    # Filter by protocol_instance if specified
                    if protocol_instance != "*" and proto_name != protocol_instance:
                        continue

                    isis_data = proto.get("isis", {})
                    levels_data = isis_data.get("levels", {}).get("level", [])

                    if not levels_data:
                        continue

                    # Initialize nested dicts
                    if ni_name not in ret_dict["network-instance"]:
                        ret_dict["network-instance"][ni_name] = {"isis": {}}
                    if proto_name not in ret_dict["network-instance"][ni_name]["isis"]:
                        ret_dict["network-instance"][ni_name]["isis"][proto_name] = {
                            "levels": {}
                        }

                    levels_dict = ret_dict["network-instance"][ni_name]["isis"][
                        proto_name
                    ]["levels"]

                    for lvl in levels_data:
                        level_num = lvl.get("level-number")
                        if level_num is None:
                            continue

                        # Filter by level if specified
                        if level != "*" and str(level_num) != str(level):
                            continue

                        counters_data = lvl.get("system-level-counters", {}).get(
                            "state", {}
                        )

                        if not counters_data:
                            # Return empty dict for level if no counters
                            levels_dict[str(level_num)] = {}
                            continue

                        counter_entry: Dict[str, TypeAny] = {}

                        # All counter fields
                        counter_fields = [
                            "corrupted-lsps",
                            "database-overloads",
                            "manual-address-drop-from-areas",
                            "exceed-max-seq-nums",
                            "seq-num-skips",
                            "own-lsp-purges",
                            "id-len-mismatch",
                            "part-changes",
                            "max-area-address-mismatches",
                            "auth-fails",
                            "auth-type-fails",
                            "spf-runs",
                            "lsp-errors",
                        ]

                        for field in counter_fields:
                            if field in counters_data:
                                counter_entry[field] = counters_data[field]

                        levels_dict[str(level_num)] = counter_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS level counters: %s", exc)

        return ret_dict


# =============================================================================
# ShowIsisSpfLog
# =============================================================================


class ShowIsisSpfLogSchema(MetaParser):
    """Schema for 'show isis spf-log'."""

    schema = {
        "network-instance": {
            Any(): {
                "isis": {
                    Any(): {
                        "spf-log": {
                            Any(): {
                                "id": int,
                                "spf-type": str,
                                "level": int,
                                "topology-id": str,
                                "algorithm": int,
                                "schedule-time": str,
                                "delay": int,
                                Optional("start-time"): str,
                                Optional("end-time"): str,
                                Optional("duration"): int,
                                Optional("node-count"): int,
                                Optional("prefix-count"): int,
                                Optional("route-download-count"): int,
                                Optional("trigger-lsp"): list,
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisSpfLog(ShowIsisSpfLogSchema):
    """Parser for 'show isis spf-log'.

    CLI: show network-instance {network_instance} protocol ISIS {protocol_instance}
         global spf-log
    """

    cli_command = (
        "show network-instance {network_instance} protocol ISIS "
        "{protocol_instance} global spf-log"
    )

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        """Parse ISIS SPF log output."""

        ret_dict: Dict[str, TypeAny] = {}

        if output is None:
            cmd = self.cli_command.format(
                network_instance=network_instance,
                protocol_instance=protocol_instance,
            )
            output = self.device.execute(f"{cmd} | display json | nomore")

        if not output or not output.strip():
            return ret_dict

        try:
            parsed_json = load_json_robust(output)
            root = (
                parsed_json.get("data", {})
                .get("openconfig-network-instance:network-instances", {})
                .get("network-instance", [])
            )

            if not root:
                return ret_dict

            ret_dict["network-instance"] = {}

            for ni in root:
                ni_name = ni.get("name", "")
                if not ni_name:
                    continue

                protocols = ni.get("protocols", {}).get("protocol", [])
                for proto in protocols:
                    ident = proto.get("identifier", "")
                    if "ISIS" not in ident:
                        continue

                    proto_name = proto.get("name", "")
                    if not proto_name:
                        continue

                    isis_data = proto.get("isis", {})
                    global_data = isis_data.get("global", {})
                    spf_log_data = global_data.get(
                        f"{ARCOS_ISIS_AUGMENTS}:spf-log", {}
                    )
                    events = spf_log_data.get("event", [])

                    if not events:
                        continue

                    # Initialize nested dicts
                    if ni_name not in ret_dict["network-instance"]:
                        ret_dict["network-instance"][ni_name] = {"isis": {}}
                    if proto_name not in ret_dict["network-instance"][ni_name]["isis"]:
                        ret_dict["network-instance"][ni_name]["isis"][proto_name] = {
                            "spf-log": {}
                        }

                    spf_log_dict = ret_dict["network-instance"][ni_name]["isis"][
                        proto_name
                    ]["spf-log"]

                    for event in events:
                        event_id = event.get("id")
                        if event_id is None:
                            continue

                        entry: Dict[str, TypeAny] = {
                            "id": event_id,
                        }

                        # Required fields
                        if "spf-type" in event:
                            entry["spf-type"] = event["spf-type"]

                        if "level" in event:
                            entry["level"] = event["level"]

                        if "topology-id" in event:
                            # Strip namespace prefix
                            topo_id = event["topology-id"]
                            if ":" in topo_id:
                                topo_id = topo_id.split(":")[-1]
                            entry["topology-id"] = topo_id

                        if "algorithm" in event:
                            entry["algorithm"] = event["algorithm"]

                        if "schedule-time" in event:
                            entry["schedule-time"] = event["schedule-time"]

                        if "delay" in event:
                            delay = event["delay"]
                            entry["delay"] = (
                                int(delay) if isinstance(delay, str) else delay
                            )

                        # Optional fields (only present for completed SPF)
                        if "start-time" in event:
                            entry["start-time"] = event["start-time"]

                        if "end-time" in event:
                            entry["end-time"] = event["end-time"]

                        if "duration" in event:
                            duration = event["duration"]
                            entry["duration"] = (
                                int(duration) if isinstance(duration, str) else duration
                            )

                        if "node-count" in event:
                            node_count = event["node-count"]
                            entry["node-count"] = (
                                int(node_count)
                                if isinstance(node_count, str)
                                else node_count
                            )

                        if "prefix-count" in event:
                            prefix_count = event["prefix-count"]
                            entry["prefix-count"] = (
                                int(prefix_count)
                                if isinstance(prefix_count, str)
                                else prefix_count
                            )

                        if "route-download-count" in event:
                            route_dl = event["route-download-count"]
                            entry["route-download-count"] = (
                                int(route_dl) if isinstance(route_dl, str) else route_dl
                            )

                        # Trigger LSP list
                        trigger_lsp_data = event.get("trigger-lsp", [])
                        if trigger_lsp_data:
                            trigger_list = []
                            for trigger in trigger_lsp_data:
                                trigger_entry: Dict[str, TypeAny] = {}
                                if "id" in trigger:
                                    trigger_entry["id"] = trigger["id"]
                                if "lsp-id" in trigger:
                                    trigger_entry["lsp-id"] = trigger["lsp-id"]
                                if "sequence" in trigger:
                                    trigger_entry["sequence"] = trigger["sequence"]
                                if "trigger-time" in trigger:
                                    trigger_entry["trigger-time"] = trigger[
                                        "trigger-time"
                                    ]
                                if trigger_entry:
                                    trigger_list.append(trigger_entry)
                            if trigger_list:
                                entry["trigger-lsp"] = trigger_list

                        spf_log_dict[str(event_id)] = entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS SPF log: %s", exc)

        return ret_dict


class ShowIsisGlobalTimersSchema(MetaParser):
    """Schema for ArcOS ISIS global timer state JSON output.

    Covers::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global timers
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("timers"): {
                            # LSP timers (from timers.state — flattened)
                            Optional("lsp-lifetime-interval"): Or(str, int),
                            Optional("lsp-refresh-interval"): Or(str, int),
                            Optional("lsp-flood-delay-adj-up"): Or(str, int),
                            # SPF timers (from timers.spf.state — flattened into "spf")
                            Optional("spf"): {
                                Optional("spf-hold-interval"): Or(str, int),
                                Optional("spf-first-interval"): Or(str, int),
                                Optional("spf-second-interval"): Or(str, int),
                                Optional("spf-mla-interval"): Or(str, int),
                            },
                        }
                    }
                }
            }
        }
    }


class ShowIsisGlobalTimers(ShowIsisGlobalTimersSchema):
    """Parser for ArcOS ISIS global timers command (JSON format).

    Supports::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global timers | display json | nomore
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global timers",
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
            cmd = (
                f"show network-instance {network_instance} protocol ISIS "
                f"{protocol_instance} global timers"
            )
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            timers_data = isis.get("global", {}).get("timers", {})
            if not timers_data:
                return ret_dict

            timers_entry: Dict[str, TypeAny] = {}
            aug_prefix = f"{ARCOS_ISIS_AUGMENTS}:"

            # LSP timers — from timers.state (flatten)
            lsp_state = timers_data.get("state", {})
            if "lsp-lifetime-interval" in lsp_state:
                timers_entry["lsp-lifetime-interval"] = lsp_state["lsp-lifetime-interval"]
            if "lsp-refresh-interval" in lsp_state:
                timers_entry["lsp-refresh-interval"] = lsp_state["lsp-refresh-interval"]
            flood_delay_key = f"{aug_prefix}lsp-flood-delay-adj-up"
            if flood_delay_key in lsp_state:
                timers_entry["lsp-flood-delay-adj-up"] = lsp_state[flood_delay_key]

            # SPF timers — from timers.spf.state (flatten into "spf" sub-dict)
            spf_state = timers_data.get("spf", {}).get("state", {})
            if spf_state:
                spf_entry: Dict[str, TypeAny] = {}
                if "spf-hold-interval" in spf_state:
                    spf_entry["spf-hold-interval"] = spf_state["spf-hold-interval"]
                if "spf-first-interval" in spf_state:
                    spf_entry["spf-first-interval"] = spf_state["spf-first-interval"]
                if "spf-second-interval" in spf_state:
                    spf_entry["spf-second-interval"] = spf_state["spf-second-interval"]
                mla_key = f"{aug_prefix}spf-mla-interval"
                if mla_key in spf_state:
                    spf_entry["spf-mla-interval"] = spf_state[mla_key]
                if spf_entry:
                    timers_entry["spf"] = spf_entry

            if timers_entry:
                ret_dict["network-instance"]["default"]["isis"]["default"][
                    "timers"
                ] = timers_entry

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS global timers: %s", exc)

        return ret_dict


# ============================================================================
#                       Show ISIS Protection-Tracker Parser
# ============================================================================
class ShowIsisProtectionTrackerSchema(MetaParser):
    """Schema for ArcOS ISIS global protection-tracker JSON output.

    The protection-tracker is a per-protected-interface object created by
    TI-LFA. Each entry tracks a protected interface, the adjacent system-id
    being protected, and (when BFD is enabled) the BFD session linked to
    fast-failure detection. Multiple entries can coexist on a device that
    has TI-LFA enabled on multiple interfaces. When TI-LFA is not enabled
    anywhere, the device returns ``{"data": {}}`` and the parser returns
    an empty dict.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name (e.g., "default")
                "isis": {
                    Any(): {  # protocol instance name (e.g., "default")
                        Optional("global"): {
                            Optional("protection-trackers"): {
                                Optional("protection-tracker"): {
                                    Any(): {  # keyed by tracker id (str)
                                        Optional("id"): Or(str, int),
                                        Optional("reference-count"): int,
                                        Optional("interface"): str,
                                        Optional("system-id"): str,
                                        Optional("last-updated-time"): str,
                                        Optional("bfd-source"): str,
                                        Optional("bfd-destination"): str,
                                        Optional("bfd-session-id"): Or(str, int),
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisProtectionTracker(ShowIsisProtectionTrackerSchema):
    """Parser for ArcOS ISIS global protection-tracker command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global protection-tracker

    The parser flattens the OpenConfig ``state`` wrapper, strips the
    ``arcos-openconfig-isis-augments:`` augment prefix from container keys,
    and keys the protection-tracker list by ``id`` for deterministic lookup.
    Empty data (``{"data": {}}``) is normalized to an empty result dict.
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global protection-tracker",
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
            cmd = (
                f"show network-instance {network_instance} protocol ISIS "
                f"{protocol_instance} global protection-tracker"
            )
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing protection-tracker output")
        ret_dict: Dict[str, TypeAny] = {}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            return ret_dict
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error loading JSON: %s", exc)
            return ret_dict

        try:
            data = parsed_json.get("data", {})
            ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
            if not ni_container:
                # Empty case — no network-instances container at all
                return ret_dict

            trackers_key = f"{ARCOS_ISIS_AUGMENTS}:protection-trackers"

            for ni in ni_container.get("network-instance", []) or []:
                ni_name = ni.get("name")
                if not ni_name:
                    continue
                for protocol in ni.get("protocols", {}).get("protocol", []) or []:
                    # Only process ISIS protocol entries
                    identifier = protocol.get("identifier", "")
                    if "ISIS" not in identifier:
                        continue
                    pi_name = protocol.get("name")
                    if not pi_name:
                        continue
                    isis_data = protocol.get("isis", {})
                    global_data = isis_data.get("global", {})
                    trackers_container = global_data.get(trackers_key, {})
                    tracker_list = trackers_container.get(
                        "protection-tracker", []
                    ) or []
                    if not tracker_list:
                        continue

                    tracker_dict: Dict[str, TypeAny] = {}
                    for entry in tracker_list:
                        entry_id = entry.get("id")
                        if entry_id is None:
                            continue
                        state = entry.get("state", {}) or {}

                        # Flatten state into the entry — keep hyphenated keys.
                        flat: Dict[str, TypeAny] = {"id": entry_id}
                        for field in (
                            "reference-count",
                            "interface",
                            "system-id",
                            "last-updated-time",
                            "bfd-source",
                            "bfd-destination",
                            "bfd-session-id",
                        ):
                            if field in state:
                                flat[field] = state[field]

                        # Key by id (stringified for consistency with other parsers)
                        tracker_dict[str(entry_id)] = flat

                    if tracker_dict:
                        ret_dict.setdefault("network-instance", {}).setdefault(
                            ni_name, {}
                        ).setdefault("isis", {}).setdefault(pi_name, {}).setdefault(
                            "global", {}
                        ).setdefault("protection-trackers", {})[
                            "protection-tracker"
                        ] = tracker_dict

        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Error parsing ISIS protection-tracker: %s", exc
            )

        return ret_dict


class ShowIsisGlobalTunnelSchema(MetaParser):
    """Schema for ArcOS ISIS global tunnel command (JSON format).

    Captures SRv6 TI-LFA and Microloop-Avoidance tunnel state. Each tunnel
    has an integer ID and an SRv6 sub-block with the SID list used as the
    repair-path encapsulation header.

    Schema design notes:
      * ``users`` and ``sids`` are kept as ``list`` so the parser is
        forward-compatible with multi-SID stacks and the
        ``MICRO_LOOP_AVOID_TUNNEL`` user type observed in the docs example
        (``Command_Line_Interface/ISIS_TILFA_Microloop.adoc:487``).
      * ``id`` is ``Or(str, int)`` defensively — JSON samples return string
        IDs but tunnel IDs are integer-typed values; future builds may
        return native ints.
      * The ``state`` wrapper is flattened per project Convention 2.
      * The ``arcos-openconfig-isis-augments:`` prefix is stripped from the
        ``tunnels`` container key per Convention 4.
    """

    schema = {
        "network-instance": {
            Any(): {                                       # network instance name
                "isis": {
                    Any(): {                               # protocol instance name
                        Optional("tunnels"): {
                            Any(): {                       # tunnel id (str/int)
                                Optional("id"): Or(str, int),
                                Optional("nexthop-address"): str,
                                Optional("nexthop-interface"): str,
                                Optional("users"): list,
                                Optional("tunnel-type"): str,
                                Optional("reference-count"): int,
                                Optional("srv6-tunnel"): {
                                    Optional("source"): str,
                                    Optional("destination"): str,
                                    Optional("num-sids"): int,
                                    Optional("sids"): list,
                                },
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisGlobalTunnel(ShowIsisGlobalTunnelSchema):
    """Parser for ArcOS ISIS global tunnel command (JSON format).

    Command patterns (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} global tunnel
        show network-instance {network_instance} protocol ISIS {protocol_instance} global tunnel {tunnel_id}

    Used by the TI-LFA + MLA test suites to confirm SRv6 backup-path
    encapsulation is programmed (``SRV6_TUNNEL`` with ``TI_LFA_TUNNEL`` or
    ``MICRO_LOOP_AVOID_TUNNEL`` user) and to inspect the SID list. arcOS
    only emits ``global tunnel`` content for SRv6 — SR-MPLS uses inline
    label pushes (no tunnel object).

    The parser flattens the ``state`` wrapper, strips the
    ``arcos-openconfig-isis-augments:`` prefix from the tunnels container
    key and from any prefixed user/type value strings, and keys the tunnel
    list by ``id`` for deterministic lookup. Empty data (``{"data": {}}``)
    returns an empty result dict.
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global tunnel",
        "show network-instance {network_instance} protocol ISIS {protocol_instance} global tunnel {tunnel_id}",
    ]

    # Value-prefix strip set (per Convention 4)
    _USER_VALUE_PREFIXES = (
        f"{ARCOS_ISIS_AUGMENTS}:",
        "openconfig-isis-types:",
        "oc-isis-types:",
    )

    def cli(
        self,
        network_instance: str = "*",
        protocol_instance: str = "*",
        tunnel_id: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            validate_input(protocol_instance, "protocol_instance")
            cmd_parts = [
                "show network-instance", network_instance,
                "protocol ISIS", protocol_instance,
                "global tunnel",
            ]
            if tunnel_id is not None:
                validate_input(str(tunnel_id), "tunnel_id")
                cmd_parts.append(str(tunnel_id))
            cmd = " ".join(cmd_parts)
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing global tunnel output")
        ret_dict: Dict[str, TypeAny] = {}

        try:
            parsed_json = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            return ret_dict
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error loading JSON: %s", exc)
            return ret_dict

        try:
            data = parsed_json.get("data", {})
            ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
            if not ni_container:
                # Empty case — no network-instances container at all
                return ret_dict

            tunnels_key = f"{ARCOS_ISIS_AUGMENTS}:tunnels"

            for ni in ni_container.get("network-instance", []) or []:
                ni_name = ni.get("name")
                if not ni_name:
                    continue
                for protocol in ni.get("protocols", {}).get("protocol", []) or []:
                    identifier = protocol.get("identifier", "")
                    if "ISIS" not in identifier:
                        continue
                    pi_name = protocol.get("name")
                    if not pi_name:
                        continue
                    isis_data = protocol.get("isis", {})
                    global_data = isis_data.get("global", {})
                    tunnels_container = global_data.get(tunnels_key, {})
                    tunnel_list = tunnels_container.get("tunnel", []) or []
                    if not tunnel_list:
                        continue

                    parsed_tunnels: Dict[str, TypeAny] = {}
                    for entry in tunnel_list:
                        entry_id = entry.get("id")
                        if entry_id is None:
                            continue
                        state = entry.get("state", {}) or {}

                        # Flatten state into the entry — keep hyphenated keys.
                        flat: Dict[str, TypeAny] = {"id": entry_id}

                        for scalar in (
                            "nexthop-address",
                            "nexthop-interface",
                            "tunnel-type",
                            "reference-count",
                        ):
                            if scalar in state:
                                val = state[scalar]
                                # Strip arcos-/openconfig- prefix from tunnel-type value
                                if scalar == "tunnel-type" and isinstance(val, str):
                                    for pfx in self._USER_VALUE_PREFIXES:
                                        if val.startswith(pfx):
                                            val = val[len(pfx):]
                                            break
                                flat[scalar] = val

                        # users — list of prefixed strings; strip prefix on each.
                        users = state.get("users")
                        if isinstance(users, list):
                            cleaned_users = []
                            for user in users:
                                if isinstance(user, str):
                                    for pfx in self._USER_VALUE_PREFIXES:
                                        if user.startswith(pfx):
                                            user = user[len(pfx):]
                                            break
                                cleaned_users.append(user)
                            flat["users"] = cleaned_users

                        # srv6-tunnel sub-block — flatten in place (already inline JSON)
                        srv6 = state.get("srv6-tunnel")
                        if isinstance(srv6, dict):
                            srv6_flat: Dict[str, TypeAny] = {}
                            for field in ("source", "destination", "num-sids", "sids"):
                                if field in srv6:
                                    srv6_flat[field] = srv6[field]
                            if srv6_flat:
                                flat["srv6-tunnel"] = srv6_flat

                        parsed_tunnels[str(entry_id)] = flat

                    if parsed_tunnels:
                        ret_dict.setdefault("network-instance", {}).setdefault(
                            ni_name, {}
                        ).setdefault("isis", {}).setdefault(pi_name, {})[
                            "tunnels"
                        ] = parsed_tunnels

        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS global tunnel: %s", exc)

        return ret_dict
