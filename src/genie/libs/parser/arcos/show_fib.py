"""ArcOS FIB (Forwarding Information Base) parsers.

Parsers for Arrcus ArcOS FIB OpenConfig-based JSON commands.

Provides three parser classes with ``af`` as a runtime parameter:

- ``ShowFibPrefixEntries``  — IPv4/IPv6 prefix entries
- ``ShowFibNexthopEntries`` — IPv4/IPv6 nexthop entries
- ``ShowFibLabelEntries``   — IPv4/IPv6 label entries

All output is JSON-only via ``| display json | nomore``.
"""

import logging
from typing import Any as TypeAny, Dict, List, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import (
    ARCOS_FIB,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input

logger = logging.getLogger(__name__)

# Namespace prefixes stripped from values
_PREFIX_OC_TYPES = "openconfig-types:"


def _strip_ns(value: str) -> str:
    """Strip known OpenConfig namespace prefixes from a string value."""
    if not isinstance(value, str):
        return value
    if value.startswith(_PREFIX_OC_TYPES):
        return value[len(_PREFIX_OC_TYPES):]
    return value


def _get_fib_data(
    json_output: Dict,
    network_instance: str,
    af: str,
) -> List[Dict]:
    """Navigate to the FIB array for a given network-instance and AF.

    Returns the ``arcos-fib:fib`` list filtered to the requested
    address-family, or an empty list if not found.

    The expected layout is::

        data[OPENCONFIG_NETWORK_INSTANCES].network-instance[]
            .name == network_instance
            .arcos-fib:fib[]
                .address-family == "openconfig-types:IPV4|IPV6"
    """
    af_upper = af.upper()
    af_match = f"{_PREFIX_OC_TYPES}{af_upper}"

    data = json_output.get("data", {})
    ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

    for ni in ni_container.get("network-instance", []):
        if ni.get("name") != network_instance:
            continue
        for fib in ni.get(ARCOS_FIB, []):
            if fib.get("address-family") == af_match:
                return [fib]
    return []


# ===================================================================
# Schemas
# ===================================================================


class _FibPrefixEntriesSchema(MetaParser):
    """Schema for IPv4/IPv6 FIB prefix entries."""

    schema = {
        "network-instance": {
            Any(): {  # NI name ("default")
                Optional("address-family"): str,
                Optional("prefix-entries"): {
                    Any(): {  # prefix key ("5.5.5.5/32")
                        Optional("prefix"): str,
                        Optional("last-updated"): str,
                        Optional("next-hop-id"): int,
                        Optional("publish-type"): str,
                        Optional("publish-id"): int,
                    }
                },
            }
        }
    }


class _FibNexthopEntriesSchema(MetaParser):
    """Schema for IPv4/IPv6 FIB nexthop entries."""

    schema = {
        "network-instance": {
            Any(): {  # NI name ("default")
                Optional("address-family"): str,
                Optional("nexthop-entries"): {
                    Any(): {  # index key ("643")
                        Optional("index"): int,
                        Optional("eos0-nexthop-index"): int,
                        Optional("source-nexthop-index"): int,
                        Optional("level"): int,
                        Optional("flags"): str,
                        Optional("paths"): {
                            Any(): {  # path index ("0", "1", ...)
                                Optional("path-id"): int,
                                Optional("path-type"): str,
                                Optional("nh-type"): str,
                                Optional("next-hop"): Or(str, int),
                                Optional("push-label"): list,
                                Optional("interface"): str,
                                Optional("network-instance"): str,
                                Optional("num-coll-paths"): int,
                                Optional("igp-path-id"): list,
                                Optional("igp-path-type"): int,
                            }
                        },
                    }
                },
            }
        }
    }


class _FibLabelEntriesSchema(MetaParser):
    """Schema for IPv4/IPv6 FIB label entries."""

    schema = {
        "network-instance": {
            Any(): {  # NI name ("default")
                Optional("address-family"): str,
                Optional("label-entries"): {
                    Any(): {  # label key ("10005")
                        Optional("local-label"): int,
                        Optional("vpn-table-id"): int,
                        Optional("next-hop-id"): int,
                        Optional("publish-id"): int,
                        Optional("control-word"): bool,
                        Optional("flow-label"): bool,
                        Optional("domain-name"): str,
                    }
                },
            }
        }
    }


# ===================================================================
# Parsing helpers (mixed into parser classes)
# ===================================================================


class _FibPrefixEntriesMixin:
    """Parsing logic for FIB prefix entries."""

    def _do_parse(
        self,
        network_instance: str,
        af: str,
        prefix: TypeOptional[str],
        output: TypeOptional[str],
    ) -> Dict:
        """Core parse logic for FIB prefix entries."""
        af_upper = af.upper()
        af_lower = af.lower()
        # Container: ipv4-entries / ipv6-entries
        entries_container_key = f"{af_lower}-entries"
        # Entry list: ipv4-prefix-entry / ipv6-prefix-entry
        entry_list_key = f"{af_lower}-prefix-entry"

        if output is None:
            validate_input(network_instance, "network_instance")
            if prefix:
                validate_input(prefix, "prefix")
            exec_cmd = (
                f"show network-instance {network_instance} fib "
                f"{af_upper} {entry_list_key}"
            )
            if prefix:
                exec_cmd += f" {prefix}"
            logger.debug("Executing command: %s", exec_cmd)
            output = self.device.execute(f"{exec_cmd} | display json | nomore")

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowFibPrefixEntries: empty output")

        parsed_json = load_json_robust(output)

        fibs = _get_fib_data(parsed_json, network_instance, af_lower)
        if not fibs:
            raise SchemaEmptyParserError(
                f"No FIB data found for NI={network_instance}, AF={af_lower}"
            )

        result: Dict[str, TypeAny] = {"network-instance": {}}

        for fib in fibs:
            container = fib.get(entries_container_key, {})
            entry_list = container.get(entry_list_key, [])

            if not entry_list:
                continue

            ni_dict = result["network-instance"].setdefault(network_instance, {})
            ni_dict["address-family"] = _strip_ns(fib.get("address-family", ""))

            prefix_entries = ni_dict.setdefault("prefix-entries", {})

            for entry in entry_list:
                pfx = entry.get("prefix", "")
                if not pfx:
                    continue

                entry_out: Dict[str, TypeAny] = {"prefix": pfx}

                for field in ("last-updated", "next-hop-id", "publish-type", "publish-id"):
                    if field in entry:
                        entry_out[field] = entry[field]

                prefix_entries[pfx] = entry_out

        if not result.get("network-instance"):
            raise SchemaEmptyParserError(
                f"No FIB prefix entries found for NI={network_instance}, AF={af_lower}"
            )

        return result


class _FibNexthopEntriesMixin:
    """Parsing logic for FIB nexthop entries."""

    def _do_parse(
        self,
        network_instance: str,
        af: str,
        index: TypeOptional[str],
        output: TypeOptional[str],
    ) -> Dict:
        """Core parse logic for FIB nexthop entries."""
        af_upper = af.upper()
        af_lower = af.lower()
        # Container: ipv4-next-hops / ipv6-next-hops
        nh_container_key = f"{af_lower}-next-hops"
        # Entry list: ipv4-nexthop-entry / ipv6-nexthop-entry
        nh_entry_key = f"{af_lower}-nexthop-entry"
        # Path list: ipv4-path / ipv6-path
        path_key = f"{af_lower}-path"

        if output is None:
            validate_input(network_instance, "network_instance")
            exec_cmd = (
                f"show network-instance {network_instance} fib "
                f"{af_upper} {nh_entry_key}"
            )
            if index:
                exec_cmd += f" {index}"
            logger.debug("Executing command: %s", exec_cmd)
            output = self.device.execute(f"{exec_cmd} | display json | nomore")

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowFibNexthopEntries: empty output")

        parsed_json = load_json_robust(output)

        fibs = _get_fib_data(parsed_json, network_instance, af_lower)
        if not fibs:
            raise SchemaEmptyParserError(
                f"No FIB data found for NI={network_instance}, AF={af_lower}"
            )

        result: Dict[str, TypeAny] = {"network-instance": {}}

        for fib in fibs:
            container = fib.get(nh_container_key, {})
            entry_list = container.get(nh_entry_key, [])

            if not entry_list:
                continue

            ni_dict = result["network-instance"].setdefault(network_instance, {})
            ni_dict["address-family"] = _strip_ns(fib.get("address-family", ""))

            nh_entries = ni_dict.setdefault("nexthop-entries", {})

            for entry in entry_list:
                idx = entry.get("index")
                if idx is None:
                    continue

                idx_str = str(idx)
                entry_out: Dict[str, TypeAny] = {}

                for field in ("index", "eos0-nexthop-index", "source-nexthop-index",
                              "level", "flags"):
                    if field in entry:
                        entry_out[field] = entry[field]

                # Parse nested paths
                paths_container = entry.get("paths", {})
                path_list = paths_container.get(path_key, [])
                if path_list:
                    paths_out: Dict[str, TypeAny] = {}
                    for pidx, path in enumerate(path_list):
                        path_out: Dict[str, TypeAny] = {}
                        for pfield in ("path-id", "path-type", "nh-type", "next-hop",
                                       "push-label", "interface", "network-instance",
                                       "num-coll-paths", "igp-path-id", "igp-path-type"):
                            if pfield in path:
                                path_out[pfield] = path[pfield]
                        paths_out[str(pidx)] = path_out
                    entry_out["paths"] = paths_out

                nh_entries[idx_str] = entry_out

        if not result.get("network-instance"):
            raise SchemaEmptyParserError(
                f"No FIB nexthop entries found for NI={network_instance}, AF={af_lower}"
            )

        return result


class _FibLabelEntriesMixin:
    """Parsing logic for FIB label entries."""

    def _do_parse(
        self,
        network_instance: str,
        af: str,
        label: TypeOptional[str],
        output: TypeOptional[str],
    ) -> Dict:
        """Core parse logic for FIB label entries."""
        af_upper = af.upper()
        af_lower = af.lower()
        # Container: ipv4-label-entries / ipv6-label-entries
        label_container_key = f"{af_lower}-label-entries"
        # Entry list: ipv4-label-entry / ipv6-label-entry
        label_entry_key = f"{af_lower}-label-entry"

        if output is None:
            validate_input(network_instance, "network_instance")
            exec_cmd = (
                f"show network-instance {network_instance} fib "
                f"{af_upper} {label_entry_key}"
            )
            if label:
                exec_cmd += f" {label}"
            logger.debug("Executing command: %s", exec_cmd)
            output = self.device.execute(f"{exec_cmd} | display json | nomore")

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowFibLabelEntries: empty output")

        parsed_json = load_json_robust(output)

        fibs = _get_fib_data(parsed_json, network_instance, af_lower)
        if not fibs:
            raise SchemaEmptyParserError(
                f"No FIB data found for NI={network_instance}, AF={af_lower}"
            )

        result: Dict[str, TypeAny] = {"network-instance": {}}

        for fib in fibs:
            container = fib.get(label_container_key, {})
            entry_list = container.get(label_entry_key, [])

            if not entry_list:
                continue

            ni_dict = result["network-instance"].setdefault(network_instance, {})
            ni_dict["address-family"] = _strip_ns(fib.get("address-family", ""))

            label_entries = ni_dict.setdefault("label-entries", {})

            for entry in entry_list:
                local_label = entry.get("local-label")
                if local_label is None:
                    continue

                label_key_str = str(local_label)
                entry_out: Dict[str, TypeAny] = {}

                for field in ("local-label", "vpn-table-id", "next-hop-id",
                              "publish-id", "control-word", "flow-label",
                              "domain-name"):
                    if field in entry:
                        entry_out[field] = entry[field]

                label_entries[label_key_str] = entry_out

        if not result.get("network-instance"):
            raise SchemaEmptyParserError(
                f"No FIB label entries found for NI={network_instance}, AF={af_lower}"
            )

        return result


# ===================================================================
# ShowFibPrefixEntries — IPv4/IPv6 prefix entries (af as parameter)
# ===================================================================


class ShowFibPrefixEntries(_FibPrefixEntriesMixin, _FibPrefixEntriesSchema):
    """Parser for ArcOS FIB prefix entries (JSON format).

    Supports both IPv4 and IPv6 via the ``af`` parameter.

    Commands (before ``| display json | nomore``)::

        show network-instance {ni} fib {af} {af_prefix_entry}
        show network-instance {ni} fib {af} {af_prefix_entry} {prefix}
    """

    cli_command = [
        "show network-instance {network_instance} fib {af} ipv4-prefix-entry",
        "show network-instance {network_instance} fib {af} ipv4-prefix-entry {prefix}",
        "show network-instance {network_instance} fib {af} ipv6-prefix-entry",
        "show network-instance {network_instance} fib {af} ipv6-prefix-entry {prefix}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        af: str = "IPV4",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        """Parse FIB prefix entries for any address family.

        Args:
            network_instance: Network instance name (default ``"default"``).
            af: Address family — ``"IPV4"`` or ``"IPV6"`` (default ``"IPV4"``).
            prefix: Optional specific prefix to filter (e.g. ``"5.5.5.5/32"``).
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ``_FibPrefixEntriesSchema``.

        Raises:
            SchemaEmptyParserError: If no prefix entries are found.
        """
        return self._do_parse(network_instance, af, prefix, output)


# ===================================================================
# ShowFibNexthopEntries — IPv4/IPv6 nexthop entries (af as parameter)
# ===================================================================


class ShowFibNexthopEntries(_FibNexthopEntriesMixin, _FibNexthopEntriesSchema):
    """Parser for ArcOS FIB nexthop entries (JSON format).

    Supports both IPv4 and IPv6 via the ``af`` parameter.

    Commands (before ``| display json | nomore``)::

        show network-instance {ni} fib {af} {af_nexthop_entry}
        show network-instance {ni} fib {af} {af_nexthop_entry} {index}
    """

    cli_command = [
        "show network-instance {network_instance} fib {af} ipv4-nexthop-entry",
        "show network-instance {network_instance} fib {af} ipv4-nexthop-entry {index}",
        "show network-instance {network_instance} fib {af} ipv6-nexthop-entry",
        "show network-instance {network_instance} fib {af} ipv6-nexthop-entry {index}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        af: str = "IPV4",
        index: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        """Parse FIB nexthop entries for any address family.

        Args:
            network_instance: Network instance name (default ``"default"``).
            af: Address family — ``"IPV4"`` or ``"IPV6"`` (default ``"IPV4"``).
            index: Optional specific nexthop index to filter (e.g. ``"643"``).
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ``_FibNexthopEntriesSchema``.

        Raises:
            SchemaEmptyParserError: If no nexthop entries are found.
        """
        return self._do_parse(network_instance, af, index, output)


# ===================================================================
# ShowFibLabelEntries — IPv4/IPv6 label entries (af as parameter)
# ===================================================================


class ShowFibLabelEntries(_FibLabelEntriesMixin, _FibLabelEntriesSchema):
    """Parser for ArcOS FIB label entries (JSON format).

    Supports both IPv4 and IPv6 via the ``af`` parameter.

    Commands (before ``| display json | nomore``)::

        show network-instance {ni} fib {af} {af_label_entry}
        show network-instance {ni} fib {af} {af_label_entry} {label}
    """

    cli_command = [
        "show network-instance {network_instance} fib {af} ipv4-label-entry",
        "show network-instance {network_instance} fib {af} ipv4-label-entry {label}",
        "show network-instance {network_instance} fib {af} ipv6-label-entry",
        "show network-instance {network_instance} fib {af} ipv6-label-entry {label}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        af: str = "IPV4",
        label: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        """Parse FIB label entries for any address family.

        Args:
            network_instance: Network instance name (default ``"default"``).
            af: Address family — ``"IPV4"`` or ``"IPV6"`` (default ``"IPV4"``).
            label: Optional specific label to filter (e.g. ``"10005"``).
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ``_FibLabelEntriesSchema``.

        Raises:
            SchemaEmptyParserError: If no label entries are found.
        """
        return self._do_parse(network_instance, af, label, output)
