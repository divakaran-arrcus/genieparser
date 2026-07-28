"""ArcOS BGP L3VPN parsers using JSON output.

Parsers:
1. ShowBgpDeaggregationLabel — deaggregation label state across VRFs
2. ShowBgpVpnExportedRoutes — VPN exported routes (L3VPN_IPV4/IPV6_UNICAST)
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import OPENCONFIG_NETWORK_INSTANCES
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)

_BGP_AUG_PREFIX = "arcos-openconfig-bgp-augments"
_BGP_TYPES_PREFIX = "openconfig-bgp-types:"
_POLICY_TYPES_PREFIX = "openconfig-policy-types:"


def _strip_prefixes(val):
    """Strip common namespace prefixes from a string value."""
    if not isinstance(val, str):
        return val
    for prefix in (f"{_BGP_AUG_PREFIX}:", _BGP_TYPES_PREFIX,
                   _POLICY_TYPES_PREFIX, "arcos-openconfig-bgp-types:"):
        if val.startswith(prefix):
            val = val[len(prefix):]
    return val


# =====================================================================
# ShowBgpDeaggregationLabel
# =====================================================================

class ShowBgpDeaggregationLabelSchema(MetaParser):
    schema = {
        Optional("entries"): {
            Any(): {  # "vrf:afi-safi" key
                "network-instance": str,
                "afi-safi": str,
                Optional("deaggregation-label"): int,
            }
        }
    }


class ShowBgpDeaggregationLabel(ShowBgpDeaggregationLabelSchema):
    """Parser for BGP deaggregation label state.

    Command::

        show network-instance * protocol BGP * global afi-safi * state deaggregation-label
    """

    cli_command = (
        "show network-instance * protocol BGP * "
        "global afi-safi * state deaggregation-label"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowBgpDeaggregationLabel: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            raise SchemaEmptyParserError("No deaggregation label data found")

        result = {"entries": {}}

        for ni in ni_list:
            ni_name = ni.get("name", "")
            protocols = ni.get("protocols", {}).get("protocol", [])

            for proto in protocols:
                ident = proto.get("identifier", "")
                if "BGP" not in ident:
                    continue

                bgp = proto.get("bgp", {})
                global_data = bgp.get("global", {})
                afi_safis = global_data.get("afi-safis", {}).get("afi-safi", [])

                for af in afi_safis:
                    raw_name = af.get("afi-safi-name", "")
                    name = _strip_prefixes(raw_name)
                    state = af.get("state", {})

                    deagg = state.get("deaggregation-label")
                    if deagg is not None:
                        key = f"{ni_name}:{name}"
                        result["entries"][key] = {
                            "network-instance": ni_name,
                            "afi-safi": name,
                            "deaggregation-label": deagg,
                        }

        if not result["entries"]:
            raise SchemaEmptyParserError("No deaggregation label data found")

        return result


# =====================================================================
# ShowBgpVpnExportedRoutes
# =====================================================================

class ShowBgpVpnExportedRoutesSchema(MetaParser):
    schema = {
        Optional("routes"): {
            Any(): {  # route prefix key
                "prefix": str,
                Optional("network-instance"): str,
                Optional("path-id"): int,
                Optional("next-hop"): str,
                Optional("local-label"): int,
                Optional("remote-label"): int,
                Optional("path-types"): str,
            }
        }
    }


class ShowBgpVpnExportedRoutes(ShowBgpVpnExportedRoutesSchema):
    """Parser for BGP VPN exported routes.

    Command::

        show network-instance default protocol BGP default rib
            afi-safi {afi_safi} network-instance {vrf} exported-rib route
    """

    cli_command = (
        "show network-instance default protocol BGP default rib "
        "afi-safi {afi_safi} network-instance {vrf_name} exported-rib route"
    )

    def cli(self, afi_safi="L3VPN_IPV4_UNICAST", vrf_name="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance default protocol BGP default rib "
                f"afi-safi {afi_safi} network-instance {vrf_name} "
                f"exported-rib route | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowBgpVpnExportedRoutes: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            raise SchemaEmptyParserError("No VPN exported route data found")

        result = {"routes": {}}

        for ni in ni_list:
            protocols = ni.get("protocols", {}).get("protocol", [])
            for proto in protocols:
                ident = proto.get("identifier", "")
                if "BGP" not in ident:
                    continue

                bgp = proto.get("bgp", {})
                rib = bgp.get("rib", {})
                afi_safis = rib.get("afi-safis", {}).get("afi-safi", [])

                for af in afi_safis:
                    ni_routes = af.get("network-instances",
                                       af.get(f"{_BGP_AUG_PREFIX}:network-instances", {}))
                    ni_entries = ni_routes.get("network-instance", [])
                    if isinstance(ni_entries, dict):
                        ni_entries = [ni_entries]

                    for ni_entry in ni_entries:
                        vrf = ni_entry.get("name", "")
                        exported = ni_entry.get("exported-rib",
                                                ni_entry.get(f"{_BGP_AUG_PREFIX}:exported-rib", {}))
                        routes = exported.get("route", exported.get("routes", []))
                        if isinstance(routes, dict):
                            routes = [routes]

                        for route in routes:
                            state = route.get("state", route)
                            prefix = state.get("prefix", route.get("prefix", ""))
                            if not prefix:
                                continue

                            entry = {"prefix": prefix}
                            if vrf:
                                entry["network-instance"] = vrf

                            if "path-id" in state:
                                entry["path-id"] = state["path-id"]
                            if "next-hop" in state:
                                entry["next-hop"] = state["next-hop"]
                            if "local-label" in state:
                                entry["local-label"] = state["local-label"]
                            if "remote-label" in state:
                                entry["remote-label"] = state["remote-label"]
                            pt = state.get("path-types", "")
                            if pt:
                                entry["path-types"] = _strip_prefixes(str(pt))

                            key = f"{vrf}:{prefix}" if vrf else prefix
                            result["routes"][key] = entry

        if not result["routes"]:
            raise SchemaEmptyParserError("No VPN exported route data found")

        return result
