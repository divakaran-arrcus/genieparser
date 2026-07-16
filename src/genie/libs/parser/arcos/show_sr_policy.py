"""ArcOS SR-Policy parsers using OpenConfig JSON output.

Three parsers:

1. ShowSrPolicySegmentList
   ``show network-instance default sr-policy segment-list``

2. ShowSrPolicyPolicy
   ``show network-instance default sr-policy policy``

3. ShowSrPolicyDatabasePolicy
   ``show network-instance default sr-policy database policy``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


def _navigate_to_sr_policy(parsed: Dict) -> Dict:
    """Navigate to the sr-policy container."""
    data = parsed.get("data", {})
    ni_container = data.get("openconfig-network-instance:network-instances", {})
    ni_list = ni_container.get("network-instance", [])
    if not ni_list:
        return {}
    ni = ni_list[0]
    return ni.get("arcos-sr-policy:sr-policy", {})


# =====================================================================
# ShowSrPolicySegmentList
# =====================================================================

class ShowSrPolicySegmentListSchema(MetaParser):
    """Schema for SR-Policy segment-list."""

    schema = {
        "segment-lists": {
            Any(): {  # segment-list name
                "name": str,
                Optional("index"): int,
                Optional("segments"): {
                    Any(): {  # segment index (as str key)
                        "index": int,
                        Optional("type"): str,
                        Optional("validate"): bool,
                        Optional("mpls-label"): int,
                        Optional("srv6-sid"): str,
                    }
                },
            }
        }
    }


class ShowSrPolicySegmentList(ShowSrPolicySegmentListSchema):
    """Parser for ``show network-instance default sr-policy segment-list``."""

    cli_command = (
        "show network-instance default sr-policy segment-list"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSrPolicySegmentList: empty output")

        parsed = load_json_robust(output)
        sr = _navigate_to_sr_policy(parsed)
        sl_container = sr.get("segment-lists", {})
        sl_list = sl_container.get("segment-list", [])

        if not sl_list:
            raise SchemaEmptyParserError("No SR-Policy segment-list data")

        result = {"segment-lists": {}}

        for sl in sl_list:
            sl_name = sl.get("name")
            if not sl_name:
                continue

            state = sl.get("state", {})
            entry = {
                "name": sl_name,
            }

            if "index" in state:
                entry["index"] = state["index"]

            # Segments
            seg_container = sl.get("segments", {})
            seg_list = seg_container.get("segment", [])
            if seg_list:
                entry["segments"] = {}
                for seg in seg_list:
                    seg_idx = seg.get("index")
                    if seg_idx is None:
                        continue

                    seg_state = seg.get("state", {})
                    seg_entry = {
                        "index": seg_idx,
                    }

                    if "type" in seg_state:
                        seg_entry["type"] = seg_state["type"]
                    if "validate" in seg_state:
                        seg_entry["validate"] = seg_state["validate"]

                    # MPLS label
                    mpls = seg.get("segment-mpls-label", {})
                    mpls_state = mpls.get("state", {})
                    if "mpls-label" in mpls_state:
                        seg_entry["mpls-label"] = mpls_state["mpls-label"]

                    # SRv6 SID
                    srv6 = seg.get("segment-srv6-sid", {})
                    srv6_state = srv6.get("state", {})
                    if "srv6-sid" in srv6_state:
                        seg_entry["srv6-sid"] = srv6_state["srv6-sid"]

                    entry["segments"][str(seg_idx)] = seg_entry

            result["segment-lists"][sl_name] = entry

        return result


# =====================================================================
# ShowSrPolicyPolicy
# =====================================================================

class ShowSrPolicyPolicySchema(MetaParser):
    """Schema for SR-Policy policy (configuration state)."""

    schema = {
        "policies": {
            Any(): {  # "endpoint color" key
                "endpoint": str,
                "color": int,
                Optional("name"): str,
                Optional("description"): str,
                Optional("enabled"): bool,
                Optional("priority"): int,
                Optional("candidate-paths"): {
                    Any(): {  # discriminator as str key
                        "discriminator": int,
                        Optional("preference"): int,
                        Optional("type"): str,
                        Optional("originator-as"): int,
                        Optional("originator-address"): str,
                        Optional("explicit-segment-lists"): list,
                    }
                },
            }
        }
    }


class ShowSrPolicyPolicy(ShowSrPolicyPolicySchema):
    """Parser for ``show network-instance default sr-policy policy``."""

    cli_command = (
        "show network-instance default sr-policy policy"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSrPolicyPolicy: empty output")

        parsed = load_json_robust(output)
        sr = _navigate_to_sr_policy(parsed)
        pol_container = sr.get("policies", {})
        pol_list = pol_container.get("policy", [])

        if not pol_list:
            raise SchemaEmptyParserError("No SR-Policy policy data")

        result = {"policies": {}}

        for pol in pol_list:
            endpoint = pol.get("endpoint")
            color = pol.get("color")
            if not endpoint or color is None:
                continue

            pol_key = f"{endpoint} {color}"
            state = pol.get("state", {})

            entry = {
                "endpoint": endpoint,
                "color": color,
            }

            for key in ("name", "description"):
                if key in state:
                    entry[key] = state[key]

            if "enabled" in state:
                entry["enabled"] = state["enabled"]
            if "priority" in state:
                entry["priority"] = state["priority"]

            # Candidate paths
            cp_container = pol.get("candidate-paths", {})
            cp_list = cp_container.get("candidate-path", [])
            if cp_list:
                entry["candidate-paths"] = {}
                for cp in cp_list:
                    disc = cp.get("discriminator")
                    if disc is None:
                        continue

                    cp_state = cp.get("state", {})
                    cp_entry = {
                        "discriminator": disc,
                    }

                    for k in ("preference", "originator-as"):
                        if k in cp_state:
                            cp_entry[k] = cp_state[k]

                    for k in ("type", "originator-address"):
                        if k in cp_state:
                            cp_entry[k] = cp_state[k]

                    # Explicit segment-lists
                    explicit = cp.get("explicit", {})
                    exp_sls = explicit.get("segment-lists", {})
                    exp_sl_list = exp_sls.get("segment-list", [])
                    if exp_sl_list:
                        cp_entry["explicit-segment-lists"] = [
                            sl.get("name") or sl.get("state", {}).get("name")
                            for sl in exp_sl_list
                            if sl.get("name") or sl.get("state", {}).get("name")
                        ]

                    entry["candidate-paths"][str(disc)] = cp_entry

            result["policies"][pol_key] = entry

        return result


# =====================================================================
# ShowSrPolicyDatabasePolicy
# =====================================================================

class ShowSrPolicyDatabasePolicySchema(MetaParser):
    """Schema for SR-Policy database policy (operational state)."""

    schema = {
        "policies": {
            Any(): {  # "endpoint color" key
                "endpoint": str,
                "color": int,
                Optional("oper-state"): str,
                Optional("transition-count"): int,
                Optional("up-time"): str,
                Optional("down-time"): str,
                Optional("candidate-paths"): {
                    Any(): {  # "origin:originator:disc" key
                        "protocol-origin": str,
                        "originator": str,
                        "discriminator": int,
                        Optional("preference"): int,
                        Optional("type"): str,
                        Optional("best-candidate-path"): bool,
                        Optional("valid"): bool,
                        Optional("segment-lists"): list,
                    }
                },
            }
        }
    }


class ShowSrPolicyDatabasePolicy(ShowSrPolicyDatabasePolicySchema):
    """Parser for ``show network-instance default sr-policy database policy``."""

    cli_command = (
        "show network-instance default sr-policy database policy"
    )

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSrPolicyDatabasePolicy: empty output")

        parsed = load_json_robust(output)
        sr = _navigate_to_sr_policy(parsed)
        db = sr.get("database", {})
        pol_container = db.get("policies", {})
        pol_list = pol_container.get("policy", [])

        if not pol_list:
            raise SchemaEmptyParserError("No SR-Policy database policy data")

        result = {"policies": {}}

        for pol in pol_list:
            endpoint = pol.get("endpoint")
            color = pol.get("color")
            if not endpoint or color is None:
                continue

            pol_key = f"{endpoint} {color}"
            state = pol.get("state", {})

            entry = {
                "endpoint": endpoint,
                "color": color,
            }

            if "oper-state" in state:
                entry["oper-state"] = state["oper-state"]
            if "transition-count" in state:
                entry["transition-count"] = state["transition-count"]
            if "up-time" in state:
                entry["up-time"] = state["up-time"]
            if "down-time" in state:
                entry["down-time"] = state["down-time"]

            # Candidate paths
            cp_container = pol.get("candidate-paths", {})
            cp_list = cp_container.get("candidate-path", [])
            if cp_list:
                entry["candidate-paths"] = {}
                for cp in cp_list:
                    origin = cp.get("protocol-origin", "")
                    originator = cp.get("originator", "")
                    disc = cp.get("discriminator")
                    if disc is None:
                        continue

                    cp_key = f"{origin}:{originator}:{disc}"
                    cp_state = cp.get("state", {})

                    cp_entry = {
                        "protocol-origin": cp_state.get("protocol-origin", origin),
                        "originator": cp_state.get("originator", originator),
                        "discriminator": disc,
                    }

                    if "preference" in cp_state:
                        cp_entry["preference"] = cp_state["preference"]
                    if "type" in cp_state:
                        cp_entry["type"] = cp_state["type"]
                    if "best-candidate-path" in cp_state:
                        cp_entry["best-candidate-path"] = cp_state["best-candidate-path"]
                    if "valid" in cp_state:
                        cp_entry["valid"] = cp_state["valid"]

                    # Segment lists in candidate path
                    sl_container = cp.get("segment-lists", {})
                    sl_list = sl_container.get("segment-list", [])
                    if sl_list:
                        cp_entry["segment-lists"] = []
                        for sl in sl_list:
                            sl_state = sl.get("state", {})
                            cp_entry["segment-lists"].append({
                                "index": sl.get("index"),
                                "name": sl_state.get("name"),
                                "valid": sl_state.get("valid"),
                            })

                    entry["candidate-paths"][cp_key] = cp_entry

            result["policies"][pol_key] = entry

        return result
