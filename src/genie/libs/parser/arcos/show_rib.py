"""ArcOS RIB (Routing Information Base) parsers.

Parsers for Arrcus ArcOS RIB OpenConfig-based JSON commands.

Provides two parser classes with ``af`` as a runtime parameter:

- ``ShowRibEntries``      — IPv4/IPv6 route entries
- ``ShowRibLabelEntries`` — IPv4/IPv6 MPLS label entries

All output is JSON-only via ``| display json | nomore``.
"""

import logging
from typing import Any as TypeAny, Dict, List, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional, Or
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.constants import (
    ARCOS_RIB,
    OPENCONFIG_NETWORK_INSTANCES,
)
from genie.libs.parser.arcos.utils import load_json_robust, validate_input

logger = logging.getLogger(__name__)

# Namespace prefixes stripped from values
_PREFIX_OC_TYPES = "openconfig-types:"
_PREFIX_OC_POLICY = "openconfig-policy-types:"


def _strip_ns(value: str) -> str:
    """Strip known OpenConfig namespace prefixes from a string value."""
    if not isinstance(value, str):
        return value
    for prefix in (_PREFIX_OC_TYPES, _PREFIX_OC_POLICY):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def _get_rib_data(
    json_output: Dict,
    network_instance: str,
    af: str,
) -> List[Dict]:
    """Navigate to the RIB array for a given network-instance and AF.

    Returns the ``arcos-rib:rib`` list filtered to the requested
    address-family, or an empty list if not found.

    The expected layout is::

        data[OPENCONFIG_NETWORK_INSTANCES].network-instance[]
            .name == network_instance
            .arcos-rib:rib[]
                .address-family == "openconfig-types:IPV4|IPV6"
    """
    af_upper = af.upper()
    af_match = f"{_PREFIX_OC_TYPES}{af_upper}"

    data = json_output.get("data", {})
    ni_container = data.get(OPENCONFIG_NETWORK_INSTANCES, {})

    for ni in ni_container.get("network-instance", []):
        if ni.get("name") != network_instance:
            continue
        for rib in ni.get(ARCOS_RIB, []):
            if rib.get("address-family") == af_match:
                return [rib]
    return []


# ===================================================================
# Shared schemas
# ===================================================================


class _RibEntriesSchema(MetaParser):
    """Shared schema for IPv4/IPv6 RIB route entries."""

    schema = {
        "network-instance": {
            Any(): {  # NI name ("default")
                Optional("address-family"): str,  # "IPV4" or "IPV6"
                Optional("entries"): {
                    Any(): {  # prefix key ("5.5.5.5/32")
                        Optional("prefix"): str,
                        Optional("best-protocol"): str,  # stripped
                        Optional("hw-update"): {
                            Optional("install-ack"): bool,
                            Optional("status-code"): int,
                            Optional("version"): str,
                        },
                        Optional("origins"): {
                            Any(): {  # origin index ("0", "1", ...)
                                Optional("origin-protocol"): str,  # stripped
                                Optional("protocol-name"): str,
                                Optional("metric"): int,
                                Optional("pref"): int,
                                Optional("label-pref"): int,
                                Optional("tag"): int,
                                Optional("route-type"): str,
                                Optional("nhid"): Or(str, int),
                                Optional("last-updated"): str,
                                Optional("flags"): str,
                                Optional("opaque-data"): str,
                                Optional("next-hops"): {
                                    Any(): {  # next-hop index ("0", "1", ...)
                                        Optional("pathid"): Or(str, int),
                                        Optional("type"): str,
                                        Optional("next-hop"): Or(str, int),
                                        Optional("network-instance"): str,
                                        Optional("interface"): str,
                                        Optional("weight"): int,
                                        Optional("flags"): str,
                                        Optional("pushed-mpls-label-stack"): list,
                                    }
                                },
                            }
                        },
                    }
                },
            }
        }
    }


