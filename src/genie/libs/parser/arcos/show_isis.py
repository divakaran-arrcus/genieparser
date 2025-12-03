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
    """Schema for ArcOS ISIS adjacency JSON output."""

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("neighbors"): {
                            Any(): {  # neighbor system-id
                                "interface": str,
                                "state": str,
                                Optional("holdtime"): int,
                                Optional("level"): str,
                                Optional("neighbor-ipv4-address"): str,
                                Optional("neighbor-ipv6-address"): str,
                                Optional("adjacency-type"): str,
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
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level} adjacency"
            if adj_router:
                validate_input(adj_router, "adj_router")
                cmd += f" {adj_router}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing output: %s", output)
        # Initialize return dictionary
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis_data = get_isis_data(parsed_json)
            interfaces_data = isis_data.get("interfaces", {}).get("interface", [])

            if not interfaces_data:
                return ret_dict

            neighbors_dict: Dict[str, TypeAny] = {}
            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]

            # Extract neighbors from each interface's adjacencies
            for intf in interfaces_data:
                intf_id = intf.get("interface-id")
                if not intf_id:
                    continue

                levels_data = intf.get("levels", {}).get("level", [])
                for level in levels_data:
                    adjacencies_data = level.get("adjacencies", {}).get("adjacency", [])

                    for adj in adjacencies_data:
                        sys_id = adj.get("system-id")
                        if not sys_id:
                            continue

                        adj_state = adj.get("state", {})

                        neighbor_entry: Dict[str, TypeAny] = {
                            "interface": intf_id,
                            "state": adj_state.get("adjacency-state", "UNKNOWN"),
                        }

                        # Hold time
                        hold_time = adj_state.get("remaining-hold-time")
                        if hold_time is not None:
                            neighbor_entry["holdtime"] = hold_time

                        # Adjacency type / level
                        adj_type = adj_state.get("adjacency-type", "")
                        if adj_type:
                            neighbor_entry["level"] = adj_type
                            neighbor_entry["adjacency-type"] = adj_type

                        # Neighbor IPv4 / IPv6 addresses
                        neighbor_ipv4 = adj_state.get("neighbor-ipv4-address")
                        if neighbor_ipv4:
                            neighbor_entry["neighbor-ipv4-address"] = neighbor_ipv4

                        neighbor_ipv6 = adj_state.get("neighbor-ipv6-address")
                        if neighbor_ipv6:
                            neighbor_entry["neighbor-ipv6-address"] = neighbor_ipv6

                        # Up-time: prefer human-readable format if available
                        adj_up_time = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:adjacency-up-time"
                        )
                        if adj_up_time:
                            neighbor_entry["up-time"] = adj_up_time
                        else:
                            up_time = adj_state.get("up-time")
                            if up_time is not None:
                                neighbor_entry["up-time"] = up_time

                        # State change tracking
                        num_state_changes = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:num-state-changes"
                        )
                        if num_state_changes is not None:
                            neighbor_entry["num-state-changes"] = num_state_changes

                        last_state_ts = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:last-state-change-timestamp"
                        )
                        if last_state_ts:
                            neighbor_entry["last-state-change-timestamp"] = last_state_ts

                        last_down_reason = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:last-down-reason"
                        )
                        if last_down_reason:
                            neighbor_entry["last-down-reason"] = last_down_reason

                        # Circuit IDs
                        local_cid = adj_state.get("local-extended-circuit-id")
                        if local_cid is not None:
                            neighbor_entry["local-extended-circuit-id"] = local_cid

                        neighbor_cid = adj_state.get("neighbor-extended-circuit-id")
                        if neighbor_cid is not None:
                            neighbor_entry["neighbor-extended-circuit-id"] = (
                                neighbor_cid
                            )

                        # Neighbor circuit type
                        neighbor_ct = adj_state.get("neighbor-circuit-type")
                        if neighbor_ct:
                            neighbor_entry["neighbor-circuit-type"] = neighbor_ct

                        # Restart support / suppress / status
                        restart_support = adj_state.get("restart-support")
                        if restart_support is not None:
                            neighbor_entry["restart-support"] = restart_support

                        restart_suppress = adj_state.get("restart-suppress")
                        if restart_suppress is not None:
                            neighbor_entry["restart-suppress"] = restart_suppress

                        restart_status = adj_state.get("restart-status")
                        if restart_status is not None:
                            neighbor_entry["restart-status"] = restart_status

                        # NLPID
                        nlpid = adj_state.get("nlpid")
                        if nlpid:
                            neighbor_entry["nlpid"] = nlpid

                        # ArcOS augments
                        usable = adj_state.get(f"{ARCOS_ISIS_AUGMENTS}:usable")
                        if usable is not None:
                            neighbor_entry["usable"] = usable

                        restart_ack = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:restart-ack"
                        )
                        if restart_ack is not None:
                            neighbor_entry["restart-ack"] = restart_ack

                        restart_req = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:restart-request"
                        )
                        if restart_req is not None:
                            neighbor_entry["restart-request"] = restart_req

                        recv_mt_ids = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:received-multi-topology-ids"
                        )
                        if recv_mt_ids:
                            neighbor_entry["received-multi-topology-ids"] = recv_mt_ids

                        active_mt_ids = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:active-multi-topology-ids"
                        )
                        if active_mt_ids:
                            neighbor_entry["active-multi-topology-ids"] = active_mt_ids

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
                                neighbor_entry["bfd"] = bfd_info

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
                                    neighbor_entry["dynamic-delay-measurement"] = (
                                        ddm_info
                                    )

                        neighbors_dict[sys_id] = neighbor_entry

            if neighbors_dict:
                ni_isis["neighbors"] = neighbors_dict

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS neighbor data: %s", exc)

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
                                Optional("extended_ipv4_reachability"): dict,
                                Optional("ipv6_reachability"): dict,
                                Optional("mt_ipv6_reachability"): dict,
                                Optional("extended_is_neighbor"): dict,
                                Optional("mt_is_neighbor"): dict,
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
                                            "mt_id": loc_state.get("mt-id"),
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
                                                            es_info["endpoint_func"] = func

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
                                                                    es_info["sid_structure"] = {
                                                                        "lb": struct.get("lb-length"),
                                                                        "ln": struct.get("ln-length"),
                                                                        "fun": struct.get("fun-length"),
                                                                        "arg": struct.get("arg-length"),
                                                                    }

                                                        end_sids.append(es_info)

                                                    if end_sids:
                                                        loc_info["end_sids"] = end_sids

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
                                        cap_info["instance_number"] = cap_state["instance-number"]
                                    if "router-id" in cap_state:
                                        cap_info["router_id"] = cap_state["router-id"]

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
                                                cap_info["sr_algorithms"] = algos

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
                                                    cap_info["sr_capability"] = sr_cap

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
                                                cap_info["ipv6_te_router_id"] = ipv6_rid

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
                                                    cap_info["node_msd"] = msd_info

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
                                                        fad_entry["metric_type"] = metric_type.split(":")[-1]
                                                    if fad_entry:
                                                        fad_info[str(fad_id)] = fad_entry
                                                if fad_info:
                                                    cap_info["flex_algo_definitions"] = fad_info

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
                                        "extended_ipv4_reachability", {}
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
                                            "ip_prefix": ip_prefix,
                                        }

                                        if prefix_len is not None:
                                            try:
                                                pfx_info["prefix_len"] = int(prefix_len)
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix_len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if up_down is not None:
                                            pfx_info["up_down"] = bool(up_down)

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
                                                        pfx_info["prefix_sids"] = prefix_sids

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
                                        "mt_ipv6_reachability", {}
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
                                            "ip_prefix": ip_prefix,
                                        }

                                        if prefix_len is not None:
                                            try:
                                                pfx_info["prefix_len"] = int(prefix_len)
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix_len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if mt_id is not None:
                                            pfx_info["mt-id"] = mt_id

                                        if up_down is not None:
                                            pfx_info["up_down"] = bool(up_down)

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
                                        "ipv6_reachability", {}
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
                                            "ip_prefix": ip_prefix,
                                        }

                                        if prefix_len is not None:
                                            try:
                                                pfx_info["prefix_len"] = int(prefix_len)
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix_len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if up_down is not None:
                                            pfx_info["up_down"] = bool(up_down)

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
                                        "extended_is_neighbor", {}
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
                                            "system_id": sys_id,
                                            "metric": nbr_state.get("metric"),
                                        }

                                        if instance_id:
                                            nbr_info["instance_id"] = instance_id

                                        two_way = nbr_state.get(
                                            f"{ARCOS_ISIS_AUGMENTS}:two-way-connectivity"
                                        )
                                        if two_way is not None:
                                            nbr_info["two_way"] = two_way

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
                                    mt_is = db_entry.setdefault("mt_is_neighbor", {})
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
                                                "system_id": sys_id,
                                                "metric": inst_state.get("metric"),
                                            }

                                            if mt_id is not None:
                                                nbr_info["mt_id"] = mt_id

                                            if inst_id:
                                                nbr_info["instance_id"] = inst_id

                                            two_way = inst_state.get(
                                                f"{ARCOS_ISIS_AUGMENTS}:two-way-connectivity"
                                            )
                                            if two_way is not None:
                                                nbr_info["two_way"] = two_way

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
                    nbr_info["link_id"] = {
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
                    nbr_info["ipv4_interface_address"] = addrs

            # IPv4 Neighbor Address
            elif "TLV22_IPV4_NEIGHBOR_ADDRESS" in stype:
                addrs = (
                    sub.get("ipv4-neighbor-address", {})
                    .get("state", {})
                    .get("ipv4-neighbor-address")
                )
                if addrs:
                    nbr_info["ipv4_neighbor_address"] = addrs

            # IPv6 Interface Address
            elif "TLV22_IPV6_INTERFACE_ADDRESS" in stype:
                addrs = (
                    sub.get("ipv6-interface-address", {})
                    .get("state", {})
                    .get("ipv6-interface-address")
                )
                if addrs:
                    nbr_info["ipv6_interface_address"] = addrs

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
                        nbr_info["adjacency_sids"] = adj_sids

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
                                    asla_info["admin_groups"] = groups

                            # Extended Admin Groups
                            elif "EXTENDED_ADMIN_GROUP_TYPE" in subsub_type:
                                groups = (
                                    subsub.get("extended-admin-groups", {})
                                    .get("state", {})
                                    .get("extended-admin-group")
                                )
                                if groups:
                                    asla_info["extended_admin_groups"] = groups

                            # TE Default Metric
                            elif "TE_DEFAULT_METRIC_TYPE" in subsub_type:
                                metric = (
                                    subsub.get("te-default-metric", {})
                                    .get("state", {})
                                    .get("metric")
                                )
                                if metric is not None:
                                    asla_info["te_metric"] = metric

                            # Min/Max Delay
                            elif "MIN_MAX_DELAY_METRIC_TYPE" in subsub_type:
                                delay_state = subsub.get("min-max-delay", {}).get(
                                    "state", {}
                                )
                                if "min-delay" in delay_state:
                                    asla_info["min_delay"] = delay_state["min-delay"]
                                if "max-delay" in delay_state:
                                    asla_info["max_delay"] = delay_state["max-delay"]

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
                            end_x_info["endpoint_func"] = func

                        # Parse SID structure subsubTLV
                        subsubtlvs = end_x.get("subsubtlvs", {}).get("subsubtlv", [])
                        for subsub in subsubtlvs:
                            if "SRV6_SID_STRUCTURE" in subsub.get("type", ""):
                                struct_state = (
                                    subsub.get("srv6-sid-structure", {})
                                    .get("state", {})
                                )
                                if struct_state:
                                    end_x_info["sid_structure"] = {
                                        "lb": struct_state.get("lb-length"),
                                        "ln": struct_state.get("ln-length"),
                                        "fun": struct_state.get("fun-length"),
                                        "arg": struct_state.get("arg-length"),
                                    }

                        end_x_sids.append(end_x_info)

                    if end_x_sids:
                        nbr_info["end_x_sids"] = end_x_sids

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
                        pfx_info["prefix_sids"] = prefix_sids


class ShowIsisInterfaceSchema(MetaParser):
    """Schema for ArcOS ISIS per-interface operational state and counters."""

    schema = {
        "network-instance": {
            Any(): {
                "isis": {
                    Any(): {
                        Optional("interfaces"): {
                            Any(): {  # interface name
                                "enabled": bool,
                                "interface-id": str,
                                Optional("circuit-type"): str,
                                Optional("network-type"): str,
                                Optional("protocol-up"): bool,
                                Optional("passive"): bool,
                                Optional("hello-padding"): str,
                                Optional("snpa"): str,
                                Optional("mtu"): int,
                                Optional("ifindex"): int,
                                Optional("update-index"): int,
                                Optional("speed"): int,
                                Optional("circuit-counters"): dict,
                                Optional("authentication"): dict,
                                Optional("timers"): dict,
                                Optional("bfd"): dict,
                                Optional("fast-reroute"): dict,
                                Optional("afi-safi"): dict,
                                Optional("flexible-algorithm"): dict,
                                Optional("csnp-enabled"): bool,
                                Optional("mpls-ldp-sync-enabled"): bool,
                                Optional("levels"): dict,
                                Optional("adjacencies"): dict,
                            }
                        }
                    }
                }
            }
        }
    }


class ShowIsisInterface(ShowIsisInterfaceSchema):
    """Parser for ArcOS ISIS interface command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} protocol ISIS {protocol_instance} interface [<interface>]
    """

    cli_command = [
        "show network-instance {network_instance} protocol ISIS {protocol_instance} interface",
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
            cmd = f"show network-instance {network_instance} protocol ISIS {protocol_instance} interface"
            if interface:
                validate_input(interface, "interface")
                cmd += f" {interface}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        logger.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {
            "network-instance": {"default": {"isis": {"default": {}}}}
        }

        try:
            parsed_json = load_json_robust(output)

            isis_data = get_isis_data(parsed_json)
            interfaces_data = isis_data.get("interfaces", {}).get("interface", [])

            if not interfaces_data:
                return ret_dict

            interfaces_dict: Dict[str, TypeAny] = {}
            ni_isis = ret_dict["network-instance"]["default"]["isis"]["default"]

            for intf in interfaces_data:
                intf_id = intf.get("interface-id")
                if not intf_id:
                    continue

                state = intf.get("state", {})

                intf_entry: Dict[str, TypeAny] = {
                    "enabled": state.get("enabled", False),
                    "interface-id": intf_id,
                }

                circuit_type = state.get("circuit-type", "")
                if circuit_type:
                    intf_entry["circuit-type"] = circuit_type.split(":")[-1]

                network_type = state.get(f"{ARCOS_ISIS_AUGMENTS}:network-type")
                if network_type:
                    intf_entry["network-type"] = network_type

                protocol_up = state.get(f"{ARCOS_ISIS_AUGMENTS}:protocol-up")
                if protocol_up is not None:
                    intf_entry["protocol-up"] = protocol_up

                passive = state.get("passive")
                if passive is not None:
                    intf_entry["passive"] = passive

                hello_padding = state.get("hello-padding")
                if hello_padding:
                    intf_entry["hello-padding"] = hello_padding

                snpa = state.get(f"{ARCOS_ISIS_AUGMENTS}:snpa")
                if snpa:
                    intf_entry["snpa"] = snpa

                mtu = state.get(f"{ARCOS_ISIS_AUGMENTS}:mtu")
                if mtu is not None:
                    intf_entry["mtu"] = mtu

                ifindex = state.get(f"{ARCOS_ISIS_AUGMENTS}:ifindex")
                if ifindex is not None:
                    intf_entry["ifindex"] = ifindex

                update_index = state.get(f"{ARCOS_ISIS_AUGMENTS}:update-index")
                if update_index is not None:
                    intf_entry["update-index"] = update_index

                speed = state.get(f"{ARCOS_ISIS_AUGMENTS}:speed")
                if speed is not None:
                    intf_entry["speed"] = speed

                circuit_counters_data = intf.get("circuit-counters", {}).get(
                    "state", {}
                )
                if circuit_counters_data:
                    circuit_counters: Dict[str, TypeAny] = {}
                    for key in [
                        "adj-changes",
                        "init-fails",
                        "rejected-adj",
                        "id-field-len-mismatches",
                        "max-area-address-mismatches",
                        "auth-type-fails",
                        "auth-fails",
                        "lan-dis-changes",
                        "adj-number",
                    ]:
                        if key in circuit_counters_data:
                            circuit_counters[key] = circuit_counters_data[key]

                    for key in [
                        "subnet-mismatches",
                        "duplicate-addresses",
                        "martian-addresses",
                        "missing-addresses",
                    ]:
                        aug_key = f"{ARCOS_ISIS_AUGMENTS}:{key}"
                        if aug_key in circuit_counters_data:
                            circuit_counters[key] = circuit_counters_data[aug_key]

                    if circuit_counters:
                        intf_entry["circuit-counters"] = circuit_counters

                auth_data = intf.get("authentication", {})
                if auth_data:
                    auth_state = auth_data.get("state", {})
                    auth_info: Dict[str, TypeAny] = {}
                    if "hello-authentication" in auth_state:
                        auth_info["hello-authentication"] = auth_state[
                            "hello-authentication"
                        ]
                    if "auth-type" in auth_state:
                        auth_info["auth-type"] = auth_state["auth-type"]

                    key_state = auth_data.get("key", {}).get("state", {})
                    crypto_alg = key_state.get(
                        f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm"
                    )
                    if crypto_alg:
                        auth_info["crypto-algorithm"] = crypto_alg

                    if auth_info:
                        intf_entry["authentication"] = auth_info

                timers_data = intf.get("timers", {}).get("state", {})
                if timers_data:
                    timers: Dict[str, TypeAny] = {}
                    if "csnp-interval" in timers_data:
                        timers["csnp-interval"] = timers_data["csnp-interval"]
                    if "lsp-pacing-interval" in timers_data:
                        timers["lsp-pacing-interval"] = timers_data[
                            "lsp-pacing-interval"
                        ]

                    hello_interval = timers_data.get(
                        f"{ARCOS_ISIS_AUGMENTS}:hello-interval"
                    )
                    if hello_interval is not None:
                        timers["hello-interval"] = hello_interval

                    hello_mult = timers_data.get(
                        f"{ARCOS_ISIS_AUGMENTS}:hello-multiplier"
                    )
                    if hello_mult is not None:
                        timers["hello-multiplier"] = hello_mult

                    if timers:
                        intf_entry["timers"] = timers

                bfd_data = intf.get("bfd", {})
                if bfd_data:
                    bfd_info: Dict[str, TypeAny] = {}
                    bfd_state = bfd_data.get("state", {})
                    if "bfd-tlv" in bfd_state:
                        bfd_info["bfd-tlv"] = bfd_state["bfd-tlv"]

                    aug_state = bfd_data.get(f"{ARCOS_ISIS_AUGMENTS}:state", {})
                    if "profile" in aug_state:
                        bfd_info["profile"] = aug_state["profile"]

                    if bfd_info:
                        intf_entry["bfd"] = bfd_info

                frr_data = intf.get(f"{ARCOS_ISIS_AUGMENTS}:fast-reroute", {})
                if frr_data:
                    frr_info: Dict[str, TypeAny] = {}
                    ti_lfa_state = frr_data.get("ti-lfa", {}).get("state", {})
                    if "srv6-enabled" in ti_lfa_state:
                        frr_info["srv6-enabled"] = ti_lfa_state["srv6-enabled"]

                    tiebreaker_data = frr_data.get("tiebreaker", {})
                    if tiebreaker_data:
                        tiebreakers: Dict[str, TypeAny] = {}
                        for tb_type in ["srlg-disjoint", "node-protecting"]:
                            tb_state = tiebreaker_data.get(tb_type, {}).get("state", {})
                            if "priority" in tb_state:
                                tiebreakers[tb_type] = {
                                    "priority": tb_state["priority"]
                                }
                        if tiebreakers:
                            frr_info["tiebreakers"] = tiebreakers

                    if frr_info:
                        intf_entry["fast-reroute"] = frr_info

                # AFI-SAFI per interface with fast-reroute config
                afi_safi_data = intf.get("afi-safi", {}).get("af", [])
                if afi_safi_data:
                    afi_safi_dict: Dict[str, TypeAny] = {}
                    for af in afi_safi_data:
                        af_state = af.get("state", {})
                        afi_name = af_state.get("afi-name", "")
                        safi_name = af_state.get("safi-name", "")
                        if not afi_name:
                            continue

                        # Create key like "IPV4-UNICAST"
                        afi_key = afi_name.split(":")[-1] if ":" in afi_name else afi_name
                        safi_key = (
                            safi_name.split(":")[-1] if ":" in safi_name else safi_name
                        )
                        af_key = f"{afi_key}-{safi_key}" if safi_key else afi_key

                        af_entry: Dict[str, TypeAny] = {
                            "afi-name": afi_key,
                            "safi-name": safi_key,
                            "enabled": af_state.get("enabled", False),
                        }

                        # Fast-reroute config per AFI-SAFI
                        af_frr = af_state.get(f"{ARCOS_ISIS_AUGMENTS}:fast-reroute", {})
                        if af_frr:
                            frr_config: Dict[str, TypeAny] = {}
                            ip_frr = af_frr.get("ip", {}).get("config", {})
                            if "enabled" in ip_frr:
                                frr_config["ip-enabled"] = ip_frr["enabled"]

                            ti_lfa = af_frr.get("ti-lfa", {}).get("config", {})
                            if ti_lfa:
                                srv6_cfg = ti_lfa.get("srv6", {})
                                if "enabled" in srv6_cfg:
                                    frr_config["ti-lfa-srv6-enabled"] = srv6_cfg["enabled"]
                                sr_mpls_cfg = ti_lfa.get("sr-mpls", {})
                                if "enabled" in sr_mpls_cfg:
                                    frr_config["ti-lfa-sr-mpls-enabled"] = sr_mpls_cfg[
                                        "enabled"
                                    ]

                            if frr_config:
                                af_entry["fast-reroute"] = frr_config

                        # IPv4 unnumbered
                        ipv4_unnumbered = af_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:ipv4-unnumbered"
                        )
                        if ipv4_unnumbered is not None:
                            af_entry["ipv4-unnumbered"] = ipv4_unnumbered

                        afi_safi_dict[af_key] = af_entry

                    if afi_safi_dict:
                        intf_entry["afi-safi"] = afi_safi_dict

                # Flexible-algorithm admin-groups at interface level
                flex_algo_data = intf.get(
                    f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithm", {}
                )
                if flex_algo_data:
                    flex_algo_state = flex_algo_data.get("state", {})
                    admin_groups = flex_algo_state.get("admin-groups")
                    if admin_groups:
                        intf_entry["flexible-algorithm"] = {
                            "admin-groups": admin_groups
                        }

                # CSNP enabled
                csnp_data = intf.get(f"{ARCOS_ISIS_AUGMENTS}:csnp", {})
                if csnp_data:
                    csnp_state = csnp_data.get("state", {})
                    if "enabled" in csnp_state:
                        intf_entry["csnp-enabled"] = csnp_state["enabled"]

                # MPLS igp-ldp-sync
                mpls_data = intf.get(f"{ARCOS_ISIS_AUGMENTS}:mpls", {})
                if mpls_data:
                    ldp_sync_state = mpls_data.get("igp-ldp-sync", {}).get("state", {})
                    if "enabled" in ldp_sync_state:
                        intf_entry["mpls-ldp-sync-enabled"] = ldp_sync_state["enabled"]

                levels_data = intf.get("levels", {}).get("level", [])
                if levels_data:
                    levels_dict: Dict[str, TypeAny] = {}
                    for level in levels_data:
                        level_num = level.get("level-number")
                        if level_num is None:
                            continue

                        level_state = level.get("state", {})
                        level_entry: Dict[str, TypeAny] = {
                            "enabled": level_state.get("enabled", False),
                        }

                        metric = level_state.get(f"{ARCOS_ISIS_AUGMENTS}:metric")
                        if metric is not None:
                            level_entry["metric"] = metric

                        priority = level_state.get("priority")
                        if priority is not None:
                            level_entry["priority"] = priority

                        flex_alg = level_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithm"
                        )
                        if flex_alg:
                            level_entry["flexible-algorithm"] = flex_alg

                        packet_counters_data = level.get("packet-counters", {})
                        if packet_counters_data:
                            packet_counters: Dict[str, TypeAny] = {}
                            for pkt_type in [
                                "lsp",
                                "iih",
                                "psnp",
                                "csnp",
                                "unknown",
                            ]:
                                pkt_state = packet_counters_data.get(pkt_type, {}).get(
                                    "state", {}
                                )
                                if pkt_state:
                                    packet_counters[pkt_type] = pkt_state
                            if packet_counters:
                                level_entry["packet-counters"] = packet_counters

                        levels_dict[str(level_num)] = level_entry

                        adjacencies_data = level.get("adjacencies", {}).get(
                            "adjacency", []
                        )
                        if adjacencies_data:
                            adjacencies_dict: Dict[str, TypeAny] = {}
                            for adj in adjacencies_data:
                                sys_id = adj.get("system-id")
                                if not sys_id:
                                    continue

                                adj_state = adj.get("state", {})
                                adj_entry: Dict[str, TypeAny] = {
                                    "system-id": sys_id,
                                    "adjacency-state": adj_state.get(
                                        "adjacency-state", "UNKNOWN"
                                    ),
                                }

                                neighbor_ipv4 = adj_state.get("neighbor-ipv4-address")
                                if neighbor_ipv4:
                                    adj_entry["neighbor-ipv4-address"] = neighbor_ipv4

                                neighbor_ipv6 = adj_state.get("neighbor-ipv6-address")
                                if neighbor_ipv6:
                                    adj_entry["neighbor-ipv6-address"] = neighbor_ipv6

                                hold_time = adj_state.get("remaining-hold-time")
                                if hold_time is not None:
                                    adj_entry["remaining-hold-time"] = hold_time

                                # Up-time: prefer human-readable format if available
                                adj_up_time = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:adjacency-up-time"
                                )
                                if adj_up_time:
                                    adj_entry["up-time"] = adj_up_time
                                else:
                                    up_time = adj_state.get("up-time")
                                    if up_time is not None:
                                        adj_entry["up-time"] = up_time

                                # State change tracking
                                num_state_changes = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:num-state-changes"
                                )
                                if num_state_changes is not None:
                                    adj_entry["num-state-changes"] = num_state_changes

                                last_state_ts = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:last-state-change-timestamp"
                                )
                                if last_state_ts:
                                    adj_entry["last-state-change-timestamp"] = (
                                        last_state_ts
                                    )

                                last_down_reason = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:last-down-reason"
                                )
                                if last_down_reason:
                                    adj_entry["last-down-reason"] = last_down_reason

                                local_cid = adj_state.get("local-extended-circuit-id")
                                if local_cid is not None:
                                    adj_entry["local-extended-circuit-id"] = local_cid

                                neighbor_cid = adj_state.get(
                                    "neighbor-extended-circuit-id"
                                )
                                if neighbor_cid is not None:
                                    adj_entry["neighbor-extended-circuit-id"] = (
                                        neighbor_cid
                                    )

                                neighbor_ct = adj_state.get("neighbor-circuit-type")
                                if neighbor_ct:
                                    adj_entry["neighbor-circuit-type"] = neighbor_ct

                                adj_type = adj_state.get("adjacency-type")
                                if adj_type:
                                    adj_entry["adjacency-type"] = adj_type

                                restart_support = adj_state.get("restart-support")
                                if restart_support is not None:
                                    adj_entry["restart-support"] = restart_support

                                restart_suppress = adj_state.get("restart-suppress")
                                if restart_suppress is not None:
                                    adj_entry["restart-suppress"] = restart_suppress

                                restart_status = adj_state.get("restart-status")
                                if restart_status is not None:
                                    adj_entry["restart-status"] = restart_status

                                nlpid = adj_state.get("nlpid")
                                if nlpid:
                                    adj_entry["nlpid"] = nlpid

                                usable = adj_state.get(f"{ARCOS_ISIS_AUGMENTS}:usable")
                                if usable is not None:
                                    adj_entry["usable"] = usable

                                restart_ack = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:restart-ack"
                                )
                                if restart_ack is not None:
                                    adj_entry["restart-ack"] = restart_ack

                                restart_req = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:restart-request"
                                )
                                if restart_req is not None:
                                    adj_entry["restart-request"] = restart_req

                                recv_mt_ids = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:received-multi-topology-ids"
                                )
                                if recv_mt_ids:
                                    adj_entry["received-multi-topology-ids"] = (
                                        recv_mt_ids
                                    )

                                active_mt_ids = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:active-multi-topology-ids"
                                )
                                if active_mt_ids:
                                    adj_entry["active-multi-topology-ids"] = (
                                        active_mt_ids
                                    )

                                bfd_data = adj.get(f"{ARCOS_ISIS_AUGMENTS}:bfd", {})
                                if bfd_data:
                                    bfd_info: Dict[str, TypeAny] = {}
                                    bfd_state = bfd_data.get("state", {})
                                    if bfd_state.get("bfd-required") is not None:
                                        bfd_info["bfd-required"] = bfd_state[
                                            "bfd-required"
                                        ]

                                    topologies_data = bfd_data.get(
                                        "topologies", {}
                                    ).get("topology", [])
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
                                                    topologies[mt_id][key] = topo_state[
                                                        key
                                                    ]

                                        if topologies:
                                            bfd_info["topologies"] = topologies

                                    if bfd_info:
                                        adj_entry["bfd"] = bfd_info

                                ddm_data = adj.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:dynamic-delay-measurement",
                                    {},
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
                                            adj_entry["dynamic-delay-measurement"] = (
                                                ddm_info
                                            )

                                adjacencies_dict[sys_id] = adj_entry

                            if adjacencies_dict:
                                intf_entry["adjacencies"] = adjacencies_dict

                    if levels_dict:
                        intf_entry["levels"] = levels_dict

                interfaces_dict[intf_id] = intf_entry

            if interfaces_dict:
                ni_isis["interfaces"] = interfaces_dict

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS interface data: %s", exc)

        return ret_dict


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
                                Optional("level_capability"): str,
                                Optional("max_ecmp_paths"): int,
                                Optional("graceful_restart_enabled"): bool,
                                Optional("lsp_mtu_size"): int,
                                Optional("segment_routing_enabled"): bool,
                                Optional("srv6"): {
                                    Optional("enabled"): bool,
                                    Optional("locators"): list,  # list of locator names
                                },
                                Optional("traffic_engineering"): {
                                    Optional("ipv6_router_id"): str,
                                },
                                Optional("micro_loop_avoidance"): {
                                    Optional("srv6_enabled"): bool,
                                    Optional("rib_update_delay"): int,
                                },
                                Optional("lsp_bit"): {
                                    Optional("overload_bit"): {
                                        Optional("set_bit_on_boot"): bool,
                                        Optional("advertise_high_metric"): bool,
                                        Optional("reset_triggers"): list,
                                    },
                                    Optional("attached_bit"): {
                                        Optional("ignore_bit"): bool,
                                        Optional("suppress_bit"): bool,
                                    },
                                },
                                Optional("flexible_algorithms"): {
                                    Any(): {  # algorithm ID
                                        "id": int,
                                        Optional("advertise_definition_enabled"): bool,
                                        Optional("metric_type"): str,
                                    }
                                },
                                Optional("dynamic_delay_measurement"): {
                                    Optional("probe_interval"): int,
                                    Optional("advertisement_interval"): int,
                                },
                                Optional("inter_level_policies"): {
                                    Optional("level1_to_level2"): {
                                        Optional("import_policy"): list,
                                    },
                                    Optional("level2_to_level1"): {
                                        Optional("import_policy"): list,
                                    },
                                },
                            },
                            Optional("levels"): {
                                Any(): {  # level number
                                    "level_number": int,
                                    Optional("enabled"): bool,
                                    Optional("authentication"): {
                                        Optional("lsp_authentication"): bool,
                                        Optional("auth_password"): str,
                                        Optional("crypto_algorithm"): str,
                                    },
                                }
                            },
                            Optional("afi_safi"): {
                                Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                    "afi_name": str,
                                    "safi_name": str,
                                    "enabled": bool,
                                    Optional("multi_topology_enabled"): bool,
                                    Optional("summary_prefixes"): {
                                        Any(): {  # prefix
                                            "prefix": str,
                                            Optional("level"): str,
                                            Optional("algorithm"): int,
                                            Optional("tag"): int,
                                            Optional("adv_unreachable"): bool,
                                        }
                                    },
                                    Optional("prefix_unreachable"): {
                                        Optional("adv_lifetime"): int,
                                        Optional("adv_metric"): int,
                                        Optional("adv_maximum"): int,
                                        Optional("rx_process"): bool,
                                    },
                                }
                            },
                            Optional("interfaces"): {
                                Any(): {  # interface name
                                    "interface_id": str,
                                    "enabled": bool,
                                    Optional("network_type"): str,
                                    Optional("tag"): list,  # list of integers
                                    Optional("authentication"): {
                                        Optional("hello_authentication"): bool,
                                        Optional("auth_password"): str,
                                        Optional("crypto_algorithm"): str,
                                    },
                                    Optional("timers"): {
                                        Optional("hello_interval"): int,
                                        Optional("hello_multiplier"): int,
                                    },
                                    Optional("afi_safi"): {
                                        Any(): {  # AFI-SAFI key
                                            "afi_name": str,
                                            "safi_name": str,
                                            "enabled": bool,
                                            Optional("fast_reroute"): {
                                                Optional("ti_lfa_srv6_enabled"): bool,
                                            },
                                        }
                                    },
                                    Optional("levels"): {
                                        Any(): {  # level number
                                            "level_number": int,
                                            Optional("enabled"): bool,
                                            Optional("metric"): int,
                                            Optional("flexible_algorithm"): {
                                                Optional("delay_metric"): Or(int, str),
                                                Optional("te_metric"): Or(int, str),
                                            },
                                        }
                                    },
                                    Optional("interface_ref"): {
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
                    global_entry["level_capability"] = config["level-capability"]
                if "max-ecmp-paths" in config:
                    global_entry["max_ecmp_paths"] = config["max-ecmp-paths"]

                if global_entry:
                    cfg_root["global"] = global_entry

            # Graceful restart
            gr_config = global_config.get("graceful-restart", {}).get("config", {})
            if gr_config and "enabled" in gr_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["graceful_restart_enabled"] = gr_config["enabled"]

            # Transport (LSP MTU)
            transport_config = global_config.get("transport", {}).get("config", {})
            if transport_config and "lsp-mtu-size" in transport_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["lsp_mtu_size"] = transport_config["lsp-mtu-size"]

            # Segment Routing
            sr_config = global_config.get("segment-routing", {}).get("config", {})
            if sr_config and "enabled" in sr_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["segment_routing_enabled"] = sr_config["enabled"]

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
            if te_config and "ipv6-router-id" in te_config:
                if "global" not in cfg_root:
                    cfg_root["global"] = {}
                cfg_root["global"]["traffic_engineering"] = {
                    "ipv6_router_id": te_config["ipv6-router-id"]
                }

            # Micro Loop Avoidance
            mla_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:micro-loop-avoidance", {}
            )
            mla_config = mla_root.get("config", {})
            if mla_config:
                mla_dict = {}
                if "srv6-enabled" in mla_config:
                    mla_dict["srv6_enabled"] = mla_config["srv6-enabled"]
                if "rib-update-delay" in mla_config:
                    mla_dict["rib_update_delay"] = mla_config["rib-update-delay"]
                if mla_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["micro_loop_avoidance"] = mla_dict

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
                            algo_entry["advertise_definition_enabled"] = adv_def[
                                "enabled"
                            ]

                        if "metric-type" in algo_config:
                            algo_entry["metric_type"] = algo_config["metric-type"]

                        flexalgo_dict[str(algo_id)] = algo_entry

                if flexalgo_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["flexible_algorithms"] = flexalgo_dict

            # Dynamic Delay Measurement
            ddm_root = global_config.get(
                f"{ARCOS_ISIS_AUGMENTS}:dynamic-delay-measurement", {}
            )
            ddm_config = ddm_root.get("config", {})
            if ddm_config:
                ddm_dict = {}
                if "probe-interval" in ddm_config:
                    ddm_dict["probe_interval"] = ddm_config["probe-interval"]
                if "advertisement-interval" in ddm_config:
                    ddm_dict["advertisement_interval"] = ddm_config[
                        "advertisement-interval"
                    ]
                if ddm_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["dynamic_delay_measurement"] = ddm_dict

            # LSP-bit settings (overload/attached bits + reset triggers)
            lsp_root = global_config.get("lsp-bit", {})
            if lsp_root:
                lsp_dict: Dict[str, TypeAny] = {}

                # Overload bit
                ov_root = lsp_root.get("overload-bit", {})
                ov_cfg = ov_root.get("config", {})
                ov_entry: Dict[str, TypeAny] = {}
                if "set-bit-on-boot" in ov_cfg:
                    ov_entry["set_bit_on_boot"] = ov_cfg["set-bit-on-boot"]
                if "advertise-high-metric" in ov_cfg:
                    ov_entry["advertise_high_metric"] = ov_cfg["advertise-high-metric"]

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
                            rt_entry["reset_trigger"] = trigger
                        if "delay" in rt_cfg:
                            rt_entry["delay"] = rt_cfg["delay"]
                        if rt_entry:
                            resets.append(rt_entry)
                    if resets:
                        ov_entry["reset_triggers"] = resets

                if ov_entry:
                    lsp_dict["overload_bit"] = ov_entry

                # Attached bit
                att_root = lsp_root.get("attached-bit", {})
                att_cfg = att_root.get("config", {})
                att_entry: Dict[str, TypeAny] = {}
                if "ignore-bit" in att_cfg:
                    att_entry["ignore_bit"] = att_cfg["ignore-bit"]
                if "suppress-bit" in att_cfg:
                    att_entry["suppress_bit"] = att_cfg["suppress-bit"]

                if att_entry:
                    lsp_dict["attached_bit"] = att_entry

                if lsp_dict:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["lsp_bit"] = lsp_dict

            # Inter-level propagation policies
            inter_root = global_config.get("inter-level-propagation-policies", {})
            if inter_root:
                inter_policies: Dict[str, TypeAny] = {}

                l1_root = inter_root.get("level1-to-level2", {})
                l1_cfg = l1_root.get("config", {})
                if "import-policy" in l1_cfg:
                    inter_policies["level1_to_level2"] = {
                        "import_policy": l1_cfg["import-policy"]
                    }

                l2_root = inter_root.get("level2-to-level1", {})
                l2_cfg = l2_root.get("config", {})
                if "import-policy" in l2_cfg:
                    inter_policies["level2_to_level1"] = {
                        "import_policy": l2_cfg["import-policy"]
                    }

                if inter_policies:
                    if "global" not in cfg_root:
                        cfg_root["global"] = {}
                    cfg_root["global"]["inter_level_policies"] = inter_policies

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
                    lvl_entry: Dict[str, TypeAny] = {"level_number": level_num}
                    if "enabled" in level_config:
                        lvl_entry["enabled"] = level_config["enabled"]

                    # Per-level authentication
                    auth_root = level.get("authentication", {})
                    auth_cfg = auth_root.get("config", {})
                    auth_entry: Dict[str, TypeAny] = {}
                    if "lsp-authentication" in auth_cfg:
                        auth_entry["lsp_authentication"] = auth_cfg["lsp-authentication"]

                    key_cfg = auth_root.get("key", {}).get("config", {})
                    if "auth-password" in key_cfg:
                        auth_entry["auth_password"] = key_cfg["auth-password"]
                    crypto_key = key_cfg.get(f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm")
                    if crypto_key is not None:
                        auth_entry["crypto_algorithm"] = crypto_key

                    if auth_entry:
                        lvl_entry["authentication"] = auth_entry

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
                        "afi_name": afi_name,
                        "safi_name": safi_name,
                        "enabled": af_config.get("enabled", False),
                    }

                    mt = af.get(f"{ARCOS_ISIS_AUGMENTS}:multi-topology", {})
                    mt_config = mt.get("config", {})
                    if "enabled" in mt_config:
                        af_entry["multi_topology_enabled"] = mt_config["enabled"]

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
                                    sum_entry["adv_unreachable"] = sum_config[
                                        "adv-unreachable"
                                    ]
                                summary_dict[prefix] = sum_entry
                        if summary_dict:
                            af_entry["summary_prefixes"] = summary_dict

                    # Prefix unreachable
                    prefix_unreach_root = af.get(
                        f"{ARCOS_ISIS_AUGMENTS}:prefix-unreachable", {}
                    )
                    prefix_unreach_config = prefix_unreach_root.get("config", {})
                    if prefix_unreach_config:
                        unreach_dict = {}
                        if "adv-lifetime" in prefix_unreach_config:
                            unreach_dict["adv_lifetime"] = prefix_unreach_config[
                                "adv-lifetime"
                            ]
                        if "adv-metric" in prefix_unreach_config:
                            unreach_dict["adv_metric"] = prefix_unreach_config[
                                "adv-metric"
                            ]
                        if "adv-maximum" in prefix_unreach_config:
                            unreach_dict["adv_maximum"] = prefix_unreach_config[
                                "adv-maximum"
                            ]
                        if "rx-process" in prefix_unreach_config:
                            unreach_dict["rx_process"] = prefix_unreach_config[
                                "rx-process"
                            ]
                        if unreach_dict:
                            af_entry["prefix_unreachable"] = unreach_dict

                    afi_safi_dict[af_key] = af_entry

                if afi_safi_dict:
                    cfg_root["afi_safi"] = afi_safi_dict

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
                        "interface_id": intf_id,
                        "enabled": intf_config.get("enabled", False),
                    }

                    network_type = intf_config.get(
                        f"{ARCOS_ISIS_AUGMENTS}:network-type"
                    )
                    if network_type:
                        intf_entry["network_type"] = network_type

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
                            auth_dict["hello_authentication"] = auth_config[
                                "hello-authentication"
                            ]

                        auth_key = auth_root.get("key", {}).get("config", {})
                        if "auth-password" in auth_key:
                            auth_dict["auth_password"] = auth_key["auth-password"]
                        if f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm" in auth_key:
                            auth_dict["crypto_algorithm"] = auth_key[
                                f"{ARCOS_ISIS_AUGMENTS}:crypto-algorithm"
                            ]

                        if auth_dict:
                            intf_entry["authentication"] = auth_dict

                    # Timers
                    timers_root = intf.get("timers", {}).get("config", {})
                    if timers_root:
                        timers_dict = {}
                        if f"{ARCOS_ISIS_AUGMENTS}:hello-interval" in timers_root:
                            timers_dict["hello_interval"] = timers_root[
                                f"{ARCOS_ISIS_AUGMENTS}:hello-interval"
                            ]
                        if f"{ARCOS_ISIS_AUGMENTS}:hello-multiplier" in timers_root:
                            timers_dict["hello_multiplier"] = timers_root[
                                f"{ARCOS_ISIS_AUGMENTS}:hello-multiplier"
                            ]
                        if timers_dict:
                            intf_entry["timers"] = timers_dict

                    intf_afi_safi = intf.get("afi-safi", {})
                    intf_af_list = intf_afi_safi.get("af", [])
                    if intf_af_list:
                        intf_entry["afi_safi"] = {}
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
                                "afi_name": afi_name,
                                "safi_name": safi_name,
                                "enabled": af_config.get("enabled", False),
                            }

                            # Fast Reroute (TI-LFA SRv6)
                            frr_root = af_config.get(
                                f"{ARCOS_ISIS_AUGMENTS}:fast-reroute", {}
                            )
                            tilfa_root = frr_root.get("ti-lfa", {}).get("config", {})
                            srv6_root = tilfa_root.get("srv6", {})
                            if "enabled" in srv6_root:
                                intf_af_entry["fast_reroute"] = {
                                    "ti_lfa_srv6_enabled": srv6_root["enabled"]
                                }

                            intf_entry["afi_safi"][af_key] = intf_af_entry

                    intf_levels = intf.get("levels", {})
                    level_list = intf_levels.get("level", [])
                    if level_list:
                        intf_entry["levels"] = {}
                        for level in level_list:
                            level_num = level.get("level-number")
                            if level_num is not None:
                                level_config = level.get("config", {})
                                level_entry = {
                                    "level_number": level_num,
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
                                        flex_entry["delay_metric"] = flexalgo_root[
                                            "delay-metric"
                                        ]
                                    if "te-metric" in flexalgo_root:
                                        flex_entry["te_metric"] = flexalgo_root[
                                            "te-metric"
                                        ]
                                    if flex_entry:
                                        level_entry["flexible_algorithm"] = flex_entry

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
                            intf_entry["interface_ref"] = iface_ref

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
                                "afi_name": str,
                                "safi_name": str,
                                "routes": {
                                    Any(): {  # prefix
                                        "prefix": str,
                                        "best_level_number": int,
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
                    "afi_name": afi_name,
                    "safi_name": safi_name,
                    "routes": {},
                }

                for route in route_list:
                    prefix_val = route.get("prefix")
                    if not prefix_val:
                        continue

                    state = route.get("state", {})
                    route_entry: Dict[str, TypeAny] = {
                        "prefix": prefix_val,
                        "best_level_number": state.get("best-level-number", 0),
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
                                "level_number": level_num,
                                "metric": level_state.get("metric", 0),
                            }

                            flags = level_state.get("flags", [])
                            if flags:
                                level_entry["flags"] = [
                                    f.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                    for f in flags
                                ]

                            if "next-hop-id" in level_state:
                                level_entry["next_hop_id"] = str(
                                    level_state["next-hop-id"]
                                )
                            if "prefix-origin-count" in level_state:
                                level_entry["prefix_origin_count"] = level_state[
                                    "prefix-origin-count"
                                ]
                            if "route-tag" in level_state:
                                level_entry["route_tag"] = level_state["route-tag"]
                            if "last-updated-time" in level_state:
                                level_entry["last_updated_time"] = level_state[
                                    "last-updated-time"
                                ]

                            next_hops_obj = level.get("next-hops", {})
                            next_hop_list = next_hops_obj.get("next-hop", [])

                            if next_hop_list:
                                level_entry["next_hops"] = []
                                for nh in next_hop_list:
                                    nh_entry: Dict[str, TypeAny] = {}

                                    if "next-hop-address" in nh:
                                        nh_entry["next_hop_address"] = nh[
                                            "next-hop-address"
                                        ]

                                    if "outgoing-interface" in nh:
                                        nh_entry["outgoing_interface"] = nh[
                                            "outgoing-interface"
                                        ]

                                    nh_state = nh.get("state", {})
                                    if nh_state:
                                        if "tunnel-id" in nh_state:
                                            nh_entry["tunnel_id"] = nh_state[
                                                "tunnel-id"
                                            ]
                                        if "backup" in nh_state:
                                            nh_entry["backup"] = nh_state["backup"]

                                    level_entry["next_hops"].append(nh_entry)

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
    ``isis[instance]['redistribute_routes']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("redistribute_routes"): {
                            Any(): {  # AF key (e.g., "IPV4-UNICAST")
                                "afi_name": str,
                                "safi_name": str,
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

        # Align with other ISIS parsers: nest under isis["default"]["redistribute_routes"].
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
                "redistribute_routes", {}
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
                    "afi_name": afi_name,
                    "safi_name": safi_name,
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
                            "level_number": level_num,
                            "metric": state.get("metric", 0),
                        }

                        if "route-tag" in state:
                            level_entry["route_tag"] = state["route-tag"]

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
                            level_entry["source_identifier"] = identifier.replace(
                                "openconfig-policy-types:", ""
                            )
                        if "name" in source_state:
                            level_entry["source_name"] = source_state["name"]

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
                            Optional("level_capability"): str,
                            Optional("max_ecmp_paths"): int,
                            Optional("is_type"): str,
                            Optional("table_id"): int,
                            Optional("area_address"): list,
                            Optional("system_id"): str,
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
                    global_entry["level_capability"] = level_cap

                if "max-ecmp-paths" in state:
                    global_entry["max_ecmp_paths"] = state["max-ecmp-paths"]

                # ArcOS augments
                is_type_key = f"{ARCOS_ISIS_AUGMENTS}:is-type"
                if is_type_key in state:
                    is_type = state[is_type_key]
                    is_type = is_type.replace("arcos-isis-types:", "")
                    is_type = is_type.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                    global_entry["is_type"] = is_type

                table_id_key = f"{ARCOS_ISIS_AUGMENTS}:table-id"
                if table_id_key in state:
                    global_entry["table_id"] = state[table_id_key]

                area_addr_key = f"{ARCOS_ISIS_AUGMENTS}:area-address"
                if area_addr_key in state:
                    global_entry["area_address"] = state[area_addr_key]

                system_id_key = f"{ARCOS_ISIS_AUGMENTS}:system-id"
                if system_id_key in state:
                    global_entry["system_id"] = state[system_id_key]

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
    under ``isis[instance]['fast_reroute']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("fast_reroute"): {
                            Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                "afi_name": str,
                                "safi_name": str,
                                "prefixes": {
                                    Any(): {  # prefix string
                                        "prefix": str,
                                        "levels": {
                                            Any(): {  # level number as string
                                                "level_number": int,
                                                "reroute_type": str,
                                                "metric": int,
                                                "nexthop_address": str,
                                                "nexthop_interface": str,
                                                "flags": list,
                                                "last_updated_time": str,
                                                "origin_system_id": str,
                                                Optional("protection_types"): list,
                                                Optional("pq_node_system_id"): str,
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

        # Nest under isis["default"]["fast_reroute"].
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
            fast_dict: Dict[str, TypeAny] = ni_isis.setdefault("fast_reroute", {})

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
                    "afi_name": afi_name,
                    "safi_name": safi_name,
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
                            "level_number": level_num,
                            "reroute_type": state.get("reroute-type", ""),
                            "metric": state.get("metric", 0),
                            "nexthop_address": state.get("nexthop-address", ""),
                            "nexthop_interface": state.get("nexthop-interface", ""),
                            "flags": state.get("flags", []),
                            "last_updated_time": state.get("last-updated-time", ""),
                            "origin_system_id": state.get("origin-system-id", ""),
                        }

                        prot_types = state.get("protection-types", [])
                        if prot_types:
                            level_entry["protection_types"] = [
                                p.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                for p in prot_types
                            ]

                        pq_node = level.get("pq-node", {}).get("state", {})
                        if "system-id" in pq_node:
                            level_entry["pq_node_system_id"] = pq_node["system-id"]

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

    Nested under ``isis[instance]['flex_algo_fast_reroute']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("flex_algo_fast_reroute"): {
                            Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                "afi_name": str,
                                "safi_name": str,
                                "algorithms": {
                                    Any(): {  # flexible-algorithm id as string
                                        "id": int,
                                        "prefixes": {
                                            Any(): {  # prefix string
                                                "prefix": str,
                                                "levels": {
                                                    Any(): {  # level number as string
                                                        "level_number": int,
                                                        "reroute_type": str,
                                                        "metric": int,
                                                        "nexthop_address": str,
                                                        "nexthop_interface": str,
                                                        "flags": list,
                                                        "last_updated_time": str,
                                                        "origin_system_id": str,
                                                        Optional(
                                                            "protection_types"
                                                        ): list,
                                                        Optional(
                                                            "pq_node_system_id"
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

        # Nest under isis["default"]["flex_algo_fast_reroute"].
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
                "flex_algo_fast_reroute", {}
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
                    "afi_name": afi_name,
                    "safi_name": safi_name,
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
                                "level_number": level_num,
                                "reroute_type": state.get("reroute-type", ""),
                                "metric": state.get("metric", 0),
                                "nexthop_address": state.get("nexthop-address", ""),
                                "nexthop_interface": state.get("nexthop-interface", ""),
                                "flags": state.get("flags", []),
                                "last_updated_time": state.get("last-updated-time", ""),
                                "origin_system_id": state.get("origin-system-id", ""),
                            }

                            prot_types = state.get("protection-types", [])
                            if prot_types:
                                level_entry["protection_types"] = [
                                    p.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                    for p in prot_types
                                ]

                            pq_node = level.get("pq-node", {}).get("state", {})
                            if "system-id" in pq_node:
                                level_entry["pq_node_system_id"] = pq_node["system-id"]

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

    Nested under ``isis[instance]['flex_algo_routes']``.
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "isis": {
                    Any(): {  # protocol instance name
                        Optional("flex_algo_routes"): {
                            Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                                "afi_name": str,
                                "safi_name": str,
                                "algorithms": {
                                    Any(): {  # flexible-algorithm id as string
                                        "id": int,
                                        "routes": {
                                            Any(): {  # prefix
                                                "prefix": str,
                                                "best_level_number": int,
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

        # Nest under isis["default"]["flex_algo_routes"].
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
                "flex_algo_routes", {}
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
                    "afi_name": afi_name,
                    "safi_name": safi_name,
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
                            "best_level_number": state.get("best-level-number", 0),
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
                                    "level_number": level_num,
                                    "metric": level_state.get("metric", 0),
                                }

                                flags = level_state.get("flags", [])
                                if flags:
                                    level_entry["flags"] = [
                                        f.replace(f"{ARCOS_ISIS_AUGMENTS}:", "")
                                        for f in flags
                                    ]

                                if "next-hop-id" in level_state:
                                    level_entry["next_hop_id"] = str(
                                        level_state["next-hop-id"]
                                    )
                                if "prefix-origin-count" in level_state:
                                    level_entry["prefix_origin_count"] = level_state[
                                        "prefix-origin-count"
                                    ]
                                if "route-tag" in level_state:
                                    level_entry["route_tag"] = level_state["route-tag"]
                                if "last-updated-time" in level_state:
                                    level_entry["last_updated_time"] = level_state[
                                        "last-updated-time"
                                    ]

                                next_hops_obj = level.get("next-hops", {})
                                next_hop_list = next_hops_obj.get("next-hop", [])

                                if next_hop_list:
                                    level_entry["next_hops"] = []
                                    for nh in next_hop_list:
                                        nh_entry: Dict[str, TypeAny] = {}

                                        if "next-hop-address" in nh:
                                            nh_entry["next_hop_address"] = nh[
                                                "next-hop-address"
                                            ]

                                        if "outgoing-interface" in nh:
                                            nh_entry["outgoing_interface"] = nh[
                                                "outgoing-interface"
                                            ]

                                        nh_state = nh.get("state", {})
                                        if nh_state:
                                            if "tunnel-id" in nh_state:
                                                nh_entry["tunnel_id"] = nh_state[
                                                    "tunnel-id"
                                                ]
                                            if "backup" in nh_state:
                                                nh_entry["backup"] = nh_state["backup"]

                                        level_entry["next_hops"].append(nh_entry)

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
                            Optional("igp_ldp_sync_enabled"): bool,
                            Optional("label_db"): {
                                "state": {
                                    Optional("protocol_identifier"): str,
                                    Optional("protocol_name"): str,
                                    Optional("configured_blocks"): int,
                                    Optional("active_blocks"): int,
                                    Optional("active_usages"): int,
                                },
                                Optional("statistics"): {
                                    Optional("label_space"): int,
                                    Optional("labels"): int,
                                    Optional("allocs"): str,
                                    Optional("frees"): str,
                                    Optional("alloc_errors"): str,
                                    Optional("free_errors"): str,
                                },
                                Optional("usages"): {
                                    Any(): {  # usage type (ISIS_SRGB, ISIS_SRLB)
                                        "usage": str,
                                        Optional("blocks_count"): int,
                                        Optional("opaque_flags"): str,
                                        Optional("statistics"): {
                                            Optional("label_space"): int,
                                            Optional("labels"): int,
                                            Optional("allocs"): str,
                                            Optional("frees"): str,
                                            Optional("alloc_errors"): str,
                                            Optional("free_errors"): str,
                                        },
                                        Optional("blocks"): {
                                            Any(): {  # lower-bound as key
                                                "lower_bound": int,
                                                "upper_bound": int,
                                                Optional("block_name"): str,
                                                Optional("opaque_flags"): str,
                                                Optional("statistics"): {
                                                    Optional("label_space"): int,
                                                    Optional("labels"): int,
                                                    Optional("allocs"): str,
                                                    Optional("frees"): str,
                                                    Optional("alloc_errors"): str,
                                                    Optional("free_errors"): str,
                                                },
                                            }
                                        },
                                        Optional("labels"): {
                                            Any(): {  # label value as key
                                                "label": int,
                                                Optional("block_name"): str,
                                                Optional("label_key"): {
                                                    Optional("type"): str,
                                                    Optional("sub_type"): int,
                                                    Optional("table_id"): int,
                                                    Optional("ip_prefix"): str,
                                                    Optional("nh_address"): str,
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
                        mpls_entry["igp_ldp_sync_enabled"] = sync_state["enabled"]

                    # Label database
                    label_db = mpls.get("arcos-mpls:label-db", {})
                    if not label_db:
                        continue

                    mpls_entry["label_db"] = {"state": {}}

                    # Label DB state
                    db_state = label_db.get("state", {})
                    state_entry = mpls_entry["label_db"]["state"]

                    proto_id = db_state.get("protocol-identifier", "")
                    if proto_id:
                        state_entry["protocol_identifier"] = proto_id.replace(
                            "openconfig-policy-types:", ""
                        )

                    if "protocol-name" in db_state:
                        state_entry["protocol_name"] = db_state["protocol-name"]
                    if "configured-blocks" in db_state:
                        state_entry["configured_blocks"] = db_state["configured-blocks"]
                    if "active-blocks" in db_state:
                        state_entry["active_blocks"] = db_state["active-blocks"]
                    if "active-usages" in db_state:
                        state_entry["active_usages"] = db_state["active-usages"]

                    # Label DB statistics
                    db_stats = label_db.get("statistics", {})
                    if db_stats:
                        mpls_entry["label_db"]["statistics"] = self._parse_statistics(
                            db_stats
                        )

                    # Usages
                    usages_container = label_db.get("usages", {})
                    usage_list = usages_container.get("usage", [])

                    if usage_list:
                        mpls_entry["label_db"]["usages"] = {}
                        for usage in usage_list:
                            usage_key = usage.get("usage", "")
                            usage_key_clean = usage_key.replace("arcos-mpls:", "")

                            usage_entry: Dict[str, TypeAny] = {"usage": usage_key_clean}

                            usage_state = usage.get("state", {})
                            if "blocks" in usage_state:
                                usage_entry["blocks_count"] = usage_state["blocks"]
                            if "opaque-flags" in usage_state:
                                usage_entry["opaque_flags"] = usage_state["opaque-flags"]

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
                                        "lower_bound": lower,
                                        "upper_bound": block_state.get("upper-bound", 0),
                                    }

                                    if "block-name" in block_state:
                                        block_entry["block_name"] = block_state[
                                            "block-name"
                                        ]
                                    if "opaque-flags" in block_state:
                                        block_entry["opaque_flags"] = block_state[
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
                                        label_entry["block_name"] = label_state[
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
                                            key_entry["sub_type"] = key_state["sub-type"]
                                        if "table-id" in key_state:
                                            key_entry["table_id"] = key_state["table-id"]
                                        if "ip-prefix" in key_state:
                                            key_entry["ip_prefix"] = key_state[
                                                "ip-prefix"
                                            ]
                                        if "nh-address" in key_state:
                                            key_entry["nh_address"] = key_state[
                                                "nh-address"
                                            ]
                                        if "ifindex" in key_state:
                                            key_entry["ifindex"] = key_state["ifindex"]

                                        if key_entry:
                                            label_entry["label_key"] = key_entry

                                    usage_entry["labels"][str(label_val)] = label_entry

                            mpls_entry["label_db"]["usages"][usage_key_clean] = (
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
            result["label_space"] = stats["label-space"]
        if "labels" in stats:
            result["labels"] = stats["labels"]
        if "allocs" in stats:
            result["allocs"] = stats["allocs"]
        if "frees" in stats:
            result["frees"] = stats["frees"]
        if "alloc-errors" in stats:
            result["alloc_errors"] = stats["alloc-errors"]
        if "free-errors" in stats:
            result["free_errors"] = stats["free-errors"]
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
