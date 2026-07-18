"""ArcOS RSVP-TE parser using JSON output.

Parser:
    ShowRsvpGlobal — ``show network-instance default protocol RSVP default global state``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


def _navigate_to_rsvp(parsed: Dict) -> Dict:
    """Navigate to the RSVP container."""
    data = parsed.get("data", {})
    ni_container = data.get("openconfig-network-instance:network-instances", {})
    ni_list = ni_container.get("network-instance", [])
    if not ni_list:
        return {}
    ni = ni_list[0]
    protocols = ni.get("protocols", {}).get("protocol", [])
    for p in protocols:
        for key in p:
            if "rsvp" in key.lower():
                return p[key]
    return {}


class ShowRsvpGlobalSchema(MetaParser):
    schema = {
        Optional("hello-supported"): bool,
        Optional("hello-interval"): int,
        Optional("refresh-reduction"): bool,
    }


class ShowRsvpGlobal(ShowRsvpGlobalSchema):
    """Parser for RSVP-TE global state."""

    cli_command = (
        "show network-instance {ni} protocol RSVP {instance} global state"
    )

    def cli(self, ni="default", instance="default",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = (
                f"show network-instance {ni} protocol RSVP {instance} "
                f"global state | display json | nomore"
            )
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowRsvpGlobal: empty output")

        parsed = load_json_robust(output)
        rsvp = _navigate_to_rsvp(parsed)
        state = rsvp.get("global", {}).get("state", {})

        if not state:
            raise SchemaEmptyParserError("No RSVP global state found")

        result = {}

        if "hello-supported" in state:
            result["hello-supported"] = state["hello-supported"]
        if "hello-interval" in state:
            result["hello-interval"] = state["hello-interval"]
        if "refresh-reduction" in state:
            result["refresh-reduction"] = state["refresh-reduction"]

        if not result:
            raise SchemaEmptyParserError("No RSVP global state found")

        return result
