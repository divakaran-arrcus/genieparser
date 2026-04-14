"""ArcOS OSPFv2 parsers using JSON output.

Parsers:

1. ShowOspfGlobal — ``show network-instance {ni} protocol OSPF {instance} global state``
2. ShowOspfNeighbor — ``show network-instance {ni} protocol OSPF {instance} area {area} interface * neighbor``
3. ShowOspfArea — ``show network-instance {ni} protocol OSPF {instance} area state``
4. ShowOspfInterface — ``show network-instance {ni} protocol OSPF {instance} area {area} interface state``
5. ShowOspfSpfThrottle — ``show network-instance {ni} protocol OSPF {instance} global spf throttle``
6. ShowOspfLsdb — ``show network-instance {ni} protocol OSPF {instance} area {area} lsdb``
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

        parsed = load_json_robust(output)
        ospf = _navigate_to_ospf(parsed)
        state = ospf.get("global", {}).get("state", {})

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
