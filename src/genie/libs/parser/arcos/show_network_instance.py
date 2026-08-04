"""show_network_instance.py

ArcOS parsers for the following show commands:
    * show network-instance {network_instance}
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import OPENCONFIG_NETWORK_INSTANCES
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)

# Namespace prefixes to strip from keys and values
_BGP_AUG_PREFIX = "arcos-openconfig-bgp-augments:"
_NI_AUG_PREFIX = "arcos-openconfig-network-instance-augments:"
_L2RIB_PREFIX = "arcos-l2rib:"
_NI_TYPES_PREFIX = "openconfig-network-instance-types:"
_BGP_TYPES_PREFIX = "openconfig-bgp-types:"
_POLICY_TYPES_PREFIX = "openconfig-policy-types:"
_OC_TYPES_PREFIX = "openconfig-types:"


class ShowNetworkInstanceSchema(MetaParser):
    """Schema for ArcOS ``show network-instance`` output."""

    schema = {
        Optional("network-instance"): {
            Any(): {  # NI name
                Optional("name"): str,
                Optional("interfaces"): {
                    Any(): {  # interface id (e.g., "swp5.6001")
                        Optional("interface"): str,
                        Optional("subinterface"): Or(str, int),
                    }
                },
                Optional("fdb"): {
                    Optional("mac-entries"): {
                        Any(): {  # mac-address
                            Optional("vlan"): Or(str, int),
                            Optional("entry-type"): str,
                        }
                    }
                },
                Optional("l2rib"): {
                    Optional("id"): Or(str, int),
                    Optional("name"): str,
                    Optional("type"): str,
                    Optional("vni"): Or(str, int),
                    Optional("advertise-mac-routes"): bool,
                    Optional("maximum-mac-entries"): Or(str, int),
                    Optional("pkt-action"): str,
                    Optional("local-label"): Or(str, int),
                    Optional("is-irb"): bool,
                    Optional("mac-count"): Or(str, int),
                    Optional("mac-ipv4-count"): Or(str, int),
                },
                Optional("bgp"): {
                    Optional("as"): Or(str, int),
                    Optional("router-id"): str,
                    Optional("route-distinguisher"): str,
                    Optional("label-allocation-mode"): str,
                    Optional("control-word"): bool,
                    Optional("flow-label"): bool,
                    Optional("vni-evi"): Or(str, int),
                    Optional("tunnel-type"): str,
                    Optional("total-paths"): Or(str, int),
                    Optional("total-prefixes"): Or(str, int),
                    Optional("afi-safis"): list,
                    Optional("route-targets"): list,
                },
                Optional("table-connections"): list,
                Optional("rib-options"): {
                    Optional("ipv4"): {
                        Optional("max-prefix-limit"): Or(str, int),
                        Optional("threshold"): Or(str, int),
                    },
                    Optional("ipv6"): {
                        Optional("max-prefix-limit"): Or(str, int),
                        Optional("threshold"): Or(str, int),
                    },
                },
                Optional("l3vrf"): {
                    Optional("vrf-interface"): str,
                    Optional("table-id"): Or(str, int),
                },
            }
        }
    }


class ShowNetworkInstance(ShowNetworkInstanceSchema):
    """Parser for ArcOS ``show network-instance`` (JSON format).

    The parser expects OpenConfig JSON of the form::

        data["openconfig-network-instance:network-instances"]
            ["network-instance"][]

    Each network instance entry is flattened into interfaces, FDB MAC
    entries, L2RIB state, and BGP global state.  Namespace prefixes
    are stripped from keys and values.

    When no explicit output is provided, the parser runs::

        show network-instance {network_instance} | display json | nomore
    """

    cli_command = "show network-instance {network_instance}"

    def cli(
        self,
        network_instance: str = "",
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            if not network_instance:
                raise ValueError("network_instance parameter is required")
            cmd = (
                f"show network-instance {network_instance}"
                f" | display json | nomore"
            )
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowNetworkInstance: empty output")

        parsed_json = load_json_robust(output)

        result = self._parse_network_instance(parsed_json)

        if not result:
            raise SchemaEmptyParserError(
                "No network-instance data found in output"
            )

        return result

    def _parse_network_instance(
        self, json_data: Dict
    ) -> Dict[str, TypeAny]:
        """Extract network instance data from OpenConfig JSON."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        instances: Dict[str, TypeAny] = {}

        for ni in ni_list:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            entry: Dict[str, TypeAny] = {"name": ni_name}

            # --- interfaces ---
            interfaces = self._parse_interfaces(ni)
            if interfaces:
                entry["interfaces"] = interfaces

            # --- fdb ---
            fdb = self._parse_fdb(ni)
            if fdb:
                entry["fdb"] = fdb

            # --- l2rib ---
            l2rib = self._parse_l2rib(ni)
            if l2rib:
                entry["l2rib"] = l2rib

            # --- bgp ---
            bgp = self._parse_bgp(ni)
            if bgp:
                entry["bgp"] = bgp

            # --- table-connections ---
            tc = self._parse_table_connections(ni)
            if tc:
                entry["table-connections"] = tc

            # --- rib-options ---
            rib_opts = self._parse_rib_options(ni)
            if rib_opts:
                entry["rib-options"] = rib_opts

            # --- l3vrf ---
            l3vrf = self._parse_l3vrf(ni)
            if l3vrf:
                entry["l3vrf"] = l3vrf

            instances[ni_name] = entry

        return {"network-instance": instances}

    def _parse_interfaces(self, ni: Dict) -> Dict[str, TypeAny]:
        """Flatten interfaces.interface[].state into dict keyed by id."""
        ifaces_container = ni.get("interfaces", {})
        iface_list = ifaces_container.get("interface", [])

        if not iface_list:
            return {}

        result: Dict[str, TypeAny] = {}
        for iface in iface_list:
            iface_id = iface.get("id")
            if not iface_id:
                continue

            state = iface.get("state", {})
            iface_data: Dict[str, TypeAny] = {}

            if "interface" in state:
                iface_data["interface"] = state["interface"]
            if "subinterface" in state:
                iface_data["subinterface"] = state["subinterface"]

            result[iface_id] = iface_data

        return result

    def _parse_fdb(self, ni: Dict) -> Dict[str, TypeAny]:
        """Extract FDB MAC table entries."""
        fdb = ni.get("fdb", {})
        mac_table = fdb.get(
            f"{_NI_AUG_PREFIX}mac-table-state", {}
        )
        entries_container = mac_table.get("entries", {})
        entry_list = entries_container.get("entry", [])

        if not entry_list:
            return {}

        mac_entries: Dict[str, TypeAny] = {}
        for entry in entry_list:
            state = entry.get("state", {})
            mac_addr = state.get("mac-address")
            if not mac_addr:
                mac_addr = entry.get("mac-address")
            if not mac_addr:
                continue

            mac_data: Dict[str, TypeAny] = {}
            if "vlan" in state:
                mac_data["vlan"] = state["vlan"]
            if "entry-type" in state:
                mac_data["entry-type"] = state["entry-type"]

            mac_entries[mac_addr] = mac_data

        return {"mac-entries": mac_entries}

    def _parse_l2rib(self, ni: Dict) -> Dict[str, TypeAny]:
        """Extract L2RIB state fields."""
        l2rib = ni.get(f"{_L2RIB_PREFIX}l2rib", {})
        l2ni_state = l2rib.get("l2ni-state", {})

        if not l2ni_state:
            return {}

        result: Dict[str, TypeAny] = {}

        # Direct fields from l2ni-state
        direct_fields = [
            "id", "name", "type", "vni", "advertise-mac-routes",
            "maximum-mac-entries", "pkt-action", "local-label", "is-irb",
        ]
        for field in direct_fields:
            if field in l2ni_state:
                value = l2ni_state[field]
                # Strip namespace prefixes from string values
                if isinstance(value, str):
                    value = _strip_value_prefix(value)
                result[field] = value

        # mac-count from stats-entries.current-total.num-macs
        stats = l2rib.get("stats-entries", {})
        current_total = stats.get("current-total", {})
        if "num-macs" in current_total:
            result["mac-count"] = current_total["num-macs"]

        # mac-ipv4-count from counting mac-ipv4-entries.entry[]
        mac_ipv4 = l2rib.get("mac-ipv4-entries", {})
        mac_ipv4_list = mac_ipv4.get("entry", [])
        if mac_ipv4_list:
            result["mac-ipv4-count"] = len(mac_ipv4_list)

        return result

    def _parse_table_connections(self, ni: Dict) -> list:
        """Extract table-connections as a list of dicts."""
        tc_container = ni.get("table-connections", {})
        tc_list = tc_container.get("table-connection", [])

        if not tc_list:
            return []

        result = []
        for tc in tc_list:
            entry: Dict[str, TypeAny] = {}

            src = tc.get("src-protocol", "")
            if src:
                entry["src-protocol"] = _strip_value_prefix(src)

            dst = tc.get("dst-protocol", "")
            if dst:
                entry["dst-protocol"] = _strip_value_prefix(dst)

            af = tc.get("address-family", "")
            if af:
                entry["address-family"] = _strip_value_prefix(af)

            # Extract src-dst-instances if present
            sdi_container = tc.get(
                f"{_NI_AUG_PREFIX}src-dst-instances", {}
            )
            sdi_list = sdi_container.get("src-dst-instance", [])
            if sdi_list:
                instances = []
                for sdi in sdi_list:
                    inst = {}
                    if "src-instance" in sdi:
                        inst["src-instance"] = sdi["src-instance"]
                    if "dst-instance" in sdi:
                        inst["dst-instance"] = sdi["dst-instance"]
                    if inst:
                        instances.append(inst)
                if instances:
                    entry["src-dst-instances"] = instances

            if entry:
                result.append(entry)

        return result

    def _parse_rib_options(self, ni: Dict) -> Dict[str, TypeAny]:
        """Extract rib-options (IPv4/IPv6 max-prefix-limit, threshold)."""
        rib_opts = ni.get("arcos-rib:rib-options", {})

        if not rib_opts:
            return {}

        result: Dict[str, TypeAny] = {}

        for af in ("ipv4", "ipv6"):
            af_data = rib_opts.get(af, {})
            state = af_data.get("state", {})
            if state:
                af_result: Dict[str, TypeAny] = {}
                if "max-prefix-limit" in state:
                    af_result["max-prefix-limit"] = state["max-prefix-limit"]
                if "threshold" in state:
                    af_result["threshold"] = state["threshold"]
                if af_result:
                    result[af] = af_result

        return result

    def _parse_l3vrf(self, ni: Dict) -> Dict[str, TypeAny]:
        """Extract L3VRF state (vrf-interface, table-id)."""
        l3vrf = ni.get(f"{_NI_AUG_PREFIX}l3vrf", {})
        state = l3vrf.get("state", {})

        if not state:
            return {}

        result: Dict[str, TypeAny] = {}
        if "vrf-interface" in state:
            result["vrf-interface"] = state["vrf-interface"]
        if "table-id" in state:
            result["table-id"] = state["table-id"]

        return result

    def _parse_bgp(self, ni: Dict) -> Dict[str, TypeAny]:
        """Extract BGP global state from the BGP protocol entry."""
        protocols = ni.get("protocols", {})
        protocol_list = protocols.get("protocol", [])

        bgp_protocol = None
        for protocol in protocol_list:
            identifier = protocol.get("identifier", "")
            if "BGP" in identifier:
                bgp_protocol = protocol
                break

        if not bgp_protocol:
            return {}

        bgp_data = bgp_protocol.get("bgp", {})
        global_data = bgp_data.get("global", {})
        state = global_data.get("state", {})

        if not state:
            return {}

        result: Dict[str, TypeAny] = {}

        # Flatten state fields, stripping augment prefixes from keys
        target_fields = {
            "as": "as",
            "router-id": "router-id",
            "total-paths": "total-paths",
            "total-prefixes": "total-prefixes",
            f"{_BGP_AUG_PREFIX}route-distinguisher": "route-distinguisher",
            f"{_BGP_AUG_PREFIX}label-allocation-mode": "label-allocation-mode",
            f"{_BGP_AUG_PREFIX}control-word": "control-word",
            f"{_BGP_AUG_PREFIX}flow-label": "flow-label",
            f"{_BGP_AUG_PREFIX}vni-evi": "vni-evi",
            f"{_BGP_AUG_PREFIX}tunnel-type": "tunnel-type",
        }

        for json_key, out_key in target_fields.items():
            if json_key in state:
                value = state[json_key]
                # Strip namespace prefixes from string values
                if isinstance(value, str):
                    value = _strip_value_prefix(value)
                result[out_key] = value

        # Extract afi-safis as list of names
        afi_safis_container = global_data.get("afi-safis", {})
        afi_safi_list = afi_safis_container.get("afi-safi", [])
        if afi_safi_list:
            afi_names = []
            for afi in afi_safi_list:
                name = afi.get("afi-safi-name", "")
                if name:
                    afi_names.append(_strip_value_prefix(name))
            if afi_names:
                result["afi-safis"] = afi_names

        # Extract route-targets (two possible locations)
        # 1. Direct: protocol.arcos-openconfig-bgp-augments:route-targets (L2VPN)
        rt_container = bgp_protocol.get(
            f"{_BGP_AUG_PREFIX}route-targets", {}
        )
        rt_list = rt_container.get("route-target", [])

        # 2. Under afi-safi rt-afi-safis (L3VPN)
        if not rt_list:
            for afi in afi_safi_list:
                rt_afi_safis = afi.get(
                    f"{_BGP_AUG_PREFIX}rt-afi-safis", {}
                )
                for rt_afi in rt_afi_safis.get("rt-afi-safi", []):
                    rts = rt_afi.get("route-targets", {})
                    rt_list = rts.get("route-target", [])
                    if rt_list:
                        break
                if rt_list:
                    break

        if rt_list:
            route_targets = []
            for rt in rt_list:
                rt_entry: Dict[str, str] = {}
                # Use state sub-object if present, otherwise top-level
                rt_state = rt.get("state", rt)
                if "route-target" in rt_state:
                    rt_entry["route-target"] = rt_state["route-target"]
                if "route-target-type" in rt_state:
                    rt_entry["route-target-type"] = rt_state[
                        "route-target-type"
                    ]
                if rt_entry:
                    route_targets.append(rt_entry)
            if route_targets:
                result["route-targets"] = route_targets

        return result


def _strip_value_prefix(value: str) -> str:
    """Remove known namespace prefixes from a value string."""
    for prefix in (
        _BGP_AUG_PREFIX,
        _NI_AUG_PREFIX,
        _L2RIB_PREFIX,
        _NI_TYPES_PREFIX,
        _BGP_TYPES_PREFIX,
        _POLICY_TYPES_PREFIX,
        _OC_TYPES_PREFIX,
    ):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value
