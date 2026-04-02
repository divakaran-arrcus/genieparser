"""ArcOS Static VXLAN parser using JSON output.

Parser:
    ShowStaticVxlanTunnels — ``show overlay static-vxlan-tunnels``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowStaticVxlanTunnelsSchema(MetaParser):
    schema = {
        Optional("tunnels"): {
            Any(): {  # remote VTEP IP as key
                "remote-vtep": str,
                Optional("local-vtep"): str,
                Optional("state"): str,
                Optional("vnis"): list,
            }
        }
    }


class ShowStaticVxlanTunnels(ShowStaticVxlanTunnelsSchema):
    """Parser for static VXLAN tunnels."""

    cli_command = "show overlay static-vxlan-tunnels"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show overlay static-vxlan-tunnels | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)
        data = parsed.get("data", {})

        overlay = data.get("arcos-overlay:overlay", data.get("overlay", {}))
        tunnels = overlay.get("static-vxlan-tunnels",
                              overlay.get("tunnel", []))

        if isinstance(tunnels, dict):
            tunnel_list = tunnels.get("tunnel", tunnels.get("static-vxlan-tunnel", []))
        else:
            tunnel_list = tunnels

        if isinstance(tunnel_list, dict):
            tunnel_list = [tunnel_list]

        if not tunnel_list:
            raise SchemaEmptyParserError("No static VXLAN tunnel data found")

        result = {"tunnels": {}}

        for t in tunnel_list:
            state = t.get("state", t)
            remote = state.get("remote-vtep", state.get("remote-ip", ""))
            if not remote:
                continue
            entry = {"remote-vtep": remote}
            if "local-vtep" in state:
                entry["local-vtep"] = state["local-vtep"]
            if "state" in state:
                entry["state"] = state["state"]
            if "vnis" in state:
                entry["vnis"] = state["vnis"] if isinstance(state["vnis"], list) else [state["vnis"]]
            result["tunnels"][remote] = entry

        if not result["tunnels"]:
            raise SchemaEmptyParserError("No static VXLAN tunnels found")

        return result
