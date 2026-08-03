"""show_interface.py

ArcOS parsers for the following show commands:
    * show interface
    * show interface {interface}
"""

import json
import logging

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import OPENCONFIG_INTERFACES
from genie.libs.parser.arcos.utils import load_json_robust, validate_input


logger = logging.getLogger(__name__)


class ShowInterfaceSchema(MetaParser):
    """Schema for ``show interface`` output on ArcOS."""

    schema = {
        Any(): {  # interface name
            "name": str,
            "type": str,
            "mtu": int,
            "enabled": bool,
            "admin-status": str,
            "oper-status": str,
            "description": str,
            Optional("mac-address"): str,
            Optional("last-change"): str,
            Optional("ipv4-addresses"): {
                Any(): {  # IP address
                    "ip": str,
                    "prefix-length": int,
                }
            },
            Optional("ipv6-addresses"): {
                Any(): {  # IP address
                    "ip": str,
                    "prefix-length": int,
                }
            },
            Optional("counters"): {
                "in-octets": str,
                "in-unicast-pkts": str,
                "in-errors": str,
                "out-octets": str,
                "out-unicast-pkts": str,
                "out-errors": str,
            },
        }
    }


class ShowInterface(ShowInterfaceSchema):
    """Parser for ``show interface`` commands on ArcOS.

    The parser expects JSON output produced by commands of the form::

        show interface | display json | nomore
        show interface <interface> | display json | nomore

    Because ``show interface *`` can be very large, the implementation
    queries by interface-type groups (e.g. ``swp*``, ``loopback*``) when
    no specific interface is provided.
    """

    # Multiple CLI command patterns (for device.parse integration)
    cli_command = [
        "show interface",
        "show interface {interface}",
    ]

    # Interface type prefixes to query for "show interface" (all interfaces)
    interface_types = ["swp", "loopback"]

    def cli(self, interface=None, output=None):  # type: ignore[override]
        """Parse CLI output (JSON format).

        Args:
            interface (str): Optional interface name for specific query.
            output (str): Optional pre-captured CLI output.
        Returns:
            dict: Parsed interface data.
        """

        if output is None:
            if interface:
                validate_input(interface, "interface")
                # Query specific interface
                cmd = f"show interface {interface} | display json | nomore"
                logger.debug("Executing command: %s", cmd)
                output = self.device.execute(cmd)
                return self._parse_output(output)
            else:
                # Query all interfaces by type
                all_interfaces = {}

                for intf_type in self.interface_types:
                    cmd = f"show interface {intf_type}* | display json | nomore"
                    try:
                        logger.debug("Executing command: %s", cmd)
                        output = self.device.execute(cmd)
                        parsed = self._parse_output(output)
                        all_interfaces.update(parsed)
                    except Exception as exc:  # pragma: no cover - defensive
                        logger.warning(
                            "Failed to query %s* interfaces: %s", intf_type, exc
                        )
                        continue

                if not all_interfaces:
                    raise SchemaEmptyParserError("No interface data found")

                return all_interfaces

        # Output provided, parse it directly
        return self._parse_output(output)

    def _parse_output(self, output):
        """Parse JSON output and return interface dictionary."""
        logger.debug("Parsing output: %s", output)

        # Some devices or helper APIs may return a decoded JSON object
        # instead of a raw string. Accept both forms.

        try:
            if not output or not output.strip():
                raise SchemaEmptyParserError("ShowInterface: empty output")
            data = load_json_robust(output)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse JSON output: %s", exc)
            raise SchemaEmptyParserError(
                f"Invalid JSON in interface output: {exc}"
            ) from exc

        interfaces_data = data.get("data", {}).get(OPENCONFIG_INTERFACES, {})
        interface_list = interfaces_data.get("interface", [])

        if not interface_list:
            raise SchemaEmptyParserError("No interface data found")

        parsed = {}

        for intf in interface_list:
            intf_name = intf.get("name")
            if not intf_name:
                continue

            state = intf.get("state", {})
            ethernet = (
                intf.get("openconfig-if-ethernet:ethernet", {}).get("state", {})
            )

            intf_dict = {
                "name": intf_name,
                "type": state.get("type", "unknown"),
                "mtu": state.get("mtu", 0),
                "enabled": state.get("enabled", False),
                "admin-status": state.get("admin-status", "UNKNOWN"),
                "oper-status": state.get("oper-status", "UNKNOWN"),
                "description": state.get("description", ""),
            }

            # MAC address
            if "mac-address" in ethernet:
                intf_dict["mac-address"] = ethernet["mac-address"]

            # Last-change timestamp
            if "last-change" in state:
                intf_dict["last-change"] = state["last-change"]

            # Counters
            counters = state.get("counters", {})
            if counters:
                intf_dict["counters"] = {
                    "in-octets": str(counters.get("in-octets", "0")),
                    "in-unicast-pkts": str(counters.get("in-unicast-pkts", "0")),
                    "in-errors": str(counters.get("in-errors", "0")),
                    "out-octets": str(counters.get("out-octets", "0")),
                    "out-unicast-pkts": str(counters.get("out-unicast-pkts", "0")),
                    "out-errors": str(counters.get("out-errors", "0")),
                }

            # Subinterfaces for IP addresses
            subinterfaces = intf.get("subinterfaces", {}).get("subinterface", [])
            for subintf in subinterfaces:
                # IPv4 addresses
                ipv4 = subintf.get("openconfig-if-ip:ipv4", {})
                ipv4_addrs = ipv4.get("addresses", {}).get("address", [])
                if ipv4_addrs:
                    intf_dict.setdefault("ipv4-addresses", {})
                    for addr in ipv4_addrs:
                        addr_state = addr.get("state", {})
                        ip = addr_state.get("ip")
                        if ip:
                            intf_dict["ipv4-addresses"][ip] = {
                                "ip": ip,
                                "prefix-length": addr_state.get(
                                    "prefix-length", 0
                                ),
                            }

                # IPv6 addresses
                ipv6 = subintf.get("openconfig-if-ip:ipv6", {})
                ipv6_addrs = ipv6.get("addresses", {}).get("address", [])
                if ipv6_addrs:
                    intf_dict.setdefault("ipv6-addresses", {})
                    for addr in ipv6_addrs:
                        addr_state = addr.get("state", {})
                        ip = addr_state.get("ip")
                        if ip:
                            intf_dict["ipv6-addresses"][ip] = {
                                "ip": ip,
                                "prefix-length": addr_state.get(
                                    "prefix-length", 0
                                ),
                            }

            parsed[intf_name] = intf_dict

        return parsed
