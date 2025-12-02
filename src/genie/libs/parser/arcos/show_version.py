"""ArcOS show version parser using OpenConfig JSON output."""

import json
import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Optional
from genie.libs.parser.arcos.utils import load_json_robust

logger = logging.getLogger(__name__)





class ShowVersionSchema(MetaParser):
    """Schema for ArcOS ``show version`` output.

    The parser normalizes the OpenConfig system version JSON into a
    single top-level ``version`` dictionary.
    """

    schema = {
        "version": {
            "sw-version": str,
            Optional("software"): str,
            Optional("platform"): str,
            Optional("form_factor"): str,
            Optional("num_cpu_cores"): str,
            Optional("cpu_info"): str,
            Optional("total_memory"): str,
            Optional("uptime"): str,
        }
    }


class ShowVersion(ShowVersionSchema):
    """Parser for ArcOS ``show version`` (JSON format).

    The parser expects OpenConfig JSON of the form::

        data["openconfig-system:system"]
            ["arcos-openconfig-system-augments:version"].state

    When no explicit output is provided, the parser runs::

        show version | display json | nomore
    """

    cli_command = "show version"

    def cli(self, output: TypeOptional[TypeAny] = None) -> Dict[str, TypeAny]:
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        logger.debug("Parsing output: %s", output)
        ret_dict: Dict[str, TypeAny] = {"version": {}}

        try:
            parsed_json = load_json_robust(output)

            data = parsed_json.get("data", {})
            system = data.get("openconfig-system:system", {})
            version_obj = system.get(
                "arcos-openconfig-system-augments:version", {}
            )
            state = version_obj.get("state", {})

            if state:
                # Primary field mapping from JSON keys to output keys
                field_mapping = {
                    "platform": "platform",
                    "form-factor": "form_factor",
                    "num-cpu-cores": "num_cpu_cores",
                    "cpu-info": "cpu_info",
                    "total-memory": "total_memory",
                    "software": "software",
                    "sw-version": "sw-version",
                    "uptime": "uptime",
                }

                for json_key, dict_key in field_mapping.items():
                    if json_key in state:
                        ret_dict["version"][dict_key] = state[json_key]

                # If sw-version was not set via "sw-version", try alternates
                if "sw-version" not in ret_dict["version"]:
                    if "version" in state:
                        ret_dict["version"]["sw-version"] = state["version"]
                    elif "software-version" in state:
                        ret_dict["version"]["sw-version"] = state[
                            "software-version"
                        ]

            # Fallback: try direct system.state if version block missing
            if not ret_dict["version"]:
                direct_state = system.get("state", {})
                if direct_state:
                    for key, value in direct_state.items():
                        ret_dict["version"][key] = value
                else:
                    # Minimal fallback information
                    ret_dict["version"]["software"] = "Arrcus ArcOS"
                    ret_dict["version"]["sw-version"] = "Unknown"

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse version JSON output: %s", exc)
            ret_dict["version"]["software"] = "Arrcus ArcOS"
            ret_dict["version"]["sw-version"] = "Parse Failed"
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error parsing version data: %s", exc)

        return ret_dict