class _RibLabelEntriesSchema(MetaParser):
    """Shared schema for IPv4/IPv6 RIB MPLS label entries."""

    schema = {
        "network-instance": {
            Any(): {  # NI name ("default")
                Optional("address-family"): str,  # "IPV4" or "IPV6"
                Optional("label-entries"): {
                    Any(): {  # label key ("10005")
                        Optional("label"): int,
                        Optional("label-type"): str,
                        Optional("vpn-table-id"): int,
                        Optional("protocol"): str,  # stripped
                        Optional("fec"): str,
                        Optional("nhid"): Or(str, int),
                        Optional("last-updated"): str,
                        Optional("time-since-creation"): str,
                        Optional("control-word"): bool,
                        Optional("flow-label"): bool,
                        Optional("flags"): str,
                    }
                },
            }
        }
    }


# ===================================================================
# Shared parsing helpers (mixed into parser classes)
# ===================================================================


class _RibEntriesMixin:
    """Parsing logic shared by route-entry parsers across address families."""

    def _do_parse(
        self,
        network_instance: str,
        af: str,
        prefix: TypeOptional[str],
        output: TypeOptional[str],
    ) -> Dict:
        """Core parse logic for RIB route entries."""
        af_upper = af.upper()
        af_lower = af.lower()
        entries_key = f"{af_lower}-entries"

        if output is None:
            validate_input(network_instance, "network_instance")
            if prefix:
                validate_input(prefix, "prefix")
            exec_cmd = (
                f"show network-instance {network_instance} rib "
                f"{af_upper} {entries_key}"
            )
            if prefix:
                exec_cmd += f" entry {prefix}"
            logger.debug("Executing command: %s", exec_cmd)
            output = self.device.execute(f"{exec_cmd} | display json | nomore")

        parsed_json = load_json_robust(output)

        ribs = _get_rib_data(parsed_json, network_instance, af_lower)
        if not ribs:
            raise SchemaEmptyParserError(
                f"No RIB data found for NI={network_instance}, AF={af_lower}"
            )

        result = self._parse_entries(ribs, network_instance, entries_key)

        if not result.get("network-instance"):
            raise SchemaEmptyParserError(
                f"No RIB entries found for NI={network_instance}, AF={af_lower}"
            )

        return result

    def _parse_entries(
        self,
        ribs: List[Dict],
        network_instance: str,
        entries_key: str,
    ) -> Dict:
        """Transform raw RIB JSON into the schema structure."""
        result: Dict[str, TypeAny] = {"network-instance": {}}

        for rib in ribs:
            entries_container = rib.get(entries_key, {})
            entry_list = entries_container.get("entry", [])

            if not entry_list:
                continue

            ni_dict = result["network-instance"].setdefault(network_instance, {})
            ni_dict["address-family"] = _strip_ns(rib.get("address-family", ""))

            entries_dict = ni_dict.setdefault("entries", {})

            for entry in entry_list:
                prefix = entry.get("prefix", "")
                if not prefix:
                    continue

                entry_out: Dict[str, TypeAny] = {}
                entry_out["prefix"] = prefix

                # best-protocol — strip namespace
                best_proto = entry.get("best-protocol")
                if best_proto is not None:
                    entry_out["best-protocol"] = _strip_ns(best_proto)

                # hw-update
                hw = entry.get("hw-update")
                if hw:
                    entry_out["hw-update"] = {}
                    for k in ("install-ack", "status-code", "version"):
                        if k in hw:
                            entry_out["hw-update"][k] = hw[k]

                # origins
                origins_container = entry.get("origins", {})
                origin_list = origins_container.get("origin", [])
                if origin_list:
                    entry_out["origins"] = self._parse_origins(origin_list)

                entries_dict[prefix] = entry_out

        return result

    def _parse_origins(self, origin_list: List[Dict]) -> Dict:
        """Parse the origins array, keyed by stringified index."""
        origins_out: Dict[str, TypeAny] = {}

        for idx, origin in enumerate(origin_list):
            origin_out: Dict[str, TypeAny] = {}

            # Simple string/int fields
            simple_fields = (
                "protocol-name", "metric", "pref", "label-pref",
                "tag", "route-type", "nhid", "last-updated",
                "flags", "opaque-data",
            )
            for field in simple_fields:
                if field in origin:
                    origin_out[field] = origin[field]

            # origin-protocol — strip namespace
            op = origin.get("origin-protocol")
            if op is not None:
                origin_out["origin-protocol"] = _strip_ns(op)

            # next-hops
            nh_container = origin.get("next-hops", {})
            nh_list = nh_container.get("next-hop", [])
            if nh_list:
                origin_out["next-hops"] = self._parse_next_hops(nh_list)

            origins_out[str(idx)] = origin_out

        return origins_out

    def _parse_next_hops(self, nh_list: List[Dict]) -> Dict:
        """Parse the next-hops array, keyed by stringified index."""
        nhs_out: Dict[str, TypeAny] = {}

        nh_fields = (
            "pathid", "type", "next-hop", "network-instance",
            "interface", "weight", "flags", "pushed-mpls-label-stack",
        )

        for idx, nh in enumerate(nh_list):
            nh_out: Dict[str, TypeAny] = {}
            for field in nh_fields:
                if field in nh:
                    nh_out[field] = nh[field]
            nhs_out[str(idx)] = nh_out

        return nhs_out


