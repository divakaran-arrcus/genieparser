"""ArcOS System parser using JSON output.

Parser:
    ShowSystemHostname — ``show system hostname``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowSystemHostnameSchema(MetaParser):
    schema = {
        Optional("hostname"): str,
    }


class ShowSystemHostname(ShowSystemHostnameSchema):
    """Parser for system hostname."""

    cli_command = "show system hostname"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show system hostname | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowSystemHostname: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        sys_data = data.get("openconfig-system:system", {})
        if not sys_data:
            sys_data = data.get("system", {})

        config = sys_data.get("config", sys_data.get("state", {}))

        if not config:
            raise SchemaEmptyParserError("No system hostname data found")

        result = {}
        hostname = config.get("hostname")
        if hostname:
            result["hostname"] = hostname
        else:
            raise SchemaEmptyParserError("No hostname found")

        return result
