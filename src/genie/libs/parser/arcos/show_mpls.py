"""ArcOS MPLS parsers using OpenConfig JSON output."""

import logging
from typing import Any as TypeAny, Dict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust, validate_input

logger = logging.getLogger(__name__)

# Constants for namespace stripping
ARCOS_MPLS_PREFIX = "arcos-mpls:"
OPENCONFIG_POLICY_PREFIX = "openconfig-policy-types:"
OPENCONFIG_NI_PREFIX = "openconfig-network-instance:"


def strip_namespace(value: str) -> str:
    """Strip common namespace prefixes from a value."""
    if not isinstance(value, str):
        return value
    for prefix in (ARCOS_MPLS_PREFIX, OPENCONFIG_POLICY_PREFIX, OPENCONFIG_NI_PREFIX):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


# =============================================================================
# ShowMplsReservedLabelBlockConfig - Running Config Parser
# =============================================================================


class ShowMplsReservedLabelBlockConfigSchema(MetaParser):
    """Schema for MPLS reserved-label-block running configuration.

    CLI Command::

        show running-config network-instance {network_instance} mpls global reserved-label-block [<local_id>]
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "mpls": {
                    "reserved-label-blocks": {
                        Any(): {  # local-id as key
                            "local-id": str,
                            "lower-bound": int,
                            "upper-bound": int,
                            Optional("usage"): str,
                            Optional("protocol-identifier"): str,
                            Optional("protocol-name"): str,
                        }
                    }
                }
            }
        }
    }


class ShowMplsReservedLabelBlockConfig(ShowMplsReservedLabelBlockConfigSchema):
    """Parser for ArcOS MPLS reserved-label-block running configuration (JSON format).

    Command pattern (before JSON pipe)::

        show running-config network-instance {network_instance} mpls global reserved-label-block [<local_id>]
    """

    cli_command = [
        "show running-config network-instance {network_instance} mpls global reserved-label-block",
    ]

    def cli(
        self,
        network_instance: str = "*",
        local_id: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            cmd = f"show running-config network-instance {network_instance} mpls global reserved-label-block"
            if local_id:
                validate_input(local_id, "local_id")
                cmd += f" {local_id}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        if not output or not output.strip():
            raise SchemaEmptyParserError(
                "ShowMplsReservedLabelBlockConfig: empty output"
            )

        logger.debug("Parsing output: %s", output)

        # Initialize return dictionary
        ret_dict: Dict[str, TypeAny] = {"network-instance": {}}

        try:
            parsed_json = load_json_robust(output)

            data = parsed_json.get("data", {})
            network_instances = data.get(
                "openconfig-network-instance:network-instances", {}
            )
            ni_list = network_instances.get("network-instance", [])

            for ni in ni_list:
                ni_name = ni.get("name")
                if not ni_name:
                    continue

                mpls = ni.get("mpls", {})
                global_config = mpls.get("global", {})
                reserved_blocks = global_config.get("reserved-label-blocks", {})
                block_list = reserved_blocks.get("reserved-label-block", [])

                if not block_list:
                    continue

                # Initialize network instance structure
                if ni_name not in ret_dict["network-instance"]:
                    ret_dict["network-instance"][ni_name] = {
                        "mpls": {"reserved-label-blocks": {}}
                    }

                blocks_dict = ret_dict["network-instance"][ni_name]["mpls"][
                    "reserved-label-blocks"
                ]

                for block in block_list:
                    block_id = block.get("local-id")
                    if not block_id:
                        continue

                    # Use "config" for running-config output
                    config = block.get("config", {})

                    block_entry: Dict[str, TypeAny] = {
                        "local-id": block_id,
                        "lower-bound": config.get("lower-bound", 0),
                        "upper-bound": config.get("upper-bound", 0),
                    }

                    # Optional fields with namespace stripping
                    usage = config.get("arcos-mpls:usage")
                    if usage:
                        block_entry["usage"] = strip_namespace(usage)

                    protocol_id = config.get("arcos-mpls:protocol-identifier")
                    if protocol_id:
                        block_entry["protocol-identifier"] = strip_namespace(protocol_id)

                    protocol_name = config.get("arcos-mpls:protocol-name")
                    if protocol_name:
                        block_entry["protocol-name"] = protocol_name

                    blocks_dict[block_id] = block_entry

        except Exception as exc:
            logger.warning("Error parsing MPLS reserved-label-block config: %s", exc)

        return ret_dict


# =============================================================================
# ShowMplsReservedLabelBlock - Operational State Parser
# =============================================================================


class ShowMplsReservedLabelBlockSchema(MetaParser):
    """Schema for MPLS reserved-label-block operational state.

    CLI Command::

        show network-instance {network_instance} mpls global reserved-label-block [<local_id>]
    """

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "mpls": {
                    "reserved-label-blocks": {
                        Any(): {  # local-id as key
                            "local-id": str,
                            "lower-bound": int,
                            "upper-bound": int,
                            Optional("usage"): str,
                            Optional("protocol-identifier"): str,
                            Optional("protocol-name"): str,
                        }
                    }
                }
            }
        }
    }


class ShowMplsReservedLabelBlock(ShowMplsReservedLabelBlockSchema):
    """Parser for ArcOS MPLS reserved-label-block operational state (JSON format).

    Command pattern (before JSON pipe)::

        show network-instance {network_instance} mpls global reserved-label-block [<local_id>]
    """

    cli_command = [
        "show network-instance {network_instance} mpls global reserved-label-block",
    ]

    def cli(
        self,
        network_instance: str = "*",
        local_id: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        if output is None:
            validate_input(network_instance, "network_instance")
            cmd = f"show network-instance {network_instance} mpls global reserved-label-block"
            if local_id:
                validate_input(local_id, "local_id")
                cmd += f" {local_id}"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(f"{cmd} | display json | nomore")

        if not output or not output.strip():
            raise SchemaEmptyParserError(
                "ShowMplsReservedLabelBlock: empty output"
            )

        logger.debug("Parsing output: %s", output)

        # Initialize return dictionary
        ret_dict: Dict[str, TypeAny] = {"network-instance": {}}

        try:
            parsed_json = load_json_robust(output)

            data = parsed_json.get("data", {})
            network_instances = data.get(
                "openconfig-network-instance:network-instances", {}
            )
            ni_list = network_instances.get("network-instance", [])

            for ni in ni_list:
                ni_name = ni.get("name")
                if not ni_name:
                    continue

                mpls = ni.get("mpls", {})
                global_config = mpls.get("global", {})
                reserved_blocks = global_config.get("reserved-label-blocks", {})
                block_list = reserved_blocks.get("reserved-label-block", [])

                if not block_list:
                    continue

                # Initialize network instance structure
                if ni_name not in ret_dict["network-instance"]:
                    ret_dict["network-instance"][ni_name] = {
                        "mpls": {"reserved-label-blocks": {}}
                    }

                blocks_dict = ret_dict["network-instance"][ni_name]["mpls"][
                    "reserved-label-blocks"
                ]

                for block in block_list:
                    block_id = block.get("local-id")
                    if not block_id:
                        continue

                    # Use "state" for operational state output
                    state = block.get("state", {})

                    block_entry: Dict[str, TypeAny] = {
                        "local-id": block_id,
                        "lower-bound": state.get("lower-bound", 0),
                        "upper-bound": state.get("upper-bound", 0),
                    }

                    # Optional fields with namespace stripping
                    usage = state.get("arcos-mpls:usage")
                    if usage:
                        block_entry["usage"] = strip_namespace(usage)

                    protocol_id = state.get("arcos-mpls:protocol-identifier")
                    if protocol_id:
                        block_entry["protocol-identifier"] = strip_namespace(protocol_id)

                    protocol_name = state.get("arcos-mpls:protocol-name")
                    if protocol_name:
                        block_entry["protocol-name"] = protocol_name

                    blocks_dict[block_id] = block_entry

        except Exception as exc:
            logger.warning("Error parsing MPLS reserved-label-block state: %s", exc)

        return ret_dict
