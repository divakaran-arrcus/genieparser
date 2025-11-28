"""ArcOS ISIS parsers.

Parsers for Arrcus ArcOS ISIS OpenConfig-based JSON commands.

Initially this module provides adjacency and LSP database parsers,
mirroring the behavior of the local Arrcus pyATS implementation.
"""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional

from genie.libs.parser.arcos.constants import (
    ARCOS_ISIS_AUGMENTS,
    DEFAULT_INSTANCE,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust


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
        "isis": {
            Any(): {  # instance name
                Optional("neighbors"): {
                    Any(): {  # neighbor system-id
                        "interface": str,
                        "state": str,
                        Optional("holdtime"): int,
                        Optional("level"): str,
                        Optional("neighbor-ipv4-address"): str,
                        Optional("neighbor-ipv6-address"): str,
                        Optional("adjacency-type"): str,
                        Optional("up-time"): int,
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


class ShowIsisAdjacency(ShowIsisAdjacencySchema):
    """Parser for ArcOS ISIS adjacency command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * interface * level * adjacency [<adj_router>]
    """

    cli_command = (
        "show network-instance * protocol ISIS * interface * level * adjacency"
    )

    def cli(
        self,
        adj_router: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if adj_router:
                cmd += f" {adj_router}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Initialize return dictionary
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis_data = get_isis_data(parsed_json)
            interfaces_data = isis_data.get("interfaces", {}).get("interface", [])

            if not interfaces_data:
                return ret_dict

            neighbors_dict: Dict[str, TypeAny] = {}

            # Extract neighbors from each interface's adjacencies
            for intf in interfaces_data:
                intf_id = intf.get("interface-id")
                if not intf_id:
                    continue

                levels_data = intf.get("levels", {}).get("level", [])
                for level in levels_data:
                    adjacencies_data = level.get("adjacencies", {}).get(
                        "adjacency", []
                    )

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

                        # Up-time
                        up_time = adj_state.get("up-time")
                        if up_time is not None:
                            neighbor_entry["up-time"] = up_time

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
                            neighbor_entry[
                                "received-multi-topology-ids"
                            ] = recv_mt_ids

                        active_mt_ids = adj_state.get(
                            f"{ARCOS_ISIS_AUGMENTS}:active-multi-topology-ids"
                        )
                        if active_mt_ids:
                            neighbor_entry[
                                "active-multi-topology-ids"
                            ] = active_mt_ids

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
                                    neighbor_entry[
                                        "dynamic-delay-measurement"
                                    ] = ddm_info

                        neighbors_dict[sys_id] = neighbor_entry

            if neighbors_dict:
                ret_dict["isis"]["default"]["neighbors"] = neighbors_dict

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS neighbor data: %s", exc)

        return ret_dict


class ShowIsisLspSchema(MetaParser):
    """Schema for ArcOS ISIS LSP database JSON output."""

    schema = {
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
                        Optional("mt_ipv6_reachability"): dict,
                        Optional("attributes"): dict,
                    }
                }
            }
        }
    }


class ShowIsisLsp(ShowIsisLspSchema):
    """Parser for ArcOS ISIS LSP database (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * level * link-state-database [lsp <lsp_id>]
    """

    cli_command = "show network-instance * protocol ISIS * level * link-state-database"

    def cli(
        self,
        lsp_id: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if lsp_id:
                cmd += f" lsp {lsp_id}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis_data = get_isis_data(parsed_json)
            levels_data = isis_data.get("levels", {}).get("level", [])

            database_dict: Dict[str, TypeAny] = {}

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

                    update_time = state.get(
                        f"{ARCOS_ISIS_AUGMENTS}:last-update-time"
                    )
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
                                    tlv.get("nlpid", {})
                                    .get("state", {})
                                    .get("nlpid")
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
                                        loc_info: Dict[str, TypeAny] = {
                                            "locator": loc_state.get("locator"),
                                            "mt-id": loc_state.get("mt-id"),
                                            "metric": loc_state.get("metric"),
                                            "algorithm": loc_state.get("algorithm"),
                                        }
                                        if loc_state.get("flags"):
                                            loc_info["flags"] = loc_state["flags"]
                                        locators.append(loc_info)
                                    if locators:
                                        tlv_info["srv6-locators"] = locators

                            # Router capabilities
                            elif "ROUTER_CAPABILITY" in tlv_type:
                                cap_state = tlv.get("router-capabilities", {}).get(
                                    "capability", []
                                )
                                if cap_state:
                                    tlv_info["router-capabilities"] = cap_state[
                                        0
                                    ].get("state", {})

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
                                                pfx_info["prefix_len"] = int(
                                                    prefix_len
                                                )
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix_len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if up_down is not None:
                                            pfx_info["up_down"] = bool(up_down)

                                        # Optional flags from subTLV
                                        sub_tlvs = (
                                            pfx.get("subTLVs", {})
                                            .get("subTLVs", [])
                                        )
                                        for sub in sub_tlvs:
                                            stype = sub.get("subtlv-type", "")
                                            if "TLV135_PREFIX_FLAGS" in stype:
                                                flags_state = (
                                                    sub.get("flags", {})
                                                    .get("state", {})
                                                )
                                                flags = flags_state.get("flags")
                                                if flags is not None:
                                                    pfx_info["flags"] = flags
                                                break

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
                                                pfx_info["prefix_len"] = int(
                                                    prefix_len
                                                )
                                            except Exception:  # pragma: no cover
                                                pfx_info["prefix_len"] = prefix_len

                                        if metric is not None:
                                            pfx_info["metric"] = metric

                                        if mt_id is not None:
                                            pfx_info["mt-id"] = mt_id

                                        if up_down is not None:
                                            pfx_info["up_down"] = bool(up_down)

                                        mt6[prefix_str] = pfx_info

                        if tlv_info:
                            db_entry["tlvs"] = tlv_info

                    database_dict[lsp_id_val] = db_entry

            if database_dict:
                ret_dict["isis"]["default"]["database"] = database_dict

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing ISIS LSP data: %s", exc)

        return ret_dict


class ShowIsisInterfaceSchema(MetaParser):
    """Schema for ArcOS ISIS per-interface operational state and counters."""

    schema = {
        "isis": {
            Any(): {  # instance name
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
                        Optional("levels"): dict,
                        Optional("adjacencies"): dict,
                    }
                }
            }
        }
    }


class ShowIsisInterface(ShowIsisInterfaceSchema):
    """Parser for ArcOS ISIS interface command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * interface [<interface>]
    """

    cli_command = "show network-instance * protocol ISIS * interface"

    def cli(
        self,
        interface: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if interface:
                cmd += f" {interface}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis_data = get_isis_data(parsed_json)
            interfaces_data = isis_data.get("interfaces", {}).get("interface", [])

            if not interfaces_data:
                return ret_dict

            interfaces_dict: Dict[str, TypeAny] = {}

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
                            tb_state = tiebreaker_data.get(tb_type, {}).get(
                                "state", {}
                            )
                            if "priority" in tb_state:
                                tiebreakers[tb_type] = {
                                    "priority": tb_state["priority"]
                                }
                        if tiebreakers:
                            frr_info["tiebreakers"] = tiebreakers

                    if frr_info:
                        intf_entry["fast-reroute"] = frr_info

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
                                    adj_entry["neighbor-ipv4-address"] = (
                                        neighbor_ipv4
                                    )

                                neighbor_ipv6 = adj_state.get("neighbor-ipv6-address")
                                if neighbor_ipv6:
                                    adj_entry["neighbor-ipv6-address"] = (
                                        neighbor_ipv6
                                    )

                                hold_time = adj_state.get("remaining-hold-time")
                                if hold_time is not None:
                                    adj_entry["remaining-hold-time"] = hold_time

                                up_time = adj_state.get("up-time")
                                if up_time is not None:
                                    adj_entry["up-time"] = up_time

                                local_cid = adj_state.get(
                                    "local-extended-circuit-id"
                                )
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

                                usable = adj_state.get(
                                    f"{ARCOS_ISIS_AUGMENTS}:usable"
                                )
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
                ret_dict["isis"]["default"]["interfaces"] = interfaces_dict

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
        "isis": {
            Any(): {  # instance name
                Optional("config"): {
                    Optional("global"): {
                        Optional("net"): list,
                        Optional("level_capability"): str,
                        Optional("max_ecmp_paths"): int,
                    },
                    Optional("afi_safi"): {
                        Any(): {  # AFI-SAFI key like "IPV6-UNICAST"
                            "afi_name": str,
                            "safi_name": str,
                            "enabled": bool,
                            Optional("multi_topology_enabled"): bool,
                        }
                    },
                    Optional("interfaces"): {
                        Any(): {  # interface name
                            "interface_id": str,
                            "enabled": bool,
                            Optional("network_type"): str,
                            Optional("afi_safi"): {
                                Any(): {  # AFI-SAFI key
                                    "afi_name": str,
                                    "safi_name": str,
                                    "enabled": bool,
                                }
                            },
                            Optional("levels"): {
                                Any(): {  # level number
                                    "level_number": int,
                                    "enabled": bool,
                                }
                            },
                        }
                    },
                }
            }
        }
    }


class ShowIsisConfig(ShowIsisConfigSchema):
    """Parser for ArcOS ISIS running configuration (JSON format).

    Command pattern (before JSON pipe)::

        show running-config network-instance * protocol ISIS [<instance>]
    """

    cli_command = "show running-config network-instance * protocol ISIS"

    def cli(
        self,
        instance: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if instance:
                cmd += f" {instance}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["config"].
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            cfg_root = (
                ret_dict.setdefault("isis", {})
                .setdefault("default", {})
                .setdefault("config", {})
            )

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
                            intf_entry["afi_safi"][af_key] = {
                                "afi_name": afi_name,
                                "safi_name": safi_name,
                                "enabled": af_config.get("enabled", False),
                            }

                    intf_levels = intf.get("levels", {})
                    level_list = intf_levels.get("level", [])
                    if level_list:
                        intf_entry["levels"] = {}
                        for level in level_list:
                            level_num = level.get("level-number")
                            if level_num is not None:
                                level_config = level.get("config", {})
                                intf_entry["levels"][str(level_num)] = {
                                    "level_number": level_num,
                                    "enabled": level_config.get("enabled", False),
                                }

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
        "isis": {
            Any(): {  # instance name
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


class ShowIsisRoute(ShowIsisRouteSchema):
    """Parser for ArcOS ISIS routes command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * global af * UNICAST route [<prefix>]
    """

    cli_command = "show network-instance * protocol ISIS * global af * UNICAST route"

    def cli(
        self,
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Align with other ISIS parsers: nest under isis["default"]["routes"].
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            routes_root = ret_dict.setdefault("isis", {}).setdefault("default", {})
            routes_dict: Dict[str, TypeAny] = routes_root.setdefault("routes", {})

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
        "isis": {
            Any(): {  # instance name
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


class ShowIsisRedistributeRoute(ShowIsisRedistributeRouteSchema):
    """Parser for ArcOS ISIS redistribute routes command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * global af * UNICAST redistribute-route [<prefix>]
    """

    cli_command = (
        "show network-instance * protocol ISIS * global af * UNICAST redistribute-route"
    )

    def cli(
        self,
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Align with other ISIS parsers: nest under isis["default"]["redistribute_routes"].
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            redist_root = ret_dict.setdefault("isis", {}).setdefault("default", {})
            redist_dict: Dict[str, TypeAny] = redist_root.setdefault(
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

                redist_obj = af.get(
                    f"{ARCOS_ISIS_AUGMENTS}:redistribute-routes", {}
                )
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

                    route_entry: Dict[str, TypeAny] = {"prefix": prefix_val, "levels": {}}

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
        "isis_global": {
            Any(): {  # instance name (e.g., 'default')
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


class ShowIsisGlobal(ShowIsisGlobalSchema):
    """Parser for ArcOS ISIS global state command (JSON format).

    Supports::

        show network-instance * protocol ISIS * global state | display json | nomore
    """

    cli_command = "show network-instance * protocol ISIS * global state"

    def cli(self, output: TypeOptional[str] = None) -> TypeAny:
        if output is None:
            cmd = self.cli_command
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Initialize return dictionary
        ret_dict: Dict[str, TypeAny] = {"isis_global": {}}

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
                ret_dict["isis_global"][DEFAULT_INSTANCE] = global_entry

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
        "isis": {
            Any(): {  # instance name
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


class ShowIsisFastReroute(ShowIsisFastRerouteSchema):
    """Parser for ArcOS ISIS fast-reroute command (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * global af * UNICAST fast-reroute [<prefix>]
    """

    cli_command = (
        "show network-instance * protocol ISIS * global af * UNICAST fast-reroute"
    )

    def cli(
        self,
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["fast_reroute"].
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            fast_root = ret_dict.setdefault("isis", {}).setdefault("default", {})
            fast_dict: Dict[str, TypeAny] = fast_root.setdefault("fast_reroute", {})

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
        "isis": {
            Any(): {  # instance name
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
                                                Optional("protection_types"): list,
                                                Optional("pq_node_system_id"): str,
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


class ShowIsisFlexAlgoFastReroute(ShowIsisFlexAlgoFastRerouteSchema):
    """Parser for ArcOS ISIS flexible-algorithm fast-reroute (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * global af * UNICAST flexible-algorithm * fast-reroute [<prefix>]
    """

    cli_command = (
        "show network-instance * protocol ISIS * global af * UNICAST "
        "flexible-algorithm * fast-reroute"
    )

    def cli(
        self,
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["flex_algo_fast_reroute"].
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            flex_frr_root = ret_dict.setdefault("isis", {}).setdefault("default", {})
            flex_frr_dict: Dict[str, TypeAny] = flex_frr_root.setdefault(
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

                fa_container = af.get(
                    f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithms", {}
                )
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
                                "last_updated_time": state.get(
                                    "last-updated-time", ""
                                ),
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
                                level_entry["pq_node_system_id"] = pq_node[
                                    "system-id"
                                ]

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
        "isis": {
            Any(): {  # instance name
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


class ShowIsisFlexAlgoRoute(ShowIsisFlexAlgoRouteSchema):
    """Parser for ArcOS ISIS flexible-algorithm routes (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance * protocol ISIS * global af * UNICAST flexible-algorithm * route [<prefix>]
    """

    cli_command = (
        "show network-instance * protocol ISIS * global af * UNICAST "
        "flexible-algorithm * route"
    )

    def cli(
        self,
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            cmd = f"{self.cli_command}"
            if prefix:
                cmd += f" {prefix}"
            output = self.device.execute(f"{cmd} | display json | nomore")

        # Nest under isis["default"]["flex_algo_routes"].
        ret_dict: Dict[str, TypeAny] = {"isis": {"default": {}}}

        try:
            parsed_json = load_json_robust(output)

            isis = get_isis_data(parsed_json)
            if not isis:
                return ret_dict

            global_config = isis.get("global", {})
            afi_safi = global_config.get("afi-safi", {})
            af_list = afi_safi.get("af", [])

            flex_routes_root = ret_dict.setdefault("isis", {}).setdefault(
                "default", {}
            )
            flex_routes_dict: Dict[str, TypeAny] = flex_routes_root.setdefault(
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

                fa_container = af.get(
                    f"{ARCOS_ISIS_AUGMENTS}:flexible-algorithms", {}
                )
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
                                                nh_entry["backup"] = nh_state[
                                                    "backup"
                                                ]

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
            logger.warning(
                "Error parsing ISIS flexible-algorithm routes data: %s", exc
            )

        return ret_dict