class _RibLabelEntriesMixin:
    """Parsing logic shared by label-entry parsers across address families."""

    def _do_parse(
        self,
        network_instance: str,
        af: str,
        label: TypeOptional[str],
        output: TypeOptional[str],
    ) -> Dict:
        """Core parse logic for RIB label entries."""
        af_upper = af.upper()
        af_lower = af.lower()
        label_key = f"{af_lower}-label-entries"

        if output is None:
            validate_input(network_instance, "network_instance")
            if label:
                validate_input(label, "label")
            exec_cmd = (
                f"show network-instance {network_instance} rib "
                f"{af_upper} {label_key}"
            )
            if label:
                exec_cmd += f" entry {label}"
            logger.debug("Executing command: %s", exec_cmd)
            output = self.device.execute(f"{exec_cmd} | display json | nomore")

        parsed_json = load_json_robust(output)

        ribs = _get_rib_data(parsed_json, network_instance, af_lower)
        if not ribs:
            raise SchemaEmptyParserError(
                f"No RIB data found for NI={network_instance}, AF={af_lower}"
            )

        result = self._parse_label_entries(ribs, network_instance, label_key)

        if not result.get("network-instance"):
            raise SchemaEmptyParserError(
                f"No RIB label entries found for NI={network_instance}, AF={af_lower}"
            )

        return result

    def _parse_label_entries(
        self,
        ribs: List[Dict],
        network_instance: str,
        label_key: str,
    ) -> Dict:
        """Transform raw RIB label JSON into the schema structure."""
        result: Dict[str, TypeAny] = {"network-instance": {}}

        label_fields = (
            "label", "label-type", "vpn-table-id", "fec", "nhid",
            "last-updated", "time-since-creation", "control-word",
            "flow-label", "flags",
        )

        for rib in ribs:
            label_container = rib.get(label_key, {})
            entry_list = label_container.get("entry", [])

            if not entry_list:
                continue

            ni_dict = result["network-instance"].setdefault(network_instance, {})
            ni_dict["address-family"] = _strip_ns(rib.get("address-family", ""))

            label_entries_dict = ni_dict.setdefault("label-entries", {})

            for entry in entry_list:
                label_val = entry.get("label")
                if label_val is None:
                    continue

                label_key_str = str(label_val)
                entry_out: Dict[str, TypeAny] = {}

                for field in label_fields:
                    if field in entry:
                        entry_out[field] = entry[field]

                # protocol — strip namespace
                proto = entry.get("protocol")
                if proto is not None:
                    entry_out["protocol"] = _strip_ns(proto)

                label_entries_dict[label_key_str] = entry_out

        return result


