"""ArcOS IPFIX parser using JSON output.

Parser:
    ShowIpfix — ``show ipfix``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowIpfixSchema(MetaParser):
    schema = {
        Optional("observation-points"): {
            Any(): {
                "name": str,
                Optional("observation-domain-id"): int,
            }
        },
        Optional("exporting-processes"): {
            Any(): {
                "name": str,
                Optional("destinations"): {
                    Any(): {
                        "name": str,
                        Optional("destination-address"): str,
                        Optional("destination-port"): int,
                        Optional("packets-sent"): int,
                        Optional("packets-dropped"): int,
                    }
                },
            }
        },
    }


class ShowIpfix(ShowIpfixSchema):
    """Parser for IPFIX state."""

    cli_command = "show ipfix"

    def cli(self, output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = "show ipfix | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowIpfix: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        ipfix = data.get("arcos-ipfix:ipfix", data.get("ipfix", {}))

        if not ipfix:
            raise SchemaEmptyParserError("No IPFIX data found")

        result = {}

        obs_list = ipfix.get("observationPoint", [])
        if obs_list:
            if isinstance(obs_list, dict):
                obs_list = [obs_list]
            result["observation-points"] = {}
            for obs in obs_list:
                name = obs.get("name", "")
                if not name:
                    continue
                entry = {"name": name}
                state = obs.get("state", obs.get("config", obs))
                if "observationDomainId" in state:
                    entry["observation-domain-id"] = state["observationDomainId"]
                result["observation-points"][name] = entry

        exp_list = ipfix.get("exportingProcess", [])
        if exp_list:
            if isinstance(exp_list, dict):
                exp_list = [exp_list]
            result["exporting-processes"] = {}
            for exp in exp_list:
                name = exp.get("name", "")
                if not name:
                    continue
                entry = {"name": name}

                dests = exp.get("destination", [])
                if dests:
                    if isinstance(dests, dict):
                        dests = [dests]
                    entry["destinations"] = {}
                    for d in dests:
                        d_name = d.get("name", "")
                        if not d_name:
                            continue
                        d_entry = {"name": d_name}
                        udp = d.get("udpExporter", {})
                        ts = udp.get("transportSession", udp.get("state", {}))
                        if "destinationAddress" in ts:
                            d_entry["destination-address"] = ts["destinationAddress"]
                        if "destinationPort" in ts:
                            d_entry["destination-port"] = ts["destinationPort"]
                        if "packetsSent" in ts:
                            d_entry["packets-sent"] = ts["packetsSent"]
                        if "packetsDropped" in ts:
                            d_entry["packets-dropped"] = ts["packetsDropped"]
                        entry["destinations"][d_name] = d_entry

                result["exporting-processes"][name] = entry

        if not result:
            raise SchemaEmptyParserError("No IPFIX data found")

        return result
