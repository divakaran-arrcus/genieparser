"""ArcOS RIB (Routing Information Base) parsers.

Parsers for ArcOS RIB commands using JSON format.

This module provides parsers for:
- ``ShowRibIpv4Entries`` - Show IPv4 RIB entries
- ``ShowRibIpv6Entries`` - Show IPv6 RIB entries
- ``ShowRibIpv4State`` - Show IPv4 RIB state/summary
- ``ShowRibIpv6State`` - Show IPv6 RIB state/summary
- ``ShowRibIpv4LabelEntries`` - Show IPv4 MPLS label entries

The parsers handle JSON output from commands like::

    show network-instance <instance> rib IPV4 ipv4-entries | display json | nomore
    show network-instance <instance> rib IPV6 ipv6-entries | display json | nomore
    show network-instance <instance> rib IPV4 state | display json | nomore
    show network-instance <instance> rib IPV6 state | display json | nomore
    show network-instance <instance> rib IPV4 ipv4-label-entries | display json | nomore
"""

import json
import logging

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or, ListOf
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import (
    OPENCONFIG_NETWORK_INSTANCES,
    DEFAULT_INSTANCE,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# ShowRibIpv4Entries Schema and Parser
# -----------------------------------------------------------------------------


class ShowRibIpv4EntriesSchema(MetaParser):
    """Schema for ``show network-instance <instance> rib IPV4 ipv4-entries`` output."""

    schema = {
        "network-instance": {
            Any(): {  # network instance name (e.g., "default")
                "rib": {
                    "address-family": str,
                    "ipv4-entries": {
                        Any(): {  # prefix (e.g., "10.0.0.0/24")
                            "prefix": str,
                            "best-protocol": str,
                            Optional("hw-update"): {
                                Optional("install-ack"): bool,
                                Optional("status-code"): int,
                                Optional("version"): str,
                            },
                            "origins": {
                                Any(): {  # origin index
                                    "origin-protocol": str,
                                    "protocol-name": str,
                                    Optional("metric"): int,
                                    Optional("pref"): int,
                                    Optional("label-pref"): int,
                                    Optional("tag"): int,
                                    Optional("route-type"): str,
                                    Optional("nhid"): str,
                                    Optional("last-updated"): str,
                                    Optional("flags"): str,
                                    Optional("opaque-data"): str,
                                    Optional("next-hops"): {
                                        Any(): {  # next-hop index
                                            Optional("pathid"): str,
                                            Optional("type"): str,
                                            Optional("next-hop"): str,
                                            Optional("network-instance"): str,
                                            Optional("interface"): str,
                                            Optional("weight"): int,
                                            Optional("flags"): str,
                                            Optional("label"): Or(int, str, list),
                                        }
                                    },
                                }
                            },
                        }
                    }
                }
            }
        }
    }


class ShowRibIpv4Entries(ShowRibIpv4EntriesSchema):
    """Parser for ``show network-instance <instance> rib IPV4 ipv4-entries``.

    Retrieves IPv4 RIB entries from ArcOS.

    Examples:
        >>> parser = ShowRibIpv4Entries(device=device)
        >>> output = parser.cli()
        >>> output = parser.cli(network_instance="default")
        >>> output = parser.cli(network_instance="default", prefix="10.0.0.0/24")
    """

    cli_command = [
        "show network-instance {network_instance} rib IPV4 ipv4-entries",
        "show network-instance {network_instance} rib IPV4 ipv4-entries {prefix}",
    ]

    def cli(
        self,
        network_instance=None,
        prefix=None,
        output=None,
    ):
        """Parse CLI output (JSON format).

        Args:
            network_instance (str): Network instance name (default: "default").
            prefix (str): Optional specific prefix to query.
            output (str): Optional pre-captured CLI output.

        Returns:
            dict: Parsed IPv4 RIB entries.
        """
        if output is None:
            ni = network_instance or DEFAULT_INSTANCE
            validate_input(ni, "network_instance")

            if prefix:
                validate_input(prefix, "prefix")
                cmd = f"show network-instance {ni} rib IPV4 ipv4-entries {prefix} | display json | nomore"
            else:
                cmd = f"show network-instance {ni} rib IPV4 ipv4-entries | display json | nomore"

            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        return self._parse_output(output)

    def _parse_output(self, output):
        """Parse JSON output and return IPv4 RIB entries."""
        logger.debug("Parsing IPv4 RIB entries")

        try:
            data = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            raise SchemaEmptyParserError(
                f"Invalid JSON in RIB output: {exc}"
            ) from exc

        result = {"network-instance": {}}

        # Navigate OpenConfig structure
        ni_data = data.get("data", {}).get(OPENCONFIG_NETWORK_INSTANCES, {})
        network_instances = ni_data.get("network-instance", [])

        if not network_instances:
            raise SchemaEmptyParserError("No network instance data found in RIB output")

        for ni in network_instances:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            # Get RIB data from arcos-rib:rib array
            rib_list = ni.get("arcos-rib:rib", [])
            if not rib_list:
                continue

            for rib in rib_list:
                address_family = rib.get("address-family", "")
                if "IPV4" not in address_family:
                    continue

                ipv4_entries_data = rib.get("ipv4-entries", {})
                entry_list = ipv4_entries_data.get("entry", [])

                if not entry_list:
                    continue

                parsed_entries = self._parse_entries(entry_list)

                if parsed_entries:
                    result["network-instance"][ni_name] = {
                        "rib": {
                            "address-family": address_family,
                            "ipv4-entries": parsed_entries,
                        }
                    }

        if not result["network-instance"]:
            raise SchemaEmptyParserError("No IPv4 RIB entries found")

        return result

    def _parse_entries(self, entry_list):
        """Parse IPv4 RIB entries."""
        entries = {}

        for entry in entry_list:
            prefix = entry.get("prefix")
            if not prefix:
                continue

            entry_dict = {
                "prefix": prefix,
                "best-protocol": entry.get("best-protocol", ""),
            }

            # Hardware update info
            hw_update = entry.get("hw-update", {})
            if hw_update:
                entry_dict["hw-update"] = {
                    "install-ack": hw_update.get("install-ack", False),
                    "status-code": hw_update.get("status-code", 0),
                    "version": hw_update.get("version", "0"),
                }

            # Parse origins
            origins_data = entry.get("origins", {}).get("origin", [])
            entry_dict["origins"] = self._parse_origins(origins_data)

            entries[prefix] = entry_dict

        return entries

    def _parse_origins(self, origins_list):
        """Parse route origins."""
        origins = {}

        for idx, origin in enumerate(origins_list):
            origin_dict = {
                "origin-protocol": origin.get("origin-protocol", ""),
                "protocol-name": origin.get("protocol-name", ""),
            }

            # Optional fields
            for field in ["metric", "pref", "label-pref", "tag"]:
                if field in origin:
                    origin_dict[field] = origin[field]

            for field in ["route-type", "nhid", "last-updated", "flags", "opaque-data"]:
                if field in origin:
                    origin_dict[field] = origin[field]

            # Parse next-hops
            next_hops_data = origin.get("next-hops", {}).get("next-hop", [])
            if next_hops_data:
                origin_dict["next-hops"] = self._parse_next_hops(next_hops_data)

            origins[str(idx)] = origin_dict

        return origins

    def _parse_next_hops(self, next_hops_list):
        """Parse next-hop entries."""
        next_hops = {}

        for idx, nh in enumerate(next_hops_list):
            nh_dict = {}

            for field in ["pathid", "type", "next-hop", "network-instance",
                          "interface", "flags"]:
                if field in nh:
                    nh_dict[field] = nh[field]

            if "weight" in nh:
                nh_dict["weight"] = nh["weight"]

            if "label" in nh:
                nh_dict["label"] = nh["label"]

            next_hops[str(idx)] = nh_dict

        return next_hops


# -----------------------------------------------------------------------------
# ShowRibIpv6Entries Schema and Parser
# -----------------------------------------------------------------------------


class ShowRibIpv6EntriesSchema(MetaParser):
    """Schema for ``show network-instance <instance> rib IPV6 ipv6-entries`` output."""

    schema = {
        "network-instance": {
            Any(): {  # network instance name
                "rib": {
                    "address-family": str,
                    "ipv6-entries": {
                        Any(): {  # prefix
                            "prefix": str,
                            "best-protocol": str,
                            Optional("hw-update"): {
                                Optional("install-ack"): bool,
                                Optional("status-code"): int,
                                Optional("version"): str,
                            },
                            "origins": {
                                Any(): {
                                    "origin-protocol": str,
                                    "protocol-name": str,
                                    Optional("metric"): int,
                                    Optional("pref"): int,
                                    Optional("label-pref"): int,
                                    Optional("tag"): int,
                                    Optional("route-type"): str,
                                    Optional("nhid"): str,
                                    Optional("last-updated"): str,
                                    Optional("flags"): str,
                                    Optional("opaque-data"): str,
                                    Optional("next-hops"): {
                                        Any(): {
                                            Optional("pathid"): str,
                                            Optional("type"): str,
                                            Optional("next-hop"): str,
                                            Optional("network-instance"): str,
                                            Optional("interface"): str,
                                            Optional("weight"): int,
                                            Optional("flags"): str,
                                            Optional("sid"): str,
                                        }
                                    },
                                }
                            },
                        }
                    }
                }
            }
        }
    }


class ShowRibIpv6Entries(ShowRibIpv6EntriesSchema):
    """Parser for ``show network-instance <instance> rib IPV6 ipv6-entries``.

    Retrieves IPv6 RIB entries from ArcOS.

    Examples:
        >>> parser = ShowRibIpv6Entries(device=device)
        >>> output = parser.cli()
        >>> output = parser.cli(network_instance="default")
        >>> output = parser.cli(network_instance="default", prefix="2001:db8::/32")
    """

    cli_command = [
        "show network-instance {network_instance} rib IPV6 ipv6-entries",
        "show network-instance {network_instance} rib IPV6 ipv6-entries {prefix}",
    ]

    def cli(
        self,
        network_instance=None,
        prefix=None,
        output=None,
    ):
        """Parse CLI output (JSON format).

        Args:
            network_instance (str): Network instance name (default: "default").
            prefix (str): Optional specific prefix to query.
            output (str): Optional pre-captured CLI output.

        Returns:
            dict: Parsed IPv6 RIB entries.
        """
        if output is None:
            ni = network_instance or DEFAULT_INSTANCE
            validate_input(ni, "network_instance")

            if prefix:
                validate_input(prefix, "prefix")
                cmd = f"show network-instance {ni} rib IPV6 ipv6-entries {prefix} | display json | nomore"
            else:
                cmd = f"show network-instance {ni} rib IPV6 ipv6-entries | display json | nomore"

            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        return self._parse_output(output)

    def _parse_output(self, output):
        """Parse JSON output and return IPv6 RIB entries."""
        logger.debug("Parsing IPv6 RIB entries")

        try:
            data = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            raise SchemaEmptyParserError(
                f"Invalid JSON in RIB output: {exc}"
            ) from exc

        result = {"network-instance": {}}

        # Navigate OpenConfig structure
        ni_data = data.get("data", {}).get(OPENCONFIG_NETWORK_INSTANCES, {})
        network_instances = ni_data.get("network-instance", [])

        if not network_instances:
            raise SchemaEmptyParserError("No network instance data found in RIB output")

        for ni in network_instances:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            rib_list = ni.get("arcos-rib:rib", [])
            if not rib_list:
                continue

            for rib in rib_list:
                address_family = rib.get("address-family", "")
                if "IPV6" not in address_family:
                    continue

                ipv6_entries_data = rib.get("ipv6-entries", {})
                entry_list = ipv6_entries_data.get("entry", [])

                if not entry_list:
                    continue

                parsed_entries = self._parse_entries(entry_list)

                if parsed_entries:
                    result["network-instance"][ni_name] = {
                        "rib": {
                            "address-family": address_family,
                            "ipv6-entries": parsed_entries,
                        }
                    }

        if not result["network-instance"]:
            raise SchemaEmptyParserError("No IPv6 RIB entries found")

        return result

    def _parse_entries(self, entry_list):
        """Parse IPv6 RIB entries."""
        entries = {}

        for entry in entry_list:
            prefix = entry.get("prefix")
            if not prefix:
                continue

            entry_dict = {
                "prefix": prefix,
                "best-protocol": entry.get("best-protocol", ""),
            }

            # Hardware update info
            hw_update = entry.get("hw-update", {})
            if hw_update:
                entry_dict["hw-update"] = {
                    "install-ack": hw_update.get("install-ack", False),
                    "status-code": hw_update.get("status-code", 0),
                    "version": hw_update.get("version", "0"),
                }

            # Parse origins
            origins_data = entry.get("origins", {}).get("origin", [])
            entry_dict["origins"] = self._parse_origins(origins_data)

            entries[prefix] = entry_dict

        return entries

    def _parse_origins(self, origins_list):
        """Parse route origins."""
        origins = {}

        for idx, origin in enumerate(origins_list):
            origin_dict = {
                "origin-protocol": origin.get("origin-protocol", ""),
                "protocol-name": origin.get("protocol-name", ""),
            }

            for field in ["metric", "pref", "label-pref", "tag"]:
                if field in origin:
                    origin_dict[field] = origin[field]

            for field in ["route-type", "nhid", "last-updated", "flags", "opaque-data"]:
                if field in origin:
                    origin_dict[field] = origin[field]

            next_hops_data = origin.get("next-hops", {}).get("next-hop", [])
            if next_hops_data:
                origin_dict["next-hops"] = self._parse_next_hops(next_hops_data)

            origins[str(idx)] = origin_dict

        return origins

    def _parse_next_hops(self, next_hops_list):
        """Parse next-hop entries."""
        next_hops = {}

        for idx, nh in enumerate(next_hops_list):
            nh_dict = {}

            for field in ["pathid", "type", "next-hop", "network-instance",
                          "interface", "flags", "sid"]:
                if field in nh:
                    nh_dict[field] = nh[field]

            if "weight" in nh:
                nh_dict["weight"] = nh["weight"]

            next_hops[str(idx)] = nh_dict

        return next_hops


# -----------------------------------------------------------------------------
# ShowRibIpv4State Schema and Parser
# -----------------------------------------------------------------------------


class ShowRibIpv4StateSchema(MetaParser):
    """Schema for ``show network-instance <instance> rib IPV4 state`` output."""

    schema = {
        "network-instance": {
            Any(): {
                "rib": {
                    "address-family": str,
                    "state": {
                        "address-family": str,
                        Optional("total-routes"): int,
                        Optional("total-paths"): int,
                    }
                }
            }
        }
    }


class ShowRibIpv4State(ShowRibIpv4StateSchema):
    """Parser for ``show network-instance <instance> rib IPV4 state``.

    Retrieves IPv4 RIB state/summary statistics.

    Examples:
        >>> parser = ShowRibIpv4State(device=device)
        >>> output = parser.cli()
        >>> output = parser.cli(network_instance="default")
    """

    cli_command = [
        "show network-instance {network_instance} rib IPV4 state",
    ]

    def cli(self, network_instance=None, output=None):
        """Parse CLI output (JSON format).

        Args:
            network_instance (str): Network instance name (default: "default").
            output (str): Optional pre-captured CLI output.

        Returns:
            dict: IPv4 RIB state.
        """
        if output is None:
            ni = network_instance or DEFAULT_INSTANCE
            validate_input(ni, "network_instance")
            cmd = f"show network-instance {ni} rib IPV4 state | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        return self._parse_output(output)

    def _parse_output(self, output):
        """Parse JSON output for IPv4 RIB state."""
        logger.debug("Parsing IPv4 RIB state")

        try:
            data = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            raise SchemaEmptyParserError(
                f"Invalid JSON in RIB state output: {exc}"
            ) from exc

        result = {"network-instance": {}}

        ni_data = data.get("data", {}).get(OPENCONFIG_NETWORK_INSTANCES, {})
        network_instances = ni_data.get("network-instance", [])

        if not network_instances:
            raise SchemaEmptyParserError("No network instance data found")

        for ni in network_instances:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            rib_list = ni.get("arcos-rib:rib", [])
            if not rib_list:
                continue

            for rib in rib_list:
                address_family = rib.get("address-family", "")
                if "IPV4" not in address_family:
                    continue

                state_data = rib.get("state", {})

                state = {
                    "address-family": state_data.get("address-family", address_family),
                }

                # Optional statistics fields
                for field in ["total-routes", "total-paths"]:
                    if field in state_data:
                        state[field] = state_data[field]

                result["network-instance"][ni_name] = {
                    "rib": {
                        "address-family": address_family,
                        "state": state,
                    }
                }

        if not result["network-instance"]:
            raise SchemaEmptyParserError("No IPv4 RIB state found")

        return result


# -----------------------------------------------------------------------------
# ShowRibIpv6State Schema and Parser
# -----------------------------------------------------------------------------


class ShowRibIpv6StateSchema(MetaParser):
    """Schema for ``show network-instance <instance> rib IPV6 state`` output."""

    schema = {
        "network-instance": {
            Any(): {
                "rib": {
                    "address-family": str,
                    "state": {
                        "address-family": str,
                        Optional("total-routes"): int,
                        Optional("total-paths"): int,
                    }
                }
            }
        }
    }


class ShowRibIpv6State(ShowRibIpv6StateSchema):
    """Parser for ``show network-instance <instance> rib IPV6 state``.

    Retrieves IPv6 RIB state/summary statistics.

    Examples:
        >>> parser = ShowRibIpv6State(device=device)
        >>> output = parser.cli()
        >>> output = parser.cli(network_instance="default")
    """

    cli_command = [
        "show network-instance {network_instance} rib IPV6 state",
    ]

    def cli(self, network_instance=None, output=None):
        """Parse CLI output (JSON format).

        Args:
            network_instance (str): Network instance name (default: "default").
            output (str): Optional pre-captured CLI output.

        Returns:
            dict: IPv6 RIB state.
        """
        if output is None:
            ni = network_instance or DEFAULT_INSTANCE
            validate_input(ni, "network_instance")
            cmd = f"show network-instance {ni} rib IPV6 state | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        return self._parse_output(output)

    def _parse_output(self, output):
        """Parse JSON output for IPv6 RIB state."""
        logger.debug("Parsing IPv6 RIB state")

        try:
            data = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            raise SchemaEmptyParserError(
                f"Invalid JSON in RIB state output: {exc}"
            ) from exc

        result = {"network-instance": {}}

        ni_data = data.get("data", {}).get(OPENCONFIG_NETWORK_INSTANCES, {})
        network_instances = ni_data.get("network-instance", [])

        if not network_instances:
            raise SchemaEmptyParserError("No network instance data found")

        for ni in network_instances:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            rib_list = ni.get("arcos-rib:rib", [])
            if not rib_list:
                continue

            for rib in rib_list:
                address_family = rib.get("address-family", "")
                if "IPV6" not in address_family:
                    continue

                state_data = rib.get("state", {})

                state = {
                    "address-family": state_data.get("address-family", address_family),
                }

                for field in ["total-routes", "total-paths"]:
                    if field in state_data:
                        state[field] = state_data[field]

                result["network-instance"][ni_name] = {
                    "rib": {
                        "address-family": address_family,
                        "state": state,
                    }
                }

        if not result["network-instance"]:
            raise SchemaEmptyParserError("No IPv6 RIB state found")

        return result


# -----------------------------------------------------------------------------
# ShowRibIpv4LabelEntries Schema and Parser
# -----------------------------------------------------------------------------


class ShowRibIpv4LabelEntriesSchema(MetaParser):
    """Schema for ``show network-instance <instance> rib IPV4 ipv4-label-entries`` output."""

    schema = {
        "network-instance": {
            Any(): {
                "rib": {
                    "address-family": str,
                    "ipv4-label-entries": {
                        Any(): {  # label as key
                            "label": int,
                            Optional("label-type"): str,
                            Optional("vpn-table-id"): int,
                            Optional("protocol"): str,
                            Optional("fec"): str,
                            Optional("nhid"): str,
                            Optional("last-updated"): str,
                            Optional("time-since-creation"): str,
                            Optional("flags"): str,
                        }
                    }
                }
            }
        }
    }


class ShowRibIpv4LabelEntries(ShowRibIpv4LabelEntriesSchema):
    """Parser for ``show network-instance <instance> rib IPV4 ipv4-label-entries``.

    Retrieves IPv4 MPLS label entries from RIB.

    Examples:
        >>> parser = ShowRibIpv4LabelEntries(device=device)
        >>> output = parser.cli()
        >>> output = parser.cli(network_instance="default")
    """

    cli_command = [
        "show network-instance {network_instance} rib IPV4 ipv4-label-entries",
    ]

    def cli(self, network_instance=None, output=None):
        """Parse CLI output (JSON format).

        Args:
            network_instance (str): Network instance name (default: "default").
            output (str): Optional pre-captured CLI output.

        Returns:
            dict: Parsed IPv4 label entries.
        """
        if output is None:
            ni = network_instance or DEFAULT_INSTANCE
            validate_input(ni, "network_instance")
            cmd = f"show network-instance {ni} rib IPV4 ipv4-label-entries | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        return self._parse_output(output)

    def _parse_output(self, output):
        """Parse JSON output for IPv4 label entries."""
        logger.debug("Parsing IPv4 label entries")

        try:
            data = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            raise SchemaEmptyParserError(
                f"Invalid JSON in label entries output: {exc}"
            ) from exc

        result = {"network-instance": {}}

        ni_data = data.get("data", {}).get(OPENCONFIG_NETWORK_INSTANCES, {})
        network_instances = ni_data.get("network-instance", [])

        if not network_instances:
            raise SchemaEmptyParserError("No network instance data found")

        for ni in network_instances:
            ni_name = ni.get("name")
            if not ni_name:
                continue

            rib_list = ni.get("arcos-rib:rib", [])
            if not rib_list:
                continue

            for rib in rib_list:
                address_family = rib.get("address-family", "")
                if "IPV4" not in address_family:
                    continue

                label_entries_data = rib.get("ipv4-label-entries", {})
                entry_list = label_entries_data.get("entry", [])

                if not entry_list:
                    continue

                parsed_entries = self._parse_label_entries(entry_list)

                if parsed_entries:
                    result["network-instance"][ni_name] = {
                        "rib": {
                            "address-family": address_family,
                            "ipv4-label-entries": parsed_entries,
                        }
                    }

        if not result["network-instance"]:
            raise SchemaEmptyParserError("No IPv4 label entries found")

        return result

    def _parse_label_entries(self, entry_list):
        """Parse IPv4 label entries."""
        entries = {}

        for entry in entry_list:
            label = entry.get("label")
            if label is None:
                continue

            entry_dict = {
                "label": label,
            }

            # Optional fields
            for field in ["label-type", "protocol", "fec", "nhid",
                          "last-updated", "time-since-creation", "flags"]:
                if field in entry:
                    entry_dict[field] = entry[field]

            if "vpn-table-id" in entry:
                entry_dict["vpn-table-id"] = entry["vpn-table-id"]

            entries[str(label)] = entry_dict

        return entries
