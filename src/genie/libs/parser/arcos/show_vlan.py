"""ArcOS show vlan parser using OpenConfig JSON output."""

import logging
from typing import Any as TypeAny, Dict, List, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import OPENCONFIG_VLANS
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowVlanSchema(MetaParser):
    """Schema for ArcOS ``show vlan`` output."""

    schema = {
        Optional("vlans"): {
            Any(): {  # vlan-id as string key
                Optional("vlan-id"): Or(str, int),
                Optional("name"): str,
                Optional("status"): str,
                Optional("members"): list,
            }
        }
    }


class ShowVlan(ShowVlanSchema):
    """Parser for ArcOS ``show vlan`` (JSON format).

    The parser expects OpenConfig JSON of the form::

        data["openconfig-vlan:vlans"]["vlan"][]

    Each VLAN entry is flattened: ``state`` fields are promoted to
    top level, and ``members`` is simplified to a list of interface
    names.

    When no explicit output is provided, the parser runs::

        show vlan | display json | nomore
    """

    cli_command = "show vlan"

    def cli(self, output: TypeOptional[TypeAny] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        parsed_json = load_json_robust(output)
        result = self._parse_vlans(parsed_json)

        if not result:
            raise SchemaEmptyParserError("No VLAN data found in output")

        return result

    def _parse_vlans(self, json_data: Dict) -> Dict[str, TypeAny]:
        """Extract VLANs from OpenConfig JSON."""
        data = json_data.get("data", {})
        vlans_container = data.get(OPENCONFIG_VLANS, {})
        vlan_list = vlans_container.get("vlan", [])

        if not vlan_list:
            return {}

        vlans: Dict[str, TypeAny] = {}

        for vlan_entry in vlan_list:
            vlan_id = vlan_entry.get("vlan-id")
            if vlan_id is None:
                continue

            vlan_key = str(vlan_id)
            vlan: Dict[str, TypeAny] = {}

            # Flatten state fields
            state = vlan_entry.get("state", {})
            if "vlan-id" in state:
                vlan["vlan-id"] = state["vlan-id"]
            else:
                vlan["vlan-id"] = vlan_id

            if "name" in state:
                vlan["name"] = state["name"]
            if "status" in state:
                vlan["status"] = state["status"]

            # Extract member interfaces
            members_container = vlan_entry.get("members", {})
            member_list = members_container.get("member", [])
            if member_list:
                interfaces: List[str] = []
                for member in member_list:
                    intf_ref = member.get("interface-ref", {})
                    intf_state = intf_ref.get("state", {})
                    intf_name = intf_state.get("interface")
                    if intf_name:
                        interfaces.append(intf_name)
                if interfaces:
                    vlan["members"] = interfaces

            vlans[vlan_key] = vlan

        return {"vlans": vlans}
