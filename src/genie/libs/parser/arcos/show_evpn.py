"""show_evpn.py

ArcOS parsers for the following show commands:
    * show evpn
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import ARCOS_EVPN
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowEvpnSchema(MetaParser):
    """Schema for ArcOS ``show evpn`` output."""

    schema = {
        Optional("anycast-gateway-mac"): str,
        Optional("df-election-time"): Or(str, int),
        Optional("router-ip-selected"): str,
        Optional("esi-info"): {
            Optional("esi-pruned-pkts"): Or(str, int),
            Optional("esi-pruned-octets"): Or(str, int),
        },
        Optional("duplicate-mac-detection"): {
            Optional("window"): Or(str, int),
            Optional("threshold"): Or(str, int),
            Optional("auto-recovery-time"): Or(str, int),
        },
        Optional("arp-nd-suppression-counters"): {
            Optional("arp-suppression-counters"): Or(str, int),
            Optional("nd-suppression-counters"): Or(str, int),
        },
    }


class ShowEvpn(ShowEvpnSchema):
    """Parser for ArcOS ``show evpn`` (JSON format).

    The parser expects JSON of the form::

        data["arcos-evpn:evpn"]

    Flattens ``state``, ``esi-info.counters``,
    ``duplicate-mac-detection.state``, and
    ``arp-nd-supression-counters`` into a single dict.

    When no explicit output is provided, the parser runs::

        show evpn | display json | nomore
    """

    cli_command = "show evpn"

    def cli(self, output: TypeOptional[TypeAny] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowEvpn: empty output")

        parsed_json = load_json_robust(output)
        result = self._parse_evpn(parsed_json)

        if not result:
            raise SchemaEmptyParserError("No EVPN data found in output")

        return result

    def _parse_evpn(self, json_data: Dict) -> Dict[str, TypeAny]:
        """Extract EVPN state from arcOS JSON."""
        data = json_data.get("data", {})
        evpn = data.get(ARCOS_EVPN, {})

        if not evpn:
            return {}

        result: Dict[str, TypeAny] = {}

        # Flatten state fields
        state = evpn.get("state", {})
        for key in ("anycast-gateway-mac", "df-election-time",
                     "router-ip-selected"):
            if key in state:
                result[key] = state[key]

        # Flatten esi-info.counters
        esi_info = evpn.get("esi-info", {})
        counters = esi_info.get("counters", {})
        if counters:
            result["esi-info"] = {
                "esi-pruned-pkts": counters.get("esi-pruned-pkts"),
                "esi-pruned-octets": counters.get("esi-pruned-octets"),
            }
            # Remove None values
            result["esi-info"] = {
                k: v for k, v in result["esi-info"].items() if v is not None
            }

        # Flatten duplicate-mac-detection.state
        dmd = evpn.get("duplicate-mac-detection", {})
        dmd_state = dmd.get("state", {})
        if dmd_state:
            result["duplicate-mac-detection"] = {}
            for key in ("window", "threshold", "auto-recovery-time"):
                if key in dmd_state:
                    result["duplicate-mac-detection"][key] = dmd_state[key]

        # Flatten arp-nd-supression-counters
        # Note: arcOS JSON has typo "supression" — we normalize to "suppression"
        arp_nd = evpn.get("arp-nd-supression-counters", {})
        if arp_nd:
            result["arp-nd-suppression-counters"] = {}
            # Map from typo keys to normalized keys
            key_map = {
                "arp-supression-counters": "arp-suppression-counters",
                "nd-supression-counters": "nd-suppression-counters",
            }
            for src_key, dst_key in key_map.items():
                if src_key in arp_nd:
                    result["arp-nd-suppression-counters"][dst_key] = (
                        arp_nd[src_key]
                    )

        return result
