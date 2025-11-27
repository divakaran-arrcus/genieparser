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


logger = logging.getLogger(__name__)


def _load_json_robust(output: TypeAny) -> Dict:
    """Load JSON from CLI output or a pre-decoded dict.

    Some devices or helper layers may return a Python dict instead of a raw
    JSON string. CLI output may also contain prompts or banners around the
    JSON. This helper normalizes those cases.
    """

    if isinstance(output, dict):
        return output

    if not isinstance(output, str):
        output = str(output)

    start = output.find("{")
    end = output.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = output[start : end + 1]
    else:
        json_str = output

    return json.loads(json_str)


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
            parsed_json = _load_json_robust(output)

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
            parsed_json = _load_json_robust(output)

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
