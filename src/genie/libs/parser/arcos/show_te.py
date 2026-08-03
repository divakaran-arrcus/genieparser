"""show_te.py

ArcOS parsers for the following show commands:
    * show network-instance {network_instance} te admin-group
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import (
    ARCOS_TE,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowTeAdminGroupSchema(MetaParser):
    """Schema for ArcOS ``show te admin-group`` output.

    Returns TE admin-group definitions keyed by name under
    ``network-instance``.
    """

    schema = {
        Optional("network-instance"): {
            Any(): {  # network instance name (e.g., "default")
                Optional("admin-groups"): {
                    Any(): {  # admin-group name (e.g., "red", "green")
                        Optional("name"): str,
                        Optional("bit-position"): Or(str, int),
                    }
                }
            }
        }
    }


class ShowTeAdminGroup(ShowTeAdminGroupSchema):
    """Parser for ArcOS ``show te admin-group`` (JSON format).

    The parser expects OpenConfig JSON of the form::

        data["openconfig-network-instance:network-instances"]
            ["network-instance"][0]["arcos-te:te"]
            ["admin-groups"]["admin-group"][]

    Each admin-group entry's ``state`` fields are flattened.
    The ``arcos-te:`` namespace prefix is stripped during parsing.

    When no explicit output is provided, the parser runs::

        show network-instance {network_instance} te admin-group
            | display json | nomore
    """

    cli_command = (
        "show network-instance {network_instance} te admin-group"
    )

    def cli(
        self,
        network_instance: str = "default",
        output: TypeOptional[TypeAny] = None,
    ) -> Dict[str, TypeAny]:
        if output is None:
            cmd = self.cli_command.format(
                network_instance=network_instance,
            )
            cmd = f"{cmd} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowTeAdminGroup: empty output")

        parsed_json = load_json_robust(output)
        result = self._parse_admin_groups(parsed_json)

        if not result:
            raise SchemaEmptyParserError(
                "No TE admin-group data found in output"
            )

        return result

    def _parse_admin_groups(
        self, json_data: Dict
    ) -> Dict[str, TypeAny]:
        """Extract TE admin-group definitions from OpenConfig JSON."""
        data = json_data.get("data", {})
        ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})
        ni_list = ni_container.get("network-instance", [])

        if not ni_list:
            return {}

        instances: Dict[str, TypeAny] = {}

        for ni in ni_list:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            te = ni.get(ARCOS_TE, {})
            ag_container = te.get("admin-groups", {})
            ag_list = ag_container.get("admin-group", [])

            if not ag_list:
                continue

            admin_groups: Dict[str, TypeAny] = {}

            for ag in ag_list:
                name = ag.get("name")
                if not name:
                    continue

                # Flatten state fields
                state = ag.get("state", {})
                entry: Dict[str, TypeAny] = {}

                if "name" in state:
                    entry["name"] = state["name"]
                else:
                    entry["name"] = name

                if "bit-position" in state:
                    entry["bit-position"] = state["bit-position"]

                admin_groups[name] = entry

            if admin_groups:
                instances[ni_name] = {"admin-groups": admin_groups}

        if not instances:
            return {}

        return {"network-instance": instances}
