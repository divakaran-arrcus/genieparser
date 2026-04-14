"""ArcOS NTP parser using JSON output.

Parser:
    ShowNtp — ``show system ntp``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowNtpSchema(MetaParser):
    """Schema for ArcOS ``show system ntp`` output."""

    schema = {
        Optional("network-instance"): str,
        Optional("associations"): {
            Any(): {  # NTP server address
                "address": str,
                Optional("stratum"): int,
                Optional("root-delay"): Or(str, int),
                Optional("root-dispersion"): Or(str, int),
                Optional("offset"): Or(str, int),
                Optional("poll-interval"): int,
                Optional("reach"): Or(str, int),
                Optional("time-since-last-response"): Or(str, int),
                Optional("association-status"): str,
            }
        },
    }


class ShowNtp(ShowNtpSchema):
    """Parser for ArcOS ``show system ntp`` (JSON format).

    Parses NTP state including server associations with stratum,
    delay, offset, poll, and association status.

    Command::

        show system ntp | display json | nomore
    """

    cli_command = "show system ntp"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show system ntp | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        sys_data = data.get("openconfig-system:system", {})
        if not sys_data:
            sys_data = data.get("system", {})

        ntp = sys_data.get("ntp", {})
        if not ntp:
            raise SchemaEmptyParserError("No NTP data found")

        result: Dict[str, TypeAny] = {}

        # Network instance from state
        state = ntp.get("state", {})
        ni = state.get("arcos-openconfig-system-augments:network-instance")
        if ni:
            result["network-instance"] = ni

        # NTP associations from augmented status list
        status_list = ntp.get("arcos-openconfig-system-augments:status", [])
        if status_list:
            associations: Dict[str, TypeAny] = {}
            for entry in status_list:
                addr = entry.get("address")
                if not addr:
                    continue

                assoc: Dict[str, TypeAny] = {"address": addr}

                for k in ("stratum", "root-delay", "root-dispersion",
                           "offset", "poll-interval", "reach",
                           "time-since-last-response",
                           "association-status"):
                    if k in entry:
                        assoc[k] = entry[k]

                associations[addr] = assoc

            if associations:
                result["associations"] = associations

        if not result:
            raise SchemaEmptyParserError("No NTP data found")

        return result
