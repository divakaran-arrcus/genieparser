"""ArcOS show bgp parser using OpenConfig JSON output."""

import json
import logging
from typing import Any as TypeAny, Dict, List, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import (
    ARCOS_BGP_AUGMENTS,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)

# Prefix strings to strip from keys and values
_BGP_AUG_PREFIX = f"{ARCOS_BGP_AUGMENTS}:"
_BGP_TYPES_PREFIX = "openconfig-bgp-types:"
_ARCOS_BGP_TYPES_PREFIX = "arcos-openconfig-bgp-types:"
_POLICY_TYPES_PREFIX = "openconfig-policy-types:"


class ShowBgpNeighborSchema(MetaParser):
    """Schema for ArcOS ``show bgp neighbor`` output."""

    schema = {
        Optional("neighbors"): {
            Any(): {  # neighbor-address
                Optional("neighbor-address"): str,
                Optional("peer-group"): str,
                Optional("enabled"): bool,
                Optional("peer-as"): Or(str, int),
                Optional("local-as"): Or(str, int),
                Optional("peer-type"): str,
                Optional("session-state"): str,
                Optional("description"): str,
                Optional("established-transitions"): Or(str, int),
                Optional("remote-router-id"): str,
                Optional("shutdown"): bool,
                Optional("shutdown-reason"): str,
                Optional("last-reset-reason"): str,
                Optional("session-elapsed-time"): str,
                Optional("last-established"): str,
                Optional("messages-sent"): {
                    Optional("UPDATE"): Or(str, int),
                    Optional("NOTIFICATION"): Or(str, int),
                    Optional("KEEPALIVE"): Or(str, int),
                    Optional("total"): Or(str, int),
                },
                Optional("messages-received"): {
                    Optional("UPDATE"): Or(str, int),
                    Optional("NOTIFICATION"): Or(str, int),
                    Optional("KEEPALIVE"): Or(str, int),
                    Optional("total"): Or(str, int),
                },
                Optional("transport"): {
                    Optional("local-address"): str,
                    Optional("local-port"): Or(str, int),
                    Optional("remote-address"): str,
                    Optional("remote-port"): Or(str, int),
                },
                Optional("afi-safis"): list,  # list of AFI names (stripped)
            }
        }
    }