# ===================================================================
# ShowRibEntries — IPv4/IPv6 route entries (af as parameter)
# ===================================================================


class ShowRibEntries(_RibEntriesMixin, _RibEntriesSchema):
    """Parser for ArcOS RIB route entries (JSON format).

    Supports both IPv4 and IPv6 via the ``af`` parameter,
    following the same pattern as ``ShowIsisRoute`` with ``{afi}``.

    Commands (before ``| display json | nomore``)::

        show network-instance {ni} rib {af} {af_entries}                  # all entries
        show network-instance {ni} rib {af} {af_entries} entry {prefix}   # single entry
    """

    cli_command = [
        "show network-instance {network_instance} rib {af} ipv4-entries",
        "show network-instance {network_instance} rib {af} ipv4-entries entry {prefix}",
        "show network-instance {network_instance} rib {af} ipv6-entries",
        "show network-instance {network_instance} rib {af} ipv6-entries entry {prefix}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        af: str = "IPV4",
        prefix: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        """Parse RIB route entries for any address family.

        Args:
            network_instance: Network instance name (default ``"default"``).
            af: Address family — ``"IPV4"`` or ``"IPV6"`` (default ``"IPV4"``).
            prefix: Optional specific prefix to filter (e.g. ``"5.5.5.5/32"``).
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ``_RibEntriesSchema``.

        Raises:
            SchemaEmptyParserError: If no RIB entries are found.
        """
        return self._do_parse(network_instance, af, prefix, output)


# ===================================================================
# ShowRibLabelEntries — IPv4/IPv6 MPLS label entries (af as parameter)
# ===================================================================


class ShowRibLabelEntries(_RibLabelEntriesMixin, _RibLabelEntriesSchema):
    """Parser for ArcOS RIB MPLS label entries (JSON format).

    Supports both IPv4 and IPv6 via the ``af`` parameter.

    Commands (before ``| display json | nomore``)::

        show network-instance {ni} rib {af} {af_label_entries}                  # all labels
        show network-instance {ni} rib {af} {af_label_entries} entry {label}    # single label
    """

    cli_command = [
        "show network-instance {network_instance} rib {af} ipv4-label-entries",
        "show network-instance {network_instance} rib {af} ipv4-label-entries entry {label}",
        "show network-instance {network_instance} rib {af} ipv6-label-entries",
        "show network-instance {network_instance} rib {af} ipv6-label-entries entry {label}",
    ]

    def cli(
        self,
        network_instance: str = "default",
        af: str = "IPV4",
        prefix: TypeOptional[str] = None,
        label: TypeOptional[str] = None,
        output: TypeOptional[str] = None,
    ) -> TypeAny:
        """Parse RIB MPLS label entries for any address family.

        Args:
            network_instance: Network instance name (default ``"default"``).
            af: Address family — ``"IPV4"`` or ``"IPV6"`` (default ``"IPV4"``).
            prefix: Deprecated alias for ``label`` (backward compatibility).
            label: Optional specific label to filter (e.g. ``"10005"``).
            output: Pre-captured command output (for unit tests).

        Returns:
            dict: Parsed output matching ``_RibLabelEntriesSchema``.

        Raises:
            SchemaEmptyParserError: If no label entries are found.
        """
        if label is None and prefix is not None:
            label = prefix
        return self._do_parse(network_instance, af, label, output)


# ===================================================================
# Backward-compatible aliases
# ===================================================================

ShowRibIpv4Entries = ShowRibEntries
ShowRibIpv6Entries = ShowRibEntries
ShowRibIpv4LabelEntries = ShowRibLabelEntries
ShowRibIpv6LabelEntries = ShowRibLabelEntries
