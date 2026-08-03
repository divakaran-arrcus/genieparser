"""show_ospf.py

ArcOS parsers for the following show commands:
    * show network-instance {ni} protocol OSPF {instance} global state
    * show network-instance {ni} protocol OSPF {instance} area {area} interface * neighbor
    * show network-instance {ni} protocol OSPF {instance} area state
    * show network-instance {ni} protocol OSPF {instance} area {area} interface state
    * show network-instance {ni} protocol OSPF {instance} global spf throttle
    * show network-instance {ni} protocol OSPF {instance} area {area} lsdb
    * show running-config network-instance {ni} protocol OSPF {instance}
    * show network-instance {ni} protocol OSPF {instance} global rib prefix
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


def _navigate_to_ospf(parsed: Dict) -> Dict:
    """Navigate to the OSPF container."""
    data = parsed.get("data", {})
    ni_container = data.get("openconfig-network-instance:network-instances", {})
    ni_list = ni_container.get("network-instance", [])
    if not ni_list:
        return {}
    ni = ni_list[0]
    protocols = ni.get("protocols", {}).get("protocol", [])
    for p in protocols:
        if "arcos-ospf:ospfv2" in p:
            return p["arcos-ospf:ospfv2"]
    return {}


# =====================================================================
# ShowOspfGlobal
# =====================================================================

class ShowOspfGlobalSchema(MetaParser):
    schema = {
        "router-id": str,
        Optional("log-adjacency-changes"): str,
        Optional("max-ecmp-paths"): int,
        Optional("abr-router"): bool,
        Optional("asbr-router"): bool,
        Optional("area-count"): int,
        Optional("neighbor-count"): int,
        Optional("full-neighbor-count"): int,
        Optional("up-interface-count"): int,
        Optional("route-preference"): {
            Optional("intra-area"): int,
            Optional("inter-area"): int,
            Optional("external"): int,
        },
        Optional("max-lsa"): {
            Optional("lsa-limit"): int,
            Optional("warning-threshold"): int,
            Optional("state"): str,
        },
        Optional("maintenance-mode"): {
            Optional("state"): str,
            Optional("trigger"): str,
        },
    }


class ShowOspfGlobal(ShowOspfGlobalSchema):
    """Parser for OSPF global state."""

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} global state"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"global state | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)
        global_data = ospf.get("global", {})
        state = global_data.get("state", {})

        if not state:
            raise SchemaEmptyParserError("No OSPF global state found")

        result = {
            "router-id": state.get("router-id", ""),
        }

        for k in ("log-adjacency-changes", "max-ecmp-paths",
                   "abr-router", "asbr-router", "area-count",
                   "neighbor-count", "full-neighbor-count",
                   "up-interface-count"):
            if k in state:
                result[k] = state[k]

        # Optional sub-dicts. Try both layouts:
        #   global.{field}.state.* (nested OpenConfig)
        #   state.{field}.*        (flat under top-level state)
        for field, keys in (
            ("route-preference", ("intra-area", "inter-area", "external")),
            ("max-lsa", ("lsa-limit", "warning-threshold", "state")),
            ("maintenance-mode", ("state", "trigger")),
        ):
            src = (global_data.get(field, {}) or {}).get("state", {}) \
                or state.get(field, {}) or {}
            sub = {k: src[k] for k in keys if k in src}
            if sub:
                result[field] = sub

        return result


# =====================================================================
# ShowOspfNeighbor
# =====================================================================

class ShowOspfNeighborSchema(MetaParser):
    schema = {
        "neighbors": {
            Any(): {  # "area:interface:router-id" key
                "area": int,
                "interface": str,
                "neighbor-router-id": str,
                Optional("neighbor-ip-address"): str,
                Optional("adjacency-state"): str,
                Optional("priority"): int,
                Optional("optional-capabilities"): str,
                Optional("database-exchange-mtu"): int,
                Optional("last-established-exstart-timestamp"): str,
                Optional("last-established-full-timestamp"): str,
                Optional("next-dead-timer-expiry-timestamp"): str,
                Optional("next-dead-timer-expiry-remaining-time"): int,
            }
        }
    }


class ShowOspfNeighbor(ShowOspfNeighborSchema):
    """Parser for OSPF neighbors (per-area)."""

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} "
        "area {area} interface * neighbor"
    )

    def cli(self, ni="default", instance="default", area="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"area {area} interface * neighbor | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        areas_container = ospf.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPF neighbor data found")

        result = {"neighbors": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            intfs = area_entry.get("interfaces", {}).get("interface", [])

            for intf in intfs:
                intf_id = intf.get("id")
                if not intf_id:
                    continue

                nbrs = intf.get("neighbors", {}).get("neighbor", [])
                for nbr in nbrs:
                    rid = nbr.get("neighbor-router-id")
                    if not rid:
                        continue

                    state = nbr.get("state", {})
                    key = f"{area_id}:{intf_id}:{rid}"

                    entry = {
                        "area": area_id,
                        "interface": intf_id,
                        "neighbor-router-id": rid,
                    }

                    if "neighbor-ip-address" in state:
                        entry["neighbor-ip-address"] = state["neighbor-ip-address"]

                    adj = state.get("adjacency-state", "")
                    if adj:
                        # Strip prefix: "arcos-ospf-types:NEIGHBOR_FULL" → "NEIGHBOR_FULL"
                        entry["adjacency-state"] = adj.split(":")[-1] if ":" in adj else adj

                    if "priority" in state:
                        entry["priority"] = state["priority"]

                    for extra_k in ("optional-capabilities",
                                     "database-exchange-mtu",
                                     "last-established-exstart-timestamp",
                                     "last-established-full-timestamp",
                                     "next-dead-timer-expiry-timestamp",
                                     "next-dead-timer-expiry-remaining-time"):
                        if extra_k in state:
                            entry[extra_k] = state[extra_k]

                    result["neighbors"][key] = entry

        if not result["neighbors"]:
            raise SchemaEmptyParserError("No OSPF neighbors found")

        return result


# =====================================================================
# Prefix stripping for OSPF types
# =====================================================================

_OSPF_VALUE_PREFIXES = [
    "arcos-ospf-types:",
    "openconfig-policy-types:",
]


def _strip_ospf_value(value: str) -> str:
    """Strip known OSPF namespace prefixes from a value string."""
    if not isinstance(value, str):
        return value
    for prefix in _OSPF_VALUE_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


# =====================================================================
# ShowOspfArea
# =====================================================================

class ShowOspfAreaSchema(MetaParser):
    """Schema for OSPF per-area operational state."""

    schema = {
        "areas": {
            Any(): {  # area ID as str
                Optional("identifier"): int,
                Optional("area-type"): str,
                Optional("advertise-summary-lsas"): bool,
                Optional("stub-default-cost"): int,
                Optional("configured-interface-count"): int,
                Optional("up-interface-count"): int,
                Optional("neighbor-count"): int,
                Optional("exchange-neighbor-count"): int,
                Optional("loading-neighbor-count"): int,
                Optional("full-neighbor-count"): int,
            }
        }
    }


class ShowOspfArea(ShowOspfAreaSchema):
    """Parser for OSPF area state.

    Command::

        show network-instance {ni} protocol OSPF {instance} area state
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} area state"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"area state | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        areas_container = ospf.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPF area data found")

        result = {"areas": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            state = area_entry.get("state", {})

            if not state:
                continue

            entry: Dict[str, TypeAny] = {}

            if "identifier" in state:
                entry["identifier"] = state["identifier"]

            area_type = state.get("area-type")
            if area_type:
                entry["area-type"] = _strip_ospf_value(area_type)

            for k in ("advertise-summary-lsas", "stub-default-cost",
                       "configured-interface-count", "up-interface-count",
                       "neighbor-count", "exchange-neighbor-count",
                       "loading-neighbor-count", "full-neighbor-count"):
                if k in state:
                    entry[k] = state[k]

            if entry:
                result["areas"][str(area_id)] = entry

        if not result["areas"]:
            raise SchemaEmptyParserError("No OSPF area data found")

        return result


# =====================================================================
# ShowOspfInterface
# =====================================================================

class ShowOspfInterfaceSchema(MetaParser):
    """Schema for OSPF per-interface operational state."""

    schema = {
        "areas": {
            Any(): {  # area ID as str
                "interfaces": {
                    Any(): {  # interface name
                        Optional("id"): str,
                        Optional("network-type"): str,
                        Optional("priority"): int,
                        Optional("metric"): int,
                        Optional("passive"): bool,
                        Optional("ignore-mtu"): bool,
                        Optional("interface-up"): bool,
                        Optional("interface-state"): str,
                        Optional("local-ip-address"): str,
                        Optional("mtu"): int,
                        Optional("speed"): Or(str, int),
                        Optional("neighbor-count"): int,
                        Optional("exchange-neighbor-count"): int,
                        Optional("loading-neighbor-count"): int,
                        Optional("full-neighbor-count"): int,
                        Optional("authentication"): {
                            Optional("auth-type"): str,
                        },
                    }
                }
            }
        }
    }


class ShowOspfInterface(ShowOspfInterfaceSchema):
    """Parser for OSPF interface state.

    Command::

        show network-instance {ni} protocol OSPF {instance}
            area {area} interface state
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} "
        "area {area} interface state"
    )

    def cli(self, ni="default", instance="default", area="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"area {area} interface state | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        areas_container = ospf.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPF interface data found")

        result = {"areas": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            intfs = area_entry.get("interfaces", {}).get("interface", [])

            if not intfs:
                continue

            interfaces_dict: Dict[str, TypeAny] = {}

            for intf in intfs:
                intf_id = intf.get("id")
                if not intf_id:
                    continue

                state = intf.get("state", {})
                entry: Dict[str, TypeAny] = {}

                if "id" in state:
                    entry["id"] = state["id"]

                network_type = state.get("network-type")
                if network_type:
                    entry["network-type"] = _strip_ospf_value(network_type)

                intf_state = state.get("interface-state")
                if intf_state:
                    entry["interface-state"] = _strip_ospf_value(intf_state)

                for k in ("priority", "metric", "passive", "ignore-mtu",
                           "interface-up", "local-ip-address", "mtu",
                           "speed", "neighbor-count",
                           "exchange-neighbor-count",
                           "loading-neighbor-count",
                           "full-neighbor-count"):
                    if k in state:
                        entry[k] = state[k]

                # Authentication. arcOS may expose this either nested
                # (intf.authentication.state.auth-type) or flat
                # (state.authentication.auth-type).
                auth_src = (intf.get("authentication", {}) or {}).get(
                    "state", {}
                ) or state.get("authentication", {}) or {}
                auth_type = auth_src.get("auth-type")
                if auth_type:
                    entry["authentication"] = {
                        "auth-type": _strip_ospf_value(auth_type),
                    }

                if entry:
                    interfaces_dict[intf_id] = entry

            if interfaces_dict:
                result["areas"][str(area_id)] = {
                    "interfaces": interfaces_dict
                }

        if not result["areas"]:
            raise SchemaEmptyParserError("No OSPF interface data found")

        return result


# =====================================================================
# ShowOspfSpfThrottle
# =====================================================================

class ShowOspfSpfThrottleSchema(MetaParser):
    """Schema for OSPF SPF throttle timers."""

    schema = {
        Optional("spf-initial-delay"): int,
        Optional("spf-short-delay"): int,
        Optional("spf-long-delay"): int,
        Optional("time-to-learn-interval"): int,
        Optional("holddown-interval"): int,
    }


class ShowOspfSpfThrottle(ShowOspfSpfThrottleSchema):
    """Parser for OSPF SPF throttle timers.

    Command::

        show network-instance {ni} protocol OSPF {instance}
            global spf throttle
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} "
        "global spf throttle"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"global spf throttle | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        timers = (
            ospf.get("global", {})
            .get("spf", {})
            .get("throttle", {})
            .get("timers", {})
            .get("state", {})
        )

        if not timers:
            raise SchemaEmptyParserError("No OSPF SPF throttle data found")

        result: Dict[str, TypeAny] = {}

        for k in ("spf-initial-delay", "spf-short-delay", "spf-long-delay",
                   "time-to-learn-interval", "holddown-interval"):
            if k in timers:
                result[k] = timers[k]

        if not result:
            raise SchemaEmptyParserError("No OSPF SPF throttle data found")

        return result


