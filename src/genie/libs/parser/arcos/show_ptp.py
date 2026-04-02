"""ArcOS PTP parser using JSON output.

Parser:
    ShowPtpInstance — ``show ptp instance-list <id> clock-info``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowPtpInstanceSchema(MetaParser):
    schema = {
        "instances": {
            Any(): {
                "instance-number": int,
                Optional("clock-profile"): str,
                Optional("clock-role"): str,
                Optional("domain-number"): int,
                Optional("priority2"): int,
            }
        }
    }


class ShowPtpInstance(ShowPtpInstanceSchema):
    """Parser for PTP instance info."""

    cli_command = "show ptp instance-list {instance_id} clock-info"

    def cli(self, instance_id="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show ptp instance-list {instance_id} clock-info | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})
        ptp = data.get("arcos-ptp:ptp", data.get("ptp", {}))

        instances = ptp.get("instance-list", [])
        if not instances:
            raise SchemaEmptyParserError("No PTP instance data found")

        if isinstance(instances, dict):
            instances = [instances]

        result = {"instances": {}}
        for inst in instances:
            inst_num = inst.get("instance-number", 0)
            state = inst.get("state", inst.get("config", inst))
            entry = {"instance-number": inst_num}

            if "clock-profile" in state:
                entry["clock-profile"] = state["clock-profile"]
            if "clock-role" in state:
                entry["clock-role"] = state["clock-role"]

            ds = inst.get("default-ds", {}).get("state", inst.get("default-ds", {}))
            if "domain-number" in ds:
                entry["domain-number"] = ds["domain-number"]
            if "priority2" in ds:
                entry["priority2"] = ds["priority2"]

            result["instances"][str(inst_num)] = entry

        if not result["instances"]:
            raise SchemaEmptyParserError("No PTP instance data found")

        return result
