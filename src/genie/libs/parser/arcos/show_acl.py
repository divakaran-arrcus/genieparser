"""ArcOS ACL parser using OpenConfig JSON output.

Parser:

ShowAclSet
    ``show acl acl-set {name} {acl_type} | display json | nomore``

Returns per-ACL-set state with entries, match criteria, actions, and counters.
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowAclSetSchema(MetaParser):
    """Schema for ``show acl acl-set`` output."""

    schema = {
        "acl-sets": {
            Any(): {  # "name type" key
                "name": str,
                "type": str,
                Optional("description"): str,
                Optional("acl-entries"): {
                    Any(): {  # sequence-id
                        "sequence-id": str,
                        Optional("description"): str,
                        Optional("priority"): int,
                        Optional("ipv4-source-address"): str,
                        Optional("ipv4-destination-address"): str,
                        Optional("ipv4-source-address-prefix-set"): str,
                        Optional("ipv4-destination-address-prefix-set"): str,
                        Optional("ipv4-protocol"): str,
                        Optional("ipv4-dscp"): str,
                        Optional("ipv6-source-address"): str,
                        Optional("ipv6-destination-address"): str,
                        Optional("ipv6-source-address-prefix-set"): str,
                        Optional("ipv6-destination-address-prefix-set"): str,
                        Optional("ipv6-protocol"): str,
                        Optional("ipv6-dscp"): str,
                        Optional("l2-source-mac"): str,
                        Optional("l2-source-mac-mask"): str,
                        Optional("l2-destination-mac"): str,
                        Optional("l2-destination-mac-mask"): str,
                        Optional("l2-ethertype"): str,
                        Optional("transport-source-port"): str,
                        Optional("transport-destination-port"): str,
                        Optional("forwarding-action"): str,
                        Optional("log-action"): str,
                        Optional("matched-ingress-packets"): str,
                        Optional("matched-egress-packets"): str,
                        Optional("matched-ingress-octets"): str,
                        Optional("matched-egress-octets"): str,
                    }
                },
            }
        }
    }


class ShowAclSet(ShowAclSetSchema):
    """Parser for ArcOS ``show acl acl-set`` (JSON format).

    Supports specific ACL: ``show acl acl-set <name> <type>``
    or all ACLs: ``show acl acl-set``
    """

    cli_command = [
        "show acl acl-set {name} {acl_type}",
        "show acl acl-set",
    ]

    def cli(
        self,
        name: TypeOptional[str] = None,
        acl_type: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            if name and acl_type:
                cmd = f"show acl acl-set {name} {acl_type} | display json | nomore"
            else:
                cmd = "show acl acl-set | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        acl_root = data.get("openconfig-acl:acl", {})
        acl_sets_container = acl_root.get("acl-sets", {})
        acl_set_list = acl_sets_container.get("acl-set", [])

        if not acl_set_list:
            raise SchemaEmptyParserError("No ACL set data found")

        result = {"acl-sets": {}}

        for acl_set in acl_set_list:
            set_name = acl_set.get("name")
            set_type_raw = acl_set.get("type", "")
            # Strip OC prefix: "openconfig-acl:ACL_IPV4" → "ACL_IPV4"
            set_type = set_type_raw.split(":")[-1] if ":" in set_type_raw else set_type_raw

            if not set_name:
                continue

            set_key = f"{set_name} {set_type}"

            state = acl_set.get("state", {})
            entry = {
                "name": set_name,
                "type": set_type,
            }

            if "description" in state:
                entry["description"] = state["description"]

            # ACL entries
            entries_container = acl_set.get("acl-entries", {})
            entry_list = entries_container.get("acl-entry", [])
            if entry_list:
                entry["acl-entries"] = {}
                for ace in entry_list:
                    seq_id = ace.get("sequence-id")
                    if seq_id is None:
                        continue

                    ace_state = ace.get("state", {})
                    ace_entry = {
                        "sequence-id": str(seq_id),
                    }

                    if "description" in ace_state:
                        ace_entry["description"] = ace_state["description"]

                    # Priority (augment)
                    prio = ace_state.get("arcos-openconfig-acl-augments:priority")
                    if prio is not None:
                        ace_entry["priority"] = prio

                    # Counters (augments)
                    for counter_key in (
                        "matched-ingress-packets", "matched-egress-packets",
                        "matched-ingress-octets", "matched-egress-octets",
                    ):
                        aug_key = f"arcos-openconfig-acl-augments:{counter_key}"
                        if aug_key in ace_state:
                            ace_entry[counter_key] = ace_state[aug_key]

                    # Helper to strip OC prefix
                    def _strip(val):
                        return val.split(":")[-1] if ":" in val else val

                    # IPv4 match
                    ipv4 = ace.get("ipv4", {})
                    ipv4_state = ipv4.get("state", {})
                    if "source-address" in ipv4_state:
                        ace_entry["ipv4-source-address"] = ipv4_state["source-address"]
                    if "destination-address" in ipv4_state:
                        ace_entry["ipv4-destination-address"] = ipv4_state["destination-address"]
                    # Prefix-set references (augment)
                    src_pfx_set = ipv4_state.get(
                        "arcos-openconfig-packet-match-augments:source-address-prefix-set"
                    )
                    if src_pfx_set:
                        ace_entry["ipv4-source-address-prefix-set"] = src_pfx_set
                    dst_pfx_set = ipv4_state.get(
                        "arcos-openconfig-packet-match-augments:destination-address-prefix-set"
                    )
                    if dst_pfx_set:
                        ace_entry["ipv4-destination-address-prefix-set"] = dst_pfx_set
                    if "protocol" in ipv4_state:
                        ace_entry["ipv4-protocol"] = _strip(ipv4_state["protocol"])
                    if "dscp" in ipv4_state:
                        ace_entry["ipv4-dscp"] = ipv4_state["dscp"]

                    # IPv6 match
                    ipv6 = ace.get("ipv6", {})
                    ipv6_state = ipv6.get("state", {})
                    if "source-address" in ipv6_state:
                        ace_entry["ipv6-source-address"] = ipv6_state["source-address"]
                    if "destination-address" in ipv6_state:
                        ace_entry["ipv6-destination-address"] = ipv6_state["destination-address"]
                    src_pfx_set6 = ipv6_state.get(
                        "arcos-openconfig-packet-match-augments:source-address-prefix-set"
                    )
                    if src_pfx_set6:
                        ace_entry["ipv6-source-address-prefix-set"] = src_pfx_set6
                    dst_pfx_set6 = ipv6_state.get(
                        "arcos-openconfig-packet-match-augments:destination-address-prefix-set"
                    )
                    if dst_pfx_set6:
                        ace_entry["ipv6-destination-address-prefix-set"] = dst_pfx_set6
                    if "protocol" in ipv6_state:
                        ace_entry["ipv6-protocol"] = _strip(ipv6_state["protocol"])
                    if "dscp" in ipv6_state:
                        ace_entry["ipv6-dscp"] = ipv6_state["dscp"]

                    # L2 match
                    l2 = ace.get("l2", {})
                    l2_state = l2.get("state", {})
                    if "source-mac" in l2_state:
                        ace_entry["l2-source-mac"] = l2_state["source-mac"]
                    if "source-mac-mask" in l2_state:
                        ace_entry["l2-source-mac-mask"] = l2_state["source-mac-mask"]
                    if "destination-mac" in l2_state:
                        ace_entry["l2-destination-mac"] = l2_state["destination-mac"]
                    if "destination-mac-mask" in l2_state:
                        ace_entry["l2-destination-mac-mask"] = l2_state["destination-mac-mask"]
                    if "ethertype" in l2_state:
                        ace_entry["l2-ethertype"] = _strip(l2_state["ethertype"])

                    # Transport match
                    transport = ace.get("transport", {})
                    transport_state = transport.get("state", {})
                    if "source-port" in transport_state:
                        ace_entry["transport-source-port"] = str(transport_state["source-port"])
                    if "destination-port" in transport_state:
                        ace_entry["transport-destination-port"] = str(transport_state["destination-port"])

                    # Actions
                    actions = ace.get("actions", {})
                    actions_state = actions.get("state", {})
                    fwd = actions_state.get("forwarding-action", "")
                    if fwd:
                        ace_entry["forwarding-action"] = fwd.split(":")[-1] if ":" in fwd else fwd
                    log_act = actions_state.get("log-action", "")
                    if log_act:
                        ace_entry["log-action"] = log_act.split(":")[-1] if ":" in log_act else log_act

                    entry["acl-entries"][str(seq_id)] = ace_entry

            result["acl-sets"][set_key] = entry

        return result