# =====================================================================
# ShowOspfLsdb
# =====================================================================

class ShowOspfLsdbSchema(MetaParser):
    """Schema for OSPF LSDB (Link-State Database)."""

    schema = {
        "areas": {
            Any(): {  # area ID as str
                Optional("lsa-types"): {
                    Any(): {  # LSA type (e.g., "ROUTER_LSA")
                        Optional("type"): str,
                        Optional("lsas"): {
                            Any(): {  # "link-state-id:adv-router" key
                                Optional("link-state-id"): str,
                                Optional("advertising-router"): str,
                                Optional("sequence-number"): str,
                                Optional("checksum"): int,
                                Optional("age"): int,
                                # Router LSA body
                                Optional("router-lsa"): {
                                    Optional("flags"): str,
                                    Optional("num-links"): int,
                                    Optional("links"): {
                                        Any(): {  # link index
                                            Optional("type"): str,
                                            Optional("link-id"): str,
                                            Optional("link-data"): str,
                                            Optional("metric"): int,
                                        }
                                    },
                                },
                                # Summary LSA body
                                Optional("summary-lsa"): {
                                    Optional("network-mask"): int,
                                    Optional("metric"): int,
                                },
                            }
                        },
                    }
                }
            }
        }
    }


class ShowOspfLsdb(ShowOspfLsdbSchema):
    """Parser for OSPF LSDB.

    Command::

        show network-instance {ni} protocol OSPF {instance}
            area {area} lsdb
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} "
        "area {area} lsdb"
    )

    def cli(self, ni="default", instance="default", area="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"area {area} lsdb | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        areas_container = ospf.get("areas", {})
        area_list = areas_container.get("area", [])

        if not area_list:
            raise SchemaEmptyParserError("No OSPF LSDB data found")

        result = {"areas": {}}

        for area_entry in area_list:
            area_id = area_entry.get("identifier", 0)
            lsdb = area_entry.get("arcos-ospfv2:lsdb", {})
            lsa_types_container = lsdb.get("lsa-types", {})
            lsa_type_list = lsa_types_container.get("lsa-type", [])

            if not lsa_type_list:
                continue

            lsa_types_dict: Dict[str, TypeAny] = {}

            for lsa_type_entry in lsa_type_list:
                raw_type = lsa_type_entry.get("type", "")
                lsa_type_name = _strip_ospf_value(raw_type)

                type_dict: Dict[str, TypeAny] = {"type": lsa_type_name}

                lsa_list = (
                    lsa_type_entry.get("lsas", {}).get("lsa", [])
                )
                if not lsa_list:
                    lsa_types_dict[lsa_type_name] = type_dict
                    continue

                lsas_dict: Dict[str, TypeAny] = {}

                for lsa in lsa_list:
                    lsa_id = lsa.get("link-state-id", "")
                    adv_rtr = lsa.get("advertising-router", "")
                    lsa_key = f"{lsa_id}:{adv_rtr}"

                    lsa_entry: Dict[str, TypeAny] = {}

                    # Header from state{}
                    state = lsa.get("state", {})
                    for hk in ("link-state-id", "advertising-router",
                               "sequence-number", "checksum", "age"):
                        if hk in state:
                            lsa_entry[hk] = state[hk]

                    # Router LSA body
                    rlsa = lsa.get("router-lsa", {}).get("state", {})
                    if rlsa:
                        rlsa_entry: Dict[str, TypeAny] = {}

                        # Flags as string: V/E/B
                        flags_parts = []
                        if rlsa.get("v-bit"):
                            flags_parts.append("V")
                        if rlsa.get("e-bit"):
                            flags_parts.append("E")
                        if rlsa.get("b-bit"):
                            flags_parts.append("B")
                        if flags_parts:
                            rlsa_entry["flags"] = " ".join(flags_parts)

                        num_links = rlsa.get("number-links")
                        if num_links is not None:
                            rlsa_entry["num-links"] = num_links

                        links = rlsa.get("links", {}).get("link", [])
                        if links:
                            links_dict: Dict[str, TypeAny] = {}
                            for idx, link in enumerate(links):
                                link_entry: Dict[str, TypeAny] = {}
                                link_type = link.get("type")
                                if link_type:
                                    link_entry["type"] = (
                                        _strip_ospf_value(link_type)
                                    )
                                for lk in ("link-id", "link-data",
                                           "metric"):
                                    if lk in link:
                                        link_entry[lk] = link[lk]
                                if link_entry:
                                    links_dict[str(idx)] = link_entry
                            if links_dict:
                                rlsa_entry["links"] = links_dict

                        if rlsa_entry:
                            lsa_entry["router-lsa"] = rlsa_entry

                    # Summary LSA body
                    slsa = lsa.get("summary-lsa", {}).get("state", {})
                    if slsa:
                        slsa_entry: Dict[str, TypeAny] = {}
                        if "network-mask" in slsa:
                            slsa_entry["network-mask"] = slsa[
                                "network-mask"
                            ]
                        if "metric" in slsa:
                            slsa_entry["metric"] = slsa["metric"]
                        if slsa_entry:
                            lsa_entry["summary-lsa"] = slsa_entry

                    if lsa_entry:
                        lsas_dict[lsa_key] = lsa_entry

                if lsas_dict:
                    type_dict["lsas"] = lsas_dict

                lsa_types_dict[lsa_type_name] = type_dict

            if lsa_types_dict:
                result["areas"][str(area_id)] = {
                    "lsa-types": lsa_types_dict
                }

        if not result["areas"]:
            raise SchemaEmptyParserError("No OSPF LSDB data found")

        return result


# =====================================================================
# ShowOspfRunningConfig
# =====================================================================

class ShowOspfRunningConfigSchema(MetaParser):
    """Schema for OSPF running configuration."""

    schema = {
        Optional("global"): {
            Optional("router-id"): str,
            Optional("route-preference"): {
                Optional("intra-area"): int,
                Optional("inter-area"): int,
                Optional("external"): int,
            },
        },
        Optional("areas"): {
            Any(): {  # area ID as str
                Optional("identifier"): int,
                Optional("area-type"): str,
                Optional("stub-default-cost"): int,
                Optional("interfaces"): {
                    Any(): {  # interface name
                        Optional("id"): str,
                        Optional("network-type"): str,
                        Optional("hello-interval"): int,
                        Optional("dead-interval"): int,
                    }
                },
            }
        },
    }


class ShowOspfRunningConfig(ShowOspfRunningConfigSchema):
    """Parser for OSPF running configuration.

    Command::

        show running-config network-instance {ni} protocol OSPF {instance}
    """

    cli_command = (
        "show running-config network-instance {ni} protocol OSPF {instance}"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show running-config network-instance {ni} "
                f"protocol OSPF {instance} | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        if not ospf:
            raise SchemaEmptyParserError(
                "No OSPF running configuration found"
            )

        result: Dict[str, TypeAny] = {}

        # Global config (flatten config{})
        global_data = ospf.get("global", {})
        if global_data:
            global_entry: Dict[str, TypeAny] = {}

            cfg = global_data.get("config", {})
            rid = cfg.get("router-id")
            if rid:
                global_entry["router-id"] = rid

            rp = global_data.get("route-preference", {}).get("config", {})
            if rp:
                rp_entry: Dict[str, TypeAny] = {}
                for k in ("intra-area", "inter-area", "external"):
                    if k in rp:
                        rp_entry[k] = rp[k]
                if rp_entry:
                    global_entry["route-preference"] = rp_entry

            if global_entry:
                result["global"] = global_entry

        # Areas (flatten config{} at area and interface levels)
        areas_container = ospf.get("areas", {})
        area_list = areas_container.get("area", [])

        if area_list:
            areas_dict: Dict[str, TypeAny] = {}

            for area_entry in area_list:
                area_id = area_entry.get("identifier", 0)
                area_cfg = area_entry.get("config", {})

                entry: Dict[str, TypeAny] = {}

                if "identifier" in area_cfg:
                    entry["identifier"] = area_cfg["identifier"]

                area_type = area_cfg.get("area-type")
                if area_type:
                    entry["area-type"] = area_type

                stub_cost = area_cfg.get("stub-default-cost")
                if stub_cost is not None:
                    entry["stub-default-cost"] = stub_cost

                # Interfaces (flatten config{} + timers.config{})
                intfs = area_entry.get("interfaces", {}).get(
                    "interface", []
                )
                if intfs:
                    intfs_dict: Dict[str, TypeAny] = {}
                    for intf in intfs:
                        intf_id = intf.get("id")
                        if not intf_id:
                            continue

                        intf_entry: Dict[str, TypeAny] = {}
                        intf_cfg = intf.get("config", {})

                        if "id" in intf_cfg:
                            intf_entry["id"] = intf_cfg["id"]

                        net_type = intf_cfg.get("network-type")
                        if net_type:
                            intf_entry["network-type"] = (
                                _strip_ospf_value(net_type)
                            )

                        timers_cfg = intf.get("timers", {}).get(
                            "config", {}
                        )
                        for tk in ("hello-interval", "dead-interval"):
                            if tk in timers_cfg:
                                intf_entry[tk] = timers_cfg[tk]

                        if intf_entry:
                            intfs_dict[intf_id] = intf_entry

                    if intfs_dict:
                        entry["interfaces"] = intfs_dict

                if entry:
                    areas_dict[str(area_id)] = entry

            if areas_dict:
                result["areas"] = areas_dict

        if not result:
            raise SchemaEmptyParserError(
                "No OSPF running configuration found"
            )

        return result


# =====================================================================
# ShowOspfGlobalRib
# =====================================================================

# Map raw arcos-ospf-types path-type values to friendly route-type strings.
# Keys are the un-prefixed values (after _strip_ospf_value), values are
# the canonical route-type strings consumed by ``get_ospf_route``.
_OSPF_PATH_TYPE_MAP = {
    "OSPF_INTRA_AREA_CONNECTED_ROUTE": "intra-area-connected",
    "OSPF_INTRA_AREA_ROUTE": "intra-area",
    "OSPF_INTER_AREA_ROUTE": "inter-area",
    "OSPF_EXTERNAL_TYPE1_REDIST_ROUTE": "external-type-1",
    "OSPF_EXTERNAL_TYPE2_REDIST_ROUTE": "external-type-2",
    "OSPF_EXTERNAL_TYPE1_ROUTE": "external-type-1",
    "OSPF_EXTERNAL_TYPE2_ROUTE": "external-type-2",
}


class ShowOspfGlobalRibSchema(MetaParser):
    """Schema for OSPF Global RIB prefix output."""

    schema = {
        "routes": {
            Any(): {  # prefix string, e.g. "4.4.4.4/32"
                "prefix": str,
                Optional("path-count"): int,
                Optional("route-flags"): list,
                Optional("path-type"): str,         # canonical route-type
                Optional("raw-path-type"): str,     # full enum from device
                Optional("area"): str,
                Optional("metric"): int,
                Optional("path-flags"): list,
                Optional("received-lsa"): {
                    Optional("lsa-type"): str,
                    Optional("link-state-id"): str,
                    Optional("advertising-router"): str,
                },
                Optional("self-originated-lsa"): {
                    Optional("lsa-type"): str,
                    Optional("link-state-id"): str,
                    Optional("advertising-router"): str,
                },
                Optional("nexthop-set"): {
                    Optional("nexthop-set-id"): int,
                    Optional("nexthop-count"): int,
                    Optional("reference-count"): int,
                },
                # next-hops is a list of {interface: str, address: str};
                # declared as plain ``list`` because the metaparser
                # schemaengine does not directly support per-element dict
                # schemas inside lists.
                Optional("next-hops"): list,
            }
        }
    }


class ShowOspfGlobalRib(ShowOspfGlobalRibSchema):
    """Parser for OSPF Global RIB prefix output.

    Command::

        show network-instance {ni} protocol OSPF {instance} global rib prefix
    """

    cli_command = (
        "show network-instance {ni} protocol OSPF {instance} global rib prefix"
    )

    def cli(self, ni: str = "default", instance: str = "default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol OSPF {instance} "
                f"global rib prefix | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("arcos OSPF: empty output")
        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)

        rib = ospf.get("global", {}).get("rib", {})
        prefixes_container = rib.get("prefixes", {})
        prefix_list = prefixes_container.get("prefix", [])

        if not prefix_list:
            raise SchemaEmptyParserError("No OSPF RIB prefixes found")

        routes: Dict[str, Dict[str, TypeAny]] = {}

        for entry in prefix_list:
            key = entry.get("prefix-key") or \
                entry.get("prefix-identifier", {}).get("prefix-key")
            if not key:
                continue

            route: Dict[str, TypeAny] = {"prefix": key}

            state = entry.get("state", {}) or {}
            if "path-count" in state:
                route["path-count"] = state["path-count"]
            if "route-flags" in state:
                route["route-flags"] = [
                    _strip_ospf_value(rf) for rf in state["route-flags"]
                ]

            bestpath = entry.get("bestpath", {}) or {}

            raw_pt = bestpath.get("path-type")
            if raw_pt:
                stripped = _strip_ospf_value(raw_pt)
                route["raw-path-type"] = stripped
                route["path-type"] = _OSPF_PATH_TYPE_MAP.get(
                    stripped, stripped.lower()
                )

            if "area-id" in bestpath:
                route["area"] = str(bestpath["area-id"])
            if "metric" in bestpath:
                route["metric"] = bestpath["metric"]
            if "path-flags" in bestpath:
                route["path-flags"] = [
                    _strip_ospf_value(pf) for pf in bestpath["path-flags"]
                ]

            for lsa_key in ("received-lsa", "self-originated-lsa"):
                lsa = bestpath.get(lsa_key)
                if lsa:
                    lsa_entry: Dict[str, TypeAny] = {}
                    if "lsa-type" in lsa:
                        lsa_entry["lsa-type"] = _strip_ospf_value(
                            lsa["lsa-type"]
                        )
                    if "link-state-id" in lsa:
                        lsa_entry["link-state-id"] = lsa["link-state-id"]
                    if "advertising-router" in lsa:
                        lsa_entry["advertising-router"] = (
                            lsa["advertising-router"]
                        )
                    if lsa_entry:
                        route[lsa_key] = lsa_entry

            nh_set = bestpath.get("nexthop-set", {}) or {}
            nh_state = nh_set.get("state", {}) or {}
            nh_set_entry: Dict[str, TypeAny] = {}
            for k in ("nexthop-set-id", "nexthop-count", "reference-count"):
                if k in nh_state:
                    nh_set_entry[k] = nh_state[k]
            if nh_set_entry:
                route["nexthop-set"] = nh_set_entry

            nh_container = nh_set.get("nexthops", {}) or {}
            nh_list = nh_container.get("nexthop", []) or []
            next_hops = []
            for nh in nh_list:
                nh_state = nh.get("state", {}) or {}
                interface = (
                    nh_state.get("outgoing-interface")
                    or nh.get("outgoing-interface")
                )
                address = (
                    nh_state.get("nexthop-address")
                    or nh.get("nexthop-address")
                )
                nh_entry: Dict[str, TypeAny] = {}
                if interface:
                    nh_entry["interface"] = interface
                if address:
                    nh_entry["address"] = address
                if nh_entry:
                    next_hops.append(nh_entry)
            if next_hops:
                route["next-hops"] = next_hops

            routes[key] = route

        if not routes:
            raise SchemaEmptyParserError("No OSPF RIB prefix entries parsed")

        return {"routes": routes}
