"""ArcOS NAT parser using JSON output.

Parser:
    ShowNatInstance — ``show nat instance <id>``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowNatInstanceSchema(MetaParser):
    schema = {
        "instances": {
            Any(): {  # instance id
                "id": int,
                Optional("name"): str,
                Optional("enabled"): bool,
                Optional("type"): str,
                Optional("mapping-entries"): {
                    Any(): {
                        "id": int,
                        Optional("internal-src-address"): str,
                        Optional("total-packets"): int,
                        Optional("total-bytes"): int,
                    }
                },
                Optional("policies"): {
                    Any(): {
                        "id": int,
                        Optional("external-interface"): str,
                    }
                },
            }
        }
    }


class ShowNatInstance(ShowNatInstanceSchema):
    """Parser for NAT instance state."""

    cli_command = "show nat instance {instance_id}"

    def cli(self, instance_id="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show nat instance {instance_id} | display json | nomore"
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowNatInstance: empty output")

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        nat = data.get("arcos-nat:nat", data.get("nat", {}))

        instances = nat.get("instance", [])
        if not instances:
            raise SchemaEmptyParserError("No NAT instance data found")

        if isinstance(instances, dict):
            instances = [instances]

        result = {"instances": {}}

        for inst in instances:
            inst_id = inst.get("id", inst.get("instance-id", 0))
            state = inst.get("state", inst.get("config", inst))

            entry = {"id": inst_id}
            if "name" in state:
                entry["name"] = state["name"]
            if "enable" in state:
                entry["enabled"] = state["enable"]
            if "type" in state:
                entry["type"] = state["type"]

            mappings = inst.get("mapping-entry", [])
            if mappings:
                if isinstance(mappings, dict):
                    mappings = [mappings]
                entry["mapping-entries"] = {}
                for m in mappings:
                    m_id = m.get("id", m.get("entry-id", 0))
                    m_state = m.get("state", m.get("config", m))
                    m_entry = {"id": m_id}
                    if "internal-src-address" in m_state:
                        m_entry["internal-src-address"] = m_state["internal-src-address"]
                    if "total-packets" in m_state:
                        m_entry["total-packets"] = m_state["total-packets"]
                    if "total-bytes" in m_state:
                        m_entry["total-bytes"] = m_state["total-bytes"]
                    entry["mapping-entries"][str(m_id)] = m_entry

            policies = inst.get("policy", [])
            if policies:
                if isinstance(policies, dict):
                    policies = [policies]
                entry["policies"] = {}
                for p in policies:
                    p_id = p.get("id", p.get("policy-id", 0))
                    p_state = p.get("state", p.get("config", p))
                    p_entry = {"id": p_id}
                    if "external-interface" in p_state:
                        p_entry["external-interface"] = p_state["external-interface"]
                    entry["policies"][str(p_id)] = p_entry

            result["instances"][str(inst_id)] = entry

        if not result["instances"]:
            raise SchemaEmptyParserError("No NAT instance data found")

        return result