class ShowBgpNeighbor(ShowBgpNeighborSchema):
    """Parser for ArcOS ``show bgp neighbor`` (JSON format).

    The parser expects OpenConfig JSON of the form::

        data["openconfig-network-instance:network-instances"]
            ["network-instance"][0]["protocols"]["protocol"][BGP]
            ["bgp"]["neighbors"]["neighbor"][]

    Each neighbor entry contains state, transport, and optional afi-safis.
    Namespace prefixes (``arcos-openconfig-bgp-augments:``,
    ``openconfig-bgp-types:``, ``openconfig-policy-types:``) are stripped
    from keys and values.

    When no explicit output is provided, the parser runs::

        show network-instance {network_instance} protocol BGP
            {protocol_instance} neighbor [<neighbor>] | display json | nomore
    """

    cli_command = [
        "show network-instance {network_instance} protocol BGP"
        " {protocol_instance} neighbor",
        "show network-instance {network_instance} protocol BGP"
        " {protocol_instance} neighbor {neighbor}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        protocol_instance: str = "default",
        neighbor: TypeOptional[str] = None,
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            if neighbor:
                cmd = self.cli_command[1].format(
                    network_instance=network_instance,
                    protocol_instance=protocol_instance,
                    neighbor=neighbor,
                )
            else:
                cmd = self.cli_command[0].format(
                    network_instance=network_instance,
                    protocol_instance=protocol_instance,
                )
            cmd = f"{cmd} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        parsed_json = load_json_robust(output)

        result = self._parse_neighbors(parsed_json)

        if not result:
            raise SchemaEmptyParserError("No BGP neighbor data found in output")

        return result

    def _parse_neighbors(self, json_data: Dict) -> Dict[str, TypeAny]:
        """Extract BGP neighbors from OpenConfig JSON."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        # Take first network-instance entry
        ni = ni_list[0]
        protocols = ni.get("protocols", {})
        protocol_list = protocols.get("protocol", [])

        # Find the BGP protocol entry
        bgp_protocol = None
        for proto in protocol_list:
            ident = proto.get("identifier", "")
            if "BGP" in ident:
                bgp_protocol = proto
                break

        if bgp_protocol is None:
            return {}

        bgp = bgp_protocol.get("bgp", {})
        neighbors_container = bgp.get("neighbors", {})
        neighbor_list = neighbors_container.get("neighbor", [])

        if not neighbor_list:
            return {}

        neighbors: Dict[str, TypeAny] = {}

        for nbr in neighbor_list:
            addr = nbr.get("neighbor-address")
            if not addr:
                continue

            entry: Dict[str, TypeAny] = {}

            # Flatten state fields
            state = nbr.get("state", {})
            _extract_state_fields(state, entry)

            # Extract messages sent/received from state.messages
            messages = state.get("messages", {})
            if messages:
                sent = messages.get("sent", {})
                if sent:
                    entry["messages-sent"] = _flatten_message_counters(sent)
                received = messages.get("received", {})
                if received:
                    entry["messages-received"] = _flatten_message_counters(
                        received
                    )

            # Extract transport state
            transport = nbr.get("transport", {})
            transport_state = transport.get("state", {})
            if transport_state:
                entry["transport"] = _flatten_transport(transport_state)

            # Extract afi-safi names
            afi_safis = nbr.get("afi-safis", {})
            afi_safi_list = afi_safis.get("afi-safi", [])
            if afi_safi_list:
                entry["afi-safis"] = [
                    _strip_value_prefix(
                        af.get("afi-safi-name", "")
                    )
                    for af in afi_safi_list
                    if af.get("afi-safi-name")
                ]

            neighbors[addr] = entry

        return {"neighbors": neighbors}


# Key fields to extract from neighbor state (before prefix stripping)
_STATE_KEYS = {
    "neighbor-address",
    "peer-group",
    "enabled",
    "peer-as",
    "local-as",
    "peer-type",
    "session-state",
    "description",
    "established-transitions",
    "remote-router-id",
    "shutdown",
    "shutdown-reason",
    "last-reset-reason",
    "session-elapsed-time",
    "last-established",
}


def _extract_state_fields(
    state: Dict, entry: Dict[str, TypeAny]
) -> None:
    """Extract key fields from neighbor state, stripping augment prefixes."""
    for key, value in state.items():
        if key == "messages":
            continue  # handled separately
        clean_key = _strip_augment_prefix(key)
        if clean_key in _STATE_KEYS:
            entry[clean_key] = value


def _flatten_message_counters(
    msg: Dict,
) -> Dict[str, TypeAny]:
    """Flatten message counters, stripping augment prefix from keys."""
    result: Dict[str, TypeAny] = {}
    for key, value in msg.items():
        clean_key = _strip_augment_prefix(key)
        result[clean_key] = value
    return result


def _flatten_transport(
    transport_state: Dict,
) -> Dict[str, TypeAny]:
    """Flatten transport state, stripping augment prefix from keys."""
    result: Dict[str, TypeAny] = {}
    for key, value in transport_state.items():
        clean_key = _strip_augment_prefix(key)
        result[clean_key] = value
    return result


def _strip_augment_prefix(key: str) -> str:
    """Remove ``arcos-openconfig-bgp-augments:`` prefix from a key."""
    if key.startswith(_BGP_AUG_PREFIX):
        return key[len(_BGP_AUG_PREFIX):]
    return key


def _strip_value_prefix(value: str) -> str:
    """Remove known namespace prefixes from a value string."""
    if value.startswith(_BGP_TYPES_PREFIX):
        return value[len(_BGP_TYPES_PREFIX):]
    if value.startswith(_ARCOS_BGP_TYPES_PREFIX):
        return value[len(_ARCOS_BGP_TYPES_PREFIX):]
    if value.startswith(_POLICY_TYPES_PREFIX):
        return value[len(_POLICY_TYPES_PREFIX):]
    if value.startswith(_BGP_AUG_PREFIX):
        return value[len(_BGP_AUG_PREFIX):]
    return value


# ---------------------------------------------------------------------------
# BGP Global State parser
# ---------------------------------------------------------------------------


class ShowBgpGlobalStateSchema(MetaParser):
    """Schema for ArcOS ``show bgp global state`` output."""

    schema = {
        Optional("as"): Or(str, int),
        Optional("router-id"): str,
        Optional("total-paths"): Or(str, int),
        Optional("total-prefixes"): Or(str, int),
        Optional("route-distinguisher"): str,
        Optional("total-configured-neighbors"): Or(str, int),
        Optional("total-established-neighbors"): Or(str, int),
        Optional("established-configured-neighbors"): Or(str, int),
        Optional("shutdown-configured-neighbors"): Or(str, int),
        Optional("network-instances-present"): Or(str, int),
        Optional("cluster-id"): str,
        Optional("segment-routing-enabled"): bool,
        Optional("shutdown-protocol"): bool,
    }


class ShowBgpGlobalState(ShowBgpGlobalStateSchema):
    """Parser for ArcOS ``show bgp global state`` (JSON format).

    Parses BGP global state from::

        show network-instance {network_instance} protocol BGP
            {protocol_instance} global state | display json | nomore
    """

    cli_command = (
        "show network-instance {network_instance} protocol BGP"
        " {protocol_instance} global state"
    )

    def cli(
        self,
        network_instance: str = "default",
        protocol_instance: str = "default",
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = self.cli_command.format(
                network_instance=network_instance,
                protocol_instance=protocol_instance,
            )
            cmd = f"{cmd} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        parsed_json = load_json_robust(output)
        result = self._parse_global_state(parsed_json)

        if not result:
            raise SchemaEmptyParserError(
                "No BGP global state data found in output"
            )

        return result

    def _parse_global_state(
        self, json_data: Dict
    ) -> Dict[str, TypeAny]:
        """Extract BGP global state."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        ni = ni_list[0]
        protocols = ni.get("protocols", {})
        protocol_list = protocols.get("protocol", [])

        bgp_protocol = None
        for proto in protocol_list:
            if "BGP" in proto.get("identifier", ""):
                bgp_protocol = proto
                break

        if not bgp_protocol:
            return {}

        state = (
            bgp_protocol.get("bgp", {})
            .get("global", {})
            .get("state", {})
        )

        if not state:
            return {}

        result: Dict[str, TypeAny] = {}

        # Direct fields
        for key in ("as", "router-id", "total-paths", "total-prefixes"):
            if key in state:
                result[key] = state[key]

        # Augmented fields — strip prefix
        aug_fields = {
            "route-distinguisher": "route-distinguisher",
            "total-configured-neighbors": "total-configured-neighbors",
            "total-established-neighbors": "total-established-neighbors",
            "established-configured-neighbors": "established-configured-neighbors",
            "shutdown-configured-neighbors": "shutdown-configured-neighbors",
            "network-instances-present": "network-instances-present",
            "cluster-id": "cluster-id",
            "shutdown-protocol": "shutdown-protocol",
        }

        for field, out_key in aug_fields.items():
            aug_key = f"{_BGP_AUG_PREFIX}{field}"
            if aug_key in state:
                result[out_key] = state[aug_key]

        # Segment routing enabled (nested)
        sr = state.get(f"{_BGP_AUG_PREFIX}segment-routing", {})
        if "enabled" in sr:
            result["segment-routing-enabled"] = sr["enabled"]

        return result


# ---------------------------------------------------------------------------
# BGP Global AFI-SAFI parser
# ---------------------------------------------------------------------------


# Fields to extract from each afi-safi state block (after prefix stripping)
_AFI_SAFI_STATE_KEYS = {
    "enabled",
    "total-paths",
    "total-prefixes",
    "paths-received",
    "paths-sent",
    "total-paths-received",
    "total-paths-sent",
    "total-paths-withdrawn",
    "rib-install-prefixes",
    "total-next-hops",
}


class ShowBgpGlobalAfiSafiSchema(MetaParser):
    """Schema for ArcOS ``show bgp global afi-safi`` output."""

    schema = {
        Optional("afi-safis"): {
            Any(): {  # AFI name stripped (e.g., "IPV4_UNICAST")
                Optional("enabled"): bool,
                Optional("total-paths"): Or(str, int),
                Optional("total-prefixes"): Or(str, int),
                Optional("paths-received"): Or(str, int),
                Optional("paths-sent"): Or(str, int),
                Optional("total-paths-received"): Or(str, int),
                Optional("total-paths-sent"): Or(str, int),
                Optional("total-paths-withdrawn"): Or(str, int),
                Optional("rib-install-prefixes"): Or(str, int),
                Optional("total-next-hops"): Or(str, int),
            }
        }
    }


class ShowBgpGlobalAfiSafi(ShowBgpGlobalAfiSafiSchema):
    """Parser for ArcOS ``show bgp global afi-safi`` (JSON format).

    Parses BGP global AFI-SAFI summary from::

        show network-instance {network_instance} protocol BGP
            {protocol_instance} global afi-safi | display json | nomore

    Each AFI-SAFI entry is keyed by the stripped AFI name (e.g.
    ``IPV4_UNICAST``, ``L2VPN_EVPN``).  Only the ``state`` block fields
    are extracted; next-hops, memory-counters, auto-peer-groups and other
    sub-containers are ignored.
    """

    cli_command = (
        "show network-instance {network_instance} protocol BGP"
        " {protocol_instance} global afi-safi"
    )

    def cli(
        self,
        network_instance: str = "default",
        protocol_instance: str = "default",
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = self.cli_command.format(
                network_instance=network_instance,
                protocol_instance=protocol_instance,
            )
            cmd = f"{cmd} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        parsed_json = load_json_robust(output)
        result = self._parse_afi_safis(parsed_json)

        if not result:
            raise SchemaEmptyParserError(
                "No BGP global afi-safi data found in output"
            )

        return result

    def _parse_afi_safis(
        self, json_data: Dict
    ) -> Dict[str, TypeAny]:
        """Extract per-AFI summary from OpenConfig JSON."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        ni = ni_list[0]
        protocols = ni.get("protocols", {})
        protocol_list = protocols.get("protocol", [])

        bgp_protocol = None
        for proto in protocol_list:
            if "BGP" in proto.get("identifier", ""):
                bgp_protocol = proto
                break

        if not bgp_protocol:
            return {}

        afi_safis_container = (
            bgp_protocol.get("bgp", {})
            .get("global", {})
            .get("afi-safis", {})
        )
        afi_safi_list = afi_safis_container.get("afi-safi", [])

        if not afi_safi_list:
            return {}

        afi_safis: Dict[str, Dict[str, TypeAny]] = {}

        for af in afi_safi_list:
            raw_name = af.get("afi-safi-name", "")
            if not raw_name:
                continue

            name = _strip_value_prefix(raw_name)
            state = af.get("state", {})

            entry: Dict[str, TypeAny] = {}
            for key, value in state.items():
                clean_key = _strip_augment_prefix(key)
                if clean_key == "afi-safi-name":
                    continue
                if clean_key in _AFI_SAFI_STATE_KEYS:
                    entry[clean_key] = value

            afi_safis[name] = entry

        if not afi_safis:
            return {}

        return {"afi-safis": afi_safis}


# ---------------------------------------------------------------------------
# BGP RIB route parser
# ---------------------------------------------------------------------------

_RIB_AUG_PREFIX = "arcos-openconfig-rib-bgp-augments:"

# AFI-SAFI name mapping: CLI token -> JSON sub-key
# e.g. "IPV4_UNICAST" -> "ipv4-unicast"
_AFI_SAFI_KEY_MAP = {
    "IPV4_UNICAST": "ipv4-unicast",
    "IPV6_UNICAST": "ipv6-unicast",
    "L2VPN_EVPN": "l2vpn-evpn",
}


def _afi_safi_json_key(afi_safi: str) -> str:
    """Map an AFI-SAFI CLI token to the JSON sub-key.

    Falls back to ``afi_safi.lower().replace('_', '-')`` when the token
    is not in the known map.
    """
    return _AFI_SAFI_KEY_MAP.get(afi_safi, afi_safi.lower().replace("_", "-"))


def _strip_rib_prefix(key: str) -> str:
    """Remove ``arcos-openconfig-rib-bgp-augments:`` prefix from a key."""
    if key.startswith(_RIB_AUG_PREFIX):
        return key[len(_RIB_AUG_PREFIX):]
    return key


def _strip_rib_value(value: str) -> str:
    """Remove the RIB augment prefix from a string value."""
    if isinstance(value, str) and value.startswith(_RIB_AUG_PREFIX):
        return value[len(_RIB_AUG_PREFIX):]
    return value


class ShowBgpRibRouteSchema(MetaParser):
    """Schema for ArcOS ``show bgp rib route`` output."""

    schema = {
        Optional("routes"): {
            Any(): {  # prefix (e.g., "121.121.121.121/32")
                Optional("paths"): list,  # list of path dicts
            }
        }
    }


class ShowBgpRibRoute(ShowBgpRibRouteSchema):
    """Parser for ArcOS ``show bgp rib route`` (JSON format).

    Parses the BGP RIB loc-rib route table.  The parser expects OpenConfig
    JSON of the form::

        data["openconfig-network-instance:network-instances"]
            ["network-instance"][0]["protocols"]["protocol"][BGP]
            ["bgp"]["rib"]["afi-safis"]["afi-safi"][match]
            ["ipv4-unicast"]["loc-rib"]["routes"]["route"][]

    Namespace prefix ``arcos-openconfig-rib-bgp-augments:`` is stripped
    from keys and values.
    """

    cli_command = [
        "show network-instance {network_instance} protocol BGP"
        " {protocol_instance} rib afi-safi {afi_safi} loc-rib route",
        "show network-instance {network_instance} protocol BGP"
        " {protocol_instance} rib afi-safi {afi_safi} loc-rib route {prefix}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        protocol_instance: str = "default",
        afi_safi: str = "IPV4_UNICAST",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            if prefix:
                cmd = self.cli_command[1].format(
                    network_instance=network_instance,
                    protocol_instance=protocol_instance,
                    afi_safi=afi_safi,
                    prefix=prefix,
                )
            else:
                cmd = self.cli_command[0].format(
                    network_instance=network_instance,
                    protocol_instance=protocol_instance,
                    afi_safi=afi_safi,
                )
            cmd = f"{cmd} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        parsed_json = load_json_robust(output)

        result = self._parse_rib_routes(parsed_json, afi_safi)

        if not result:
            raise SchemaEmptyParserError("No BGP RIB route data found in output")

        return result

    def _parse_rib_routes(
        self, json_data: Dict, afi_safi: str
    ) -> Dict[str, TypeAny]:
        """Extract BGP RIB routes from OpenConfig JSON."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        ni = ni_list[0]
        protocols = ni.get("protocols", {})
        protocol_list = protocols.get("protocol", [])

        # Find the BGP protocol entry
        bgp_protocol = None
        for proto in protocol_list:
            ident = proto.get("identifier", "")
            if "BGP" in ident:
                bgp_protocol = proto
                break

        if bgp_protocol is None:
            return {}

        bgp = bgp_protocol.get("bgp", {})
        rib = bgp.get("rib", {})
        afi_safis = rib.get("afi-safis", {})
        afi_safi_list = afi_safis.get("afi-safi", [])

        if not afi_safi_list:
            return {}

        # Find matching afi-safi entry
        target_name_suffix = afi_safi  # e.g. "IPV4_UNICAST"
        matching_entry = None
        for entry in afi_safi_list:
            name = entry.get("afi-safi-name", "")
            # name may look like "openconfig-bgp-types:IPV4_UNICAST"
            stripped = _strip_value_prefix(name)
            if stripped == target_name_suffix:
                matching_entry = entry
                break

        if matching_entry is None:
            return {}

        # Determine the JSON sub-key for this AFI-SAFI
        # Try plain key first (e.g., "ipv4-unicast"), then augmented
        # (e.g., "arcos-openconfig-rib-bgp-augments:l3vpn-ipv4-unicast")
        af_key = _afi_safi_json_key(afi_safi)
        af_data = matching_entry.get(af_key, {})
        if not af_data:
            af_data = matching_entry.get(
                f"{_RIB_AUG_PREFIX}{af_key}", {}
            )
        loc_rib = af_data.get("loc-rib", {})
        routes_container = loc_rib.get("routes", {})
        route_list = routes_container.get("route", [])

        if not route_list:
            return {}

        # Group routes by prefix
        routes: Dict[str, Dict[str, TypeAny]] = {}

        for route in route_list:
            prefix_val = route.get("prefix")
            if not prefix_val:
                continue

            path_entry = self._build_path_entry(route)

            if prefix_val not in routes:
                routes[prefix_val] = {"paths": []}

            routes[prefix_val]["paths"].append(path_entry)

        if not routes:
            return {}

        return {"routes": routes}

    def _build_path_entry(self, route: Dict) -> Dict[str, TypeAny]:
        """Build a single path dict from a route entry."""
        path: Dict[str, TypeAny] = {}

        # Top-level fields
        if "origin" in route:
            path["origin"] = route["origin"]
        if "path-id" in route:
            path["path-id"] = route["path-id"]

        # Flatten state
        state = route.get("state", {})
        for key, value in state.items():
            clean_key = _strip_rib_prefix(key)

            if clean_key in ("prefix",):
                # Skip prefix — already used as grouping key
                continue
            if clean_key in ("origin", "path-id"):
                # Already extracted from top-level
                continue

            if clean_key == "valid-route":
                path["valid-route"] = value
            elif clean_key == "stale-route":
                path["stale-route"] = value
            elif clean_key == "invalid-reason":
                path["invalid-reason"] = _strip_rib_value(value)
            elif clean_key == "not-best-path-reason":
                path["not-best-path-reason"] = value
            elif clean_key == "path-types":
                # Strip prefix from each value in the list
                path["path-types"] = [_strip_rib_value(v) for v in value]
            elif clean_key == "next-hop":
                path["next-hop"] = value
            elif clean_key == "link-local-next-hop":
                path["link-local-next-hop"] = value

        # Attributes are at route level, not inside state
        # Try augmented key first, then plain "attributes" (L3VPN uses plain)
        attrs = route.get(f"{_RIB_AUG_PREFIX}attributes", {})
        if not attrs:
            attrs = route.get("attributes", {})
        attr_state = attrs.get("state", {})
        for attr_key, attr_val in attr_state.items():
            if attr_key == "origin":
                path["origin-attr"] = attr_val
            else:
                path[attr_key] = attr_val

        return path


# ---------------------------------------------------------------------------
# BGP Running-Config parser
# ---------------------------------------------------------------------------

_NI_TYPES_PREFIX = "openconfig-network-instance-types:"
_MPLS_TYPES_PREFIX = "openconfig-mpls-types:"


def _strip_all_prefixes(value: str) -> str:
    """Remove all known namespace prefixes from a string value."""
    for prefix in (
        _BGP_TYPES_PREFIX,
        _ARCOS_BGP_TYPES_PREFIX,
        _POLICY_TYPES_PREFIX,
        _BGP_AUG_PREFIX,
        _NI_TYPES_PREFIX,
        _MPLS_TYPES_PREFIX,
    ):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


class ShowBgpConfigSchema(MetaParser):
    """Schema for ArcOS ``show running-config ... protocol BGP`` output."""

    schema = {
        "network-instance": {
            Any(): {  # network instance name (e.g., "default")
                "bgp": {
                    Any(): {  # protocol instance name (e.g., "default")
                        Optional("config"): {
                            # ── Global scalars ──
                            Optional("as"): Or(str, int),
                            Optional("router-id"): str,
                            Optional("adj-rib-out-post"): bool,
                            Optional("label-allocation-mode"): str,
                            Optional("drop-upon-invalid-sr-policy"): bool,
                            Optional("ignore-next-hop-igp-metric"): bool,
                            Optional("compatibility"): {
                                Optional("l2-attr-local"): bool,
                            },
                            # ── Global AFI-SAFIs ──
                            Optional("afi-safis"): {
                                Any(): {  # AFI name (e.g., "IPV4_UNICAST")
                                    Optional("null-label"): str,
                                    Optional("ibgp-maximum-paths"): Or(str, int),
                                    Optional("add-paths-calculate"): str,
                                    Optional("rtfilter-enabled"): bool,
                                    Optional("networks"): list,
                                    Optional("aggregate-addresses"): {
                                        Any(): {  # prefix
                                            Optional("summary-only"): bool,
                                        }
                                    },
                                    Optional("import-policy"): list,
                                    Optional("export-policy"): list,
                                }
                            },
                        },
                        # ── Neighbors ──
                        Optional("neighbors"): {
                            Any(): {  # neighbor address (IPv4 or IPv6)
                                Optional("peer-as"): Or(str, int),
                                Optional("peer-group"): str,
                                Optional("description"): str,
                                Optional("shutdown"): bool,
                                Optional("transport-local-address"): str,
                                Optional("bfd-enable"): bool,
                                Optional("bfd-profile"): str,
                                Optional("afi-safis"): {
                                    Any(): {  # AFI name
                                        Optional("add-paths-send"): Or(str, bool),
                                        Optional("add-paths-receive"): bool,
                                        Optional("import-policy"): list,
                                        Optional("export-policy"): list,
                                    }
                                },
                            }
                        },
                        # ── Peer Groups ──
                        Optional("peer-groups"): {
                            Any(): {  # peer-group name
                                Optional("peer-as"): Or(str, int),
                                Optional("shutdown"): bool,
                                Optional("transport-local-address"): str,
                                Optional("bfd-enable"): bool,
                                Optional("bfd-profile"): str,
                                Optional("afi-safis"): {
                                    Any(): {  # AFI name
                                        Optional("add-paths-send"): Or(str, bool),
                                        Optional("add-paths-receive"): bool,
                                        Optional("import-policy"): list,
                                        Optional("export-policy"): list,
                                    }
                                },
                            }
                        },
                    }
                }
            }
        }
    }


class ShowBgpConfig(ShowBgpConfigSchema):
    """Parser for ArcOS BGP running configuration (JSON format).

    Command pattern (before JSON pipe)::

        show running-config network-instance {network_instance} protocol BGP {protocol_instance}
    """

    cli_command = [
        "show running-config network-instance {network_instance}"
        " protocol BGP",
    ]

    def cli(
        self,
        network_instance: str = "default",
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = self.cli_command[0].format(
                network_instance=network_instance,
            )
            cmd = f"{cmd} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        parsed_json = load_json_robust(output)
        result = self._parse_bgp_config(parsed_json)

        if not result:
            raise SchemaEmptyParserError(
                "No BGP running-config data found in output"
            )

        return result

    # ------------------------------------------------------------------
    # Top-level dispatcher
    # ------------------------------------------------------------------

    def _parse_bgp_config(
        self, json_data: Dict
    ) -> Dict[str, TypeAny]:
        """Extract BGP running-config from OpenConfig JSON."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        result: Dict[str, TypeAny] = {"network-instance": {}}

        for ni in ni_list:
            ni_name = ni.get("name", "default")
            protocols = ni.get("protocols", {})
            protocol_list = protocols.get("protocol", [])

            for proto in protocol_list:
                ident = proto.get("identifier", "")
                if "BGP" not in ident:
                    continue

                proto_name = proto.get("name", "default")
                bgp = proto.get("bgp", {})
                if not bgp:
                    continue

                entry: Dict[str, TypeAny] = {}

                # Global config
                cfg = self._parse_global_config(bgp)
                if cfg:
                    entry["config"] = cfg

                # Neighbors
                nbrs = self._parse_neighbors(bgp)
                if nbrs:
                    entry["neighbors"] = nbrs

                # Peer groups
                pgs = self._parse_peer_groups(bgp)
                if pgs:
                    entry["peer-groups"] = pgs

                if entry:
                    ni_dict = result["network-instance"].setdefault(
                        ni_name, {"bgp": {}}
                    )
                    ni_dict["bgp"][proto_name] = entry

        if not result["network-instance"]:
            return {}

        return result

    # ------------------------------------------------------------------
    # Global config extraction
    # ------------------------------------------------------------------

    def _parse_global_config(
        self, bgp: Dict
    ) -> Dict[str, TypeAny]:
        """Extract global BGP config scalars and AFI-SAFIs."""
        global_data = bgp.get("global", {})
        if not global_data:
            return {}

        cfg: Dict[str, TypeAny] = {}

        # Direct config scalars
        config = global_data.get("config", {})
        if "as" in config:
            cfg["as"] = config["as"]
        if "router-id" in config:
            cfg["router-id"] = config["router-id"]

        # Augmented global scalars
        aug_adj = config.get(f"{_BGP_AUG_PREFIX}adj-rib-out-post")
        if aug_adj is not None:
            cfg["adj-rib-out-post"] = aug_adj

        aug_label = config.get(f"{_BGP_AUG_PREFIX}label-allocation-mode")
        if aug_label is not None:
            cfg["label-allocation-mode"] = _strip_all_prefixes(aug_label)

        aug_drop = config.get(
            f"{_BGP_AUG_PREFIX}drop-upon-invalid-sr-policy"
        )
        if aug_drop is not None:
            cfg["drop-upon-invalid-sr-policy"] = aug_drop

        # Route-selection-options
        rso = global_data.get("route-selection-options", {})
        rso_cfg = rso.get("config", {})
        ignore_nh = rso_cfg.get(
            f"{_BGP_AUG_PREFIX}ignore-next-hop-igp-metric"
        )
        if ignore_nh is None:
            ignore_nh = rso_cfg.get("ignore-next-hop-igp-metric")
        if ignore_nh is not None:
            cfg["ignore-next-hop-igp-metric"] = ignore_nh

        # Compatibility
        compat = global_data.get(f"{_BGP_AUG_PREFIX}compatibility", {})
        compat_cfg = compat.get("config", {})
        if "l2-attr-local" in compat_cfg:
            cfg["compatibility"] = {
                "l2-attr-local": compat_cfg["l2-attr-local"]
            }

        # Global AFI-SAFIs
        afi_safis = self._parse_global_afi_safis(global_data)
        if afi_safis:
            cfg["afi-safis"] = afi_safis

        return cfg

    # ------------------------------------------------------------------
    # Global AFI-SAFI extraction
    # ------------------------------------------------------------------

    def _parse_global_afi_safis(
        self, global_data: Dict
    ) -> Dict[str, TypeAny]:
        """Extract global AFI-SAFI config entries."""
        afi_container = global_data.get("afi-safis", {})
        afi_list = afi_container.get("afi-safi", [])
        if not afi_list:
            return {}

        result: Dict[str, TypeAny] = {}

        for af in afi_list:
            raw_name = af.get("afi-safi-name", "")
            if not raw_name:
                continue
            name = _strip_all_prefixes(raw_name)

            entry: Dict[str, TypeAny] = {}

            # null-label from config
            af_config = af.get("config", {})
            null_label = af_config.get(f"{_BGP_AUG_PREFIX}null-label")
            if null_label is not None:
                entry["null-label"] = _strip_all_prefixes(null_label)

            # ibgp maximum-paths (augmented)
            max_paths_root = af.get(
                f"{_BGP_AUG_PREFIX}use-maximum-paths", {}
            )
            max_paths_cfg = max_paths_root.get("config", {})
            ibgp = max_paths_cfg.get("ibgp", {})
            if "maximum-paths" in ibgp:
                entry["ibgp-maximum-paths"] = ibgp["maximum-paths"]

            # add-paths calculate (augmented)
            add_paths_root = af.get(f"{_BGP_AUG_PREFIX}add-paths", {})
            add_paths_cfg = add_paths_root.get("config", {})
            if "calculate" in add_paths_cfg:
                entry["add-paths-calculate"] = _strip_all_prefixes(
                    str(add_paths_cfg["calculate"])
                )

            # rtfilter (augmented)
            rtfilter_root = af.get(f"{_BGP_AUG_PREFIX}rtfilter", {})
            rtfilter_cfg = rtfilter_root.get("config", {})
            rtfilter_inner = rtfilter_cfg.get("rtfilter", {})
            if "enabled" in rtfilter_inner:
                entry["rtfilter-enabled"] = rtfilter_inner["enabled"]

            # Networks (from ipv4-unicast or ipv6-unicast sub-containers)
            networks = self._extract_networks(af)
            if networks:
                entry["networks"] = networks

            # Aggregate addresses (augmented)
            agg_root = af.get(
                f"{_BGP_AUG_PREFIX}aggregate-addresses", {}
            )
            agg_list = agg_root.get("aggregate-address", [])
            if agg_list:
                agg_dict: Dict[str, TypeAny] = {}
                for agg in agg_list:
                    agg_prefix = agg.get("prefix")
                    if not agg_prefix:
                        continue
                    agg_cfg = agg.get("config", {})
                    agg_entry: Dict[str, TypeAny] = {}
                    if "summary-only" in agg_cfg:
                        agg_entry["summary-only"] = agg_cfg["summary-only"]
                    agg_dict[agg_prefix] = agg_entry
                if agg_dict:
                    entry["aggregate-addresses"] = agg_dict

            # Global AFI-level apply-policy
            policy = af.get("apply-policy", {}).get("config", {})
            if "import-policy" in policy:
                entry["import-policy"] = policy["import-policy"]
            if "export-policy" in policy:
                entry["export-policy"] = policy["export-policy"]

            result[name] = entry

        return result

    @staticmethod
    def _extract_networks(af: Dict) -> List[str]:
        """Extract network prefixes from AFI sub-containers."""
        networks: List[str] = []
        # Check ipv4-unicast, ipv6-unicast sub-containers
        for sub_key in ("ipv4-unicast", "ipv6-unicast"):
            sub = af.get(sub_key, {})
            net_root = sub.get(f"{_BGP_AUG_PREFIX}networks", {})
            net_list = net_root.get("network", [])
            for net in net_list:
                prefix = net.get("prefix")
                if prefix:
                    networks.append(prefix)
        return networks

    # ------------------------------------------------------------------
    # Neighbor extraction
    # ------------------------------------------------------------------

    def _parse_neighbors(
        self, bgp: Dict
    ) -> Dict[str, TypeAny]:
        """Extract BGP neighbor config entries."""
        nbr_container = bgp.get("neighbors", {})
        nbr_list = nbr_container.get("neighbor", [])
        if not nbr_list:
            return {}

        result: Dict[str, TypeAny] = {}

        for nbr in nbr_list:
            addr = nbr.get("neighbor-address")
            if not addr:
                continue

            entry: Dict[str, TypeAny] = {}
            config = nbr.get("config", {})

            if "peer-as" in config:
                entry["peer-as"] = config["peer-as"]
            if "peer-group" in config:
                entry["peer-group"] = config["peer-group"]
            if "description" in config:
                entry["description"] = config["description"]

            shutdown = config.get(f"{_BGP_AUG_PREFIX}shutdown")
            if shutdown is not None:
                entry["shutdown"] = shutdown

            # Transport
            transport = nbr.get("transport", {}).get("config", {})
            if "local-address" in transport:
                entry["transport-local-address"] = transport[
                    "local-address"
                ]

            # BFD (augmented)
            bfd = nbr.get(f"{_BGP_AUG_PREFIX}bfd", {}).get("config", {})
            if "enable" in bfd:
                entry["bfd-enable"] = bfd["enable"]
            if "profile" in bfd:
                entry["bfd-profile"] = bfd["profile"]

            # Per-neighbor AFI-SAFIs
            afi_safis = self._parse_entity_afi_safis(nbr)
            if afi_safis:
                entry["afi-safis"] = afi_safis

            result[addr] = entry

        return result

    # ------------------------------------------------------------------
    # Peer-group extraction
    # ------------------------------------------------------------------

    def _parse_peer_groups(
        self, bgp: Dict
    ) -> Dict[str, TypeAny]:
        """Extract BGP peer-group config entries."""
        pg_container = bgp.get("peer-groups", {})
        pg_list = pg_container.get("peer-group", [])
        if not pg_list:
            return {}

        result: Dict[str, TypeAny] = {}

        for pg in pg_list:
            name = pg.get("peer-group-name")
            if not name:
                continue

            entry: Dict[str, TypeAny] = {}
            config = pg.get("config", {})

            if "peer-as" in config:
                entry["peer-as"] = config["peer-as"]

            shutdown = config.get(f"{_BGP_AUG_PREFIX}shutdown")
            if shutdown is not None:
                entry["shutdown"] = shutdown

            # Transport
            transport = pg.get("transport", {}).get("config", {})
            if "local-address" in transport:
                entry["transport-local-address"] = transport[
                    "local-address"
                ]

            # BFD (augmented)
            bfd = pg.get(f"{_BGP_AUG_PREFIX}bfd", {}).get("config", {})
            if "enable" in bfd:
                entry["bfd-enable"] = bfd["enable"]
            if "profile" in bfd:
                entry["bfd-profile"] = bfd["profile"]

            # Per-peer-group AFI-SAFIs
            afi_safis = self._parse_entity_afi_safis(pg)
            if afi_safis:
                entry["afi-safis"] = afi_safis

            result[name] = entry

        return result

    # ------------------------------------------------------------------
    # Shared: per-entity AFI-SAFI (neighbors and peer-groups)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_entity_afi_safis(
        entity: Dict,
    ) -> Dict[str, TypeAny]:
        """Extract per-neighbor or per-peer-group AFI-SAFI config."""
        afi_container = entity.get("afi-safis", {})
        afi_list = afi_container.get("afi-safi", [])
        if not afi_list:
            return {}

        result: Dict[str, TypeAny] = {}

        for af in afi_list:
            raw_name = af.get("afi-safi-name", "")
            if not raw_name:
                continue
            name = _strip_all_prefixes(raw_name)

            entry: Dict[str, TypeAny] = {}

            # add-paths send/receive
            add_paths = af.get(f"{_BGP_AUG_PREFIX}add-paths", {})
            ap_cfg = add_paths.get("config", {})
            if "send" in ap_cfg:
                val = ap_cfg["send"]
                if isinstance(val, str):
                    entry["add-paths-send"] = _strip_all_prefixes(val)
                else:
                    entry["add-paths-send"] = val
            if "receive" in ap_cfg:
                entry["add-paths-receive"] = ap_cfg["receive"]

            # apply-policy
            policy = af.get("apply-policy", {}).get("config", {})
            if "import-policy" in policy:
                entry["import-policy"] = policy["import-policy"]
            if "export-policy" in policy:
                entry["export-policy"] = policy["export-policy"]

            result[name] = entry

        return result


# =====================================================================
# ShowBgpLabelDb — BGP MPLS label database (for 6PE)
# =====================================================================

class ShowBgpLabelDbSchema(MetaParser):
    """Schema for ``show ... global mpls label-db``."""

    schema = {
        Optional("labels"): {
            Any(): {  # label value as key
                "label": int,
                Optional("prefix"): str,
                Optional("afi-safi"): str,
                Optional("neighbor"): str,
            }
        }
    }


class ShowBgpLabelDb(ShowBgpLabelDbSchema):
    """Parser for BGP MPLS label database.

    Parses output of::

        show network-instance {ni} protocol BGP {instance} global mpls label-db
    """

    cli_command = (
        "show network-instance {ni} protocol BGP {instance} "
        "global mpls label-db"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol BGP {instance} "
                f"global mpls label-db | display json | nomore"
            )
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])
        if not ni_list:
            raise SchemaEmptyParserError("No BGP label-db data found")

        ni_entry = ni_list[0]
        protocols = ni_entry.get("protocols", {}).get("protocol", [])

        bgp_proto = None
        for proto in protocols:
            ident = proto.get("identifier", "")
            if "BGP" in ident:
                bgp_proto = proto
                break

        if not bgp_proto:
            raise SchemaEmptyParserError("No BGP protocol found")

        bgp = bgp_proto.get("bgp", {})
        global_data = bgp.get("global", {})

        # Navigate to mpls label-db
        mpls = global_data.get(f"{_BGP_AUG_PREFIX}mpls",
                               global_data.get("mpls", {}))
        label_db = mpls.get("label-db", mpls.get("label-database", {}))
        label_entries = label_db.get("label-entry",
                                     label_db.get("entry", []))

        if not label_entries:
            raise SchemaEmptyParserError("No BGP label-db entries found")

        if isinstance(label_entries, dict):
            label_entries = [label_entries]

        result = {"labels": {}}

        for le in label_entries:
            state = le.get("state", le.get("config", le))
            label_val = state.get("label", le.get("label"))
            if label_val is None:
                continue

            entry = {"label": int(label_val)}

            prefix = state.get("prefix", state.get("ip-prefix"))
            if prefix:
                entry["prefix"] = prefix

            afi = state.get("afi-safi-name", state.get("afi-safi"))
            if afi:
                entry["afi-safi"] = _strip_all_prefixes(str(afi))

            nbr = state.get("neighbor", state.get("neighbor-address"))
            if nbr:
                entry["neighbor"] = nbr

            result["labels"][str(label_val)] = entry

        if not result["labels"]:
            raise SchemaEmptyParserError("No BGP label-db entries found")

        return result
