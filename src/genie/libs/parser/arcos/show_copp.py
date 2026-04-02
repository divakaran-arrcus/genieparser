"""ArcOS CoPP parser using JSON output.

Parser:
    ShowCoppPolicy — ``show copp policy *``
"""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)


class ShowCoppPolicySchema(MetaParser):
    schema = {
        "policies": {
            Any(): {  # policy name
                "name": str,
                Optional("classifiers"): {
                    Any(): {  # classifier name
                        "name": str,
                        Optional("actions"): {
                            Any(): str,
                        },
                    }
                },
            }
        }
    }


class ShowCoppPolicy(ShowCoppPolicySchema):
    """Parser for CoPP policy state."""

    cli_command = "show copp policy {name}"

    def cli(self, name="*",
            output: TypeOptional[str] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"show copp policy {name} | display json | nomore"
            output = self.device.execute(cmd)

        parsed = load_json_robust(output)

        data = parsed.get("data", {})
        copp = data.get("arcos-copp:copp", data.get("copp", {}))

        policies_list = copp.get("policy", copp.get("policies", {}).get("policy", []))
        if not policies_list:
            raise SchemaEmptyParserError("No CoPP policy data found")

        if isinstance(policies_list, dict):
            policies_list = [policies_list]

        result = {"policies": {}}

        for pol in policies_list:
            pol_name = pol.get("name", "")
            if not pol_name:
                continue

            entry = {"name": pol_name}

            classifiers = pol.get("classifier", pol.get("classifiers", {}).get("classifier", []))
            if classifiers:
                if isinstance(classifiers, dict):
                    classifiers = [classifiers]
                entry["classifiers"] = {}
                for cls in classifiers:
                    cls_name = cls.get("name", "")
                    if not cls_name:
                        continue
                    cls_entry = {"name": cls_name}
                    actions = cls.get("action", cls.get("actions", {}))
                    if actions and isinstance(actions, dict):
                        cls_entry["actions"] = {}
                        for ak, av in actions.items():
                            if isinstance(av, str):
                                cls_entry["actions"][ak] = av
                            else:
                                cls_entry["actions"][ak] = str(av)
                    entry["classifiers"][cls_name] = cls_entry

            result["policies"][pol_name] = entry

        if not result["policies"]:
            raise SchemaEmptyParserError("No CoPP policy data found")

        return result
