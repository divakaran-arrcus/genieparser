"""ArcOS QoS policy parser using JSON output.

Parser:

ShowQosPolicy
    ``show qos policy {name} | display json | nomore``
    or ``show qos policy * | display json | nomore``

Returns per-policy state with classifiers and actions.
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowQosPolicySchema(MetaParser):
    """Schema for ``show qos policy`` output."""

    schema = {
        "policies": {
            Any(): {  # policy name
                "name": str,
                Optional("classifiers"): {
                    Any(): {  # classifier name
                        "name": str,
                        Optional("description"): str,
                        Optional("actions"): list,
                    }
                },
            }
        }
    }


class ShowQosPolicy(ShowQosPolicySchema):
    """Parser for ArcOS ``show qos policy`` (JSON format)."""

    cli_command = [
        "show qos policy {name}",
        "show qos policy",
    ]

    def cli(
        self,
        name: str = "*",
        output: TypeOptional[str] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            # Always use wildcard — arcOS doesn't support single-policy lookup
            cmd = "show qos policy * | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowQosPolicy: empty output")

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        qos_root = data.get("arcos-qos:qos", {})
        policies_container = qos_root.get("arcos-qos-policy:policies", {})
        policy_list = policies_container.get("policy", [])

        if not policy_list:
            raise SchemaEmptyParserError("No QoS policy data found")

        result = {"policies": {}}

        for pol in policy_list:
            pol_name = pol.get("name")
            if not pol_name:
                continue

            entry = {"name": pol_name}

            # Classifiers
            cls_container = pol.get("classifiers", {})
            cls_list = cls_container.get("classifier", [])
            if cls_list:
                entry["classifiers"] = {}
                for cls in cls_list:
                    cls_name = cls.get("name")
                    if not cls_name:
                        continue

                    cls_state = cls.get("state", {})
                    cls_entry = {
                        "name": cls_name,
                    }

                    desc = cls_state.get("description")
                    if desc:
                        cls_entry["description"] = desc

                    # Actions
                    actions_container = cls.get("actions", {})
                    action_list = actions_container.get("action", [])
                    if action_list:
                        cls_entry["actions"] = []
                        for act in action_list:
                            act_type_raw = act.get("type", "")
                            act_type = act_type_raw.split(":")[-1] if ":" in act_type_raw else act_type_raw

                            act_entry = {"type": act_type}

                            # Extract action-specific data
                            if act_type == "POLICE":
                                police = act.get("police", {}).get("state", {})
                                committed = police.get("committed", {})
                                rate = committed.get("rate", {})
                                if rate:
                                    act_entry["rate_value"] = rate.get("value")
                                    act_entry["rate_unit"] = rate.get("unit")
                                burst = committed.get("burst", {})
                                if burst:
                                    act_entry["burst_value"] = burst.get("value")
                                    act_entry["burst_unit"] = burst.get("unit")

                            elif act_type == "PRIORITY":
                                prio = act.get("priority", {}).get("state", {})
                                if "level" in prio:
                                    act_entry["level"] = prio["level"]

                            elif act_type == "RATE_MAX":
                                rm = act.get("rate-max", {}).get("state", {})
                                rate = rm.get("rate", {})
                                if rate:
                                    act_entry["rate_value"] = rate.get("value")
                                    act_entry["rate_unit"] = rate.get("unit")

                            elif act_type == "RATE_MIN":
                                rm = act.get("rate-min", {}).get("state", {})
                                rate = rm.get("rate", {})
                                if rate:
                                    act_entry["rate_value"] = rate.get("value")
                                    act_entry["rate_unit"] = rate.get("unit")

                            elif act_type == "RATE_EXCESS":
                                re = act.get("rate-excess", {}).get("state", {})
                                if "ratio" in re:
                                    act_entry["ratio"] = re["ratio"]

                            elif act_type == "MARKING":
                                mk = act.get("marking", {}).get("state", {})
                                if "local-tc" in mk:
                                    act_entry["local_tc"] = mk["local-tc"]

                            cls_entry["actions"].append(act_entry)

                    entry["classifiers"][cls_name] = cls_entry

            result["policies"][pol_name] = entry

        return result
