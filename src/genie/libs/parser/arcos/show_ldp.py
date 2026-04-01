"""ArcOS LDP parsers using OpenConfig JSON output.

Four parsers:

1. ShowLdpInterface
   ``show network-instance default mpls signaling-protocols ldp
     interface-attributes interface | display json | nomore``

2. ShowLdpSession
   ``show network-instance default mpls signaling-protocols ldp
     sessions ipv4 session | display json | nomore``

3. ShowLdpHelloAdjacency
   ``show network-instance default mpls signaling-protocols ldp
     hello-adjacencies ipv4 hello-adjacency | display json | nomore``

4. ShowLdpNeighbor
   ``show network-instance default mpls signaling-protocols ldp
     neighbor | display json | nomore``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


# Common navigation helper
def _navigate_to_ldp(parsed: Dict) -> Dict:
    """Navigate OpenConfig JSON to the LDP container.

    Path: data → network-instances → network-instance[0] → mpls
          → signaling-protocols → ldp
    """
    data = parsed.get("data", {})
    ni_container = data.get("openconfig-network-instance:network-instances", {})
    ni_list = ni_container.get("network-instance", [])
    if not ni_list:
        return {}
    ni = ni_list[0]
    mpls = ni.get("mpls", {})
    sig = mpls.get("signaling-protocols", {})
    return sig.get("ldp", {})


# =====================================================================
# ShowLdpInterface
# =====================================================================

class ShowLdpInterfaceSchema(MetaParser):
    """Schema for LDP interface-attributes."""

    schema = {
        "interfaces": {
            Any(): {  # interface-id
                "interface-id": str,
                Optional("hello-holdtime"): int,
                Optional("hello-interval"): int,
                Optional("link-hello"): bool,
                Optional("address-families"): {
                    Any(): {  # afi-name
                        "afi-name": str,
                        "enabled": bool,
                    }
                },
            }
        }
    }


class ShowLdpInterface(ShowLdpInterfaceSchema):
    """Parser for ArcOS LDP interface-attributes (JSON format)."""

    cli_command = (
        "show network-instance default mpls signaling-protocols ldp "
        "interface-attributes interface"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ldp = _navigate_to_ldp(parsed)
        intf_attrs = ldp.get("interface-attributes", {})
        intf_list = intf_attrs.get("interfaces", {}).get("interface", [])

        if not intf_list:
            raise SchemaEmptyParserError("No LDP interface data found")

        result = {"interfaces": {}}

        for intf in intf_list:
            intf_id = intf.get("interface-id")
            if not intf_id:
                continue

            state = intf.get("state", {})
            entry = {
                "interface-id": intf_id,
            }

            for key in ("hello-holdtime", "hello-interval"):
                if key in state:
                    entry[key] = state[key]

            if "link-hello" in state:
                entry["link-hello"] = state["link-hello"]

            # Address families
            af_container = intf.get("address-families", {})
            af_list = af_container.get("address-family", [])
            if af_list:
                entry["address-families"] = {}
                for af in af_list:
                    af_name = af.get("afi-name")
                    if not af_name:
                        continue
                    af_state = af.get("state", {})
                    entry["address-families"][af_name] = {
                        "afi-name": af_name,
                        "enabled": af_state.get("enabled", False),
                    }

            result["interfaces"][intf_id] = entry

        return result


# =====================================================================
# ShowLdpSession
# =====================================================================

class ShowLdpSessionSchema(MetaParser):
    """Schema for LDP sessions."""

    schema = {
        "sessions": {
            Any(): {  # peer-address
                "peer-address": str,
                Optional("local-address"): str,
                Optional("session-state"): str,
                Optional("session-role"): str,
                Optional("keepalive-timeout"): int,
                Optional("keepalive-interval"): int,
                Optional("local-lsr-id"): str,
                Optional("local-label-space-id"): int,
                Optional("remote-lsr-id"): str,
                Optional("remote-label-space-id"): int,
                Optional("graceful-restart"): str,
                Optional("graceful-restart-state"): str,
                Optional("reconnect-time"): int,
                Optional("recovery-time"): int,
                Optional("forwarding-holdtime"): int,
                Optional("last-update-timestamp"): str,
                Optional("last-established-time"): str,
                Optional("uptime"): str,
                Optional("reset-count"): int,
            }
        }
    }


class ShowLdpSession(ShowLdpSessionSchema):
    """Parser for ArcOS LDP sessions (JSON format)."""

    cli_command = (
        "show network-instance default mpls signaling-protocols ldp "
        "sessions ipv4 session"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ldp = _navigate_to_ldp(parsed)

        # Sessions are under an arcOS augment namespace
        sessions_container = ldp.get(
            "arcos-openconfig-network-instance-augments:sessions", {}
        )
        session_list = sessions_container.get("ipv4", {}).get("session", [])

        if not session_list:
            raise SchemaEmptyParserError("No LDP session data found")

        result = {"sessions": {}}

        for sess in session_list:
            state = sess.get("state", {})
            peer_addr = state.get("peer-address") or sess.get("peer-address")
            if not peer_addr:
                continue

            entry = {"peer-address": peer_addr}

            for key in (
                "local-address", "session-state", "session-role",
                "local-lsr-id", "remote-lsr-id",
                "graceful-restart", "graceful-restart-state",
                "last-update-timestamp", "last-established-time",
                "uptime",
            ):
                if key in state:
                    entry[key] = state[key]

            for key in (
                "keepalive-timeout", "keepalive-interval",
                "local-label-space-id", "remote-label-space-id",
                "reconnect-time", "recovery-time",
                "forwarding-holdtime", "reset-count",
            ):
                if key in state:
                    entry[key] = state[key]

            result["sessions"][peer_addr] = entry

        return result


# =====================================================================
# ShowLdpHelloAdjacency
# =====================================================================

class ShowLdpHelloAdjacencySchema(MetaParser):
    """Schema for LDP hello adjacencies."""

    schema = {
        "hello-adjacencies": {
            Any(): {  # peer-address
                "peer-address": str,
                Optional("version"): int,
                Optional("lsr-id"): str,
                Optional("label-space-id"): int,
                Optional("transport-address"): str,
                Optional("source-address"): str,
                Optional("holdtime"): int,
                Optional("interface"): str,
                Optional("uptime"): str,
                Optional("reset-count"): int,
                Optional("adjacency-type"): str,
            }
        }
    }


class ShowLdpHelloAdjacency(ShowLdpHelloAdjacencySchema):
    """Parser for ArcOS LDP hello adjacencies (JSON format)."""

    cli_command = (
        "show network-instance default mpls signaling-protocols ldp "
        "hello-adjacencies ipv4 hello-adjacency"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ldp = _navigate_to_ldp(parsed)

        adj_container = ldp.get(
            "arcos-openconfig-network-instance-augments:hello-adjacencies", {}
        )
        adj_list = adj_container.get("ipv4", {}).get("hello-adjacency", [])

        if not adj_list:
            raise SchemaEmptyParserError(
                "No LDP hello adjacency data found"
            )

        result = {"hello-adjacencies": {}}

        for adj in adj_list:
            state = adj.get("state", {})
            peer_addr = state.get("peer-address") or adj.get("peer-address")
            if not peer_addr:
                continue

            # Multiple adjacencies can share the same peer-address
            # (LINK + TARGETED). Use peer-address + type as key.
            adj_type = state.get("adjacency-type", "LINK")
            key = f"{peer_addr}:{adj_type}"

            entry = {"peer-address": peer_addr}

            for k in (
                "lsr-id", "transport-address", "source-address",
                "interface", "uptime", "adjacency-type",
            ):
                if k in state:
                    entry[k] = state[k]

            for k in (
                "version", "label-space-id", "holdtime", "reset-count",
            ):
                if k in state:
                    entry[k] = state[k]

            result["hello-adjacencies"][key] = entry

        return result


# =====================================================================
# ShowLdpNeighbor
# =====================================================================

class ShowLdpNeighborSchema(MetaParser):
    """Schema for LDP neighbors."""

    schema = {
        "neighbors": {
            Any(): {  # "lsr-id/label-space-id"
                "lsr-id": str,
                "label-space-id": int,
                Optional("auth-enable"): bool,
                Optional("maximum-remote-binding"): int,
                Optional("targeted-hello-holdtime"): int,
                Optional("targeted-hello-interval"): int,
                Optional("targeted-address-families"): {
                    Any(): {  # afi-name
                        "afi-name": str,
                        Optional("enabled"): bool,
                        Optional("destination-address"): str,
                    }
                },
            }
        }
    }


class ShowLdpNeighbor(ShowLdpNeighborSchema):
    """Parser for ArcOS LDP neighbors (JSON format)."""

    cli_command = (
        "show network-instance default mpls signaling-protocols ldp "
        "neighbor"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        ldp = _navigate_to_ldp(parsed)

        nbr_container = ldp.get("neighbors", {})
        nbr_list = nbr_container.get("neighbor", [])

        if not nbr_list:
            raise SchemaEmptyParserError("No LDP neighbor data found")

        result = {"neighbors": {}}

        for nbr in nbr_list:
            lsr_id = nbr.get("lsr-id")
            label_space_id = nbr.get("label-space-id", 0)
            if not lsr_id:
                continue

            key = f"{lsr_id}/{label_space_id}"

            entry = {
                "lsr-id": lsr_id,
                "label-space-id": label_space_id,
            }

            # Authentication
            auth = nbr.get("authentication", {})
            auth_state = auth.get("state", {})
            if "enable" in auth_state:
                entry["auth-enable"] = auth_state["enable"]

            # Max remote binding (arcOS augment)
            mrb = nbr.get(
                "arcos-openconfig-network-instance-augments:max-remote-binding",
                {},
            )
            mrb_state = mrb.get("state", {})
            if "maximum-remote-binding" in mrb_state:
                entry["maximum-remote-binding"] = mrb_state[
                    "maximum-remote-binding"
                ]

            # Targeted (arcOS augment)
            targeted = nbr.get(
                "arcos-openconfig-network-instance-augments:targeted", {}
            )

            targeted_state = targeted.get("state", {})
            if "hello-holdtime" in targeted_state:
                entry["targeted-hello-holdtime"] = targeted_state[
                    "hello-holdtime"
                ]
            if "hello-interval" in targeted_state:
                entry["targeted-hello-interval"] = targeted_state[
                    "hello-interval"
                ]

            # Targeted address families
            af_list = targeted.get("address-family", [])
            if af_list:
                entry["targeted-address-families"] = {}
                for af in af_list:
                    af_name = af.get("afi-name")
                    if not af_name:
                        continue
                    af_state = af.get("state", {})
                    af_entry = {"afi-name": af_name}
                    if "enabled" in af_state:
                        af_entry["enabled"] = af_state["enabled"]
                    if "destination-address" in af_state:
                        af_entry["destination-address"] = af_state[
                            "destination-address"
                        ]
                    entry["targeted-address-families"][af_name] = af_entry

            result["neighbors"][key] = entry

        return result
