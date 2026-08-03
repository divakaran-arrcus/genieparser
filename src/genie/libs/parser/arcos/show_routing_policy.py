"""show_routing_policy.py

ArcOS parsers for the following show commands:
    * show routing-policy defined-sets
    * show routing-policy policy-definition
    * show running-config routing-policy
"""

from __future__ import annotations

import logging
from typing import Any as TypeAny, Dict as TypeDict, Optional as TypeOptional

from genie.metaparser import MetaParser
from genie.metaparser.util.schemaengine import Any, Optional
from genie.metaparser.util.exceptions import SchemaEmptyParserError

from genie.libs.parser.arcos.utils import load_json_robust


logger = logging.getLogger(__name__)


# OpenConfig routing-policy namespace used by ArcOS
OPENCONFIG_ROUTING_POLICY = "openconfig-routing-policy:routing-policy"

# ArcOS routing-policy augments namespaces (for string-sets, next-hop-sets)
ARCOS_RP_STRING_SETS = "arcos-openconfig-routing-policy-augments:string-sets"
ARCOS_RP_NEXT_HOP_SETS = "arcos-openconfig-routing-policy-augments:next-hop-sets"


class ShowRoutingPolicyDefinedSetsSchema(MetaParser):
    """Schema for ``show routing-policy defined-sets`` on ArcOS.

    The parser normalizes various defined-set families into a single
    ``routing_policy.defined_sets`` dictionary with the following shape::

        {
          "routing-policy": {
            "defined-sets": {
              "prefix-sets": {
                <name>: {
                  "name": <str>,
                  "prefixes": [
                    {"ip-prefix": <str>, "masklength-range": <str>},
                    ...
                  ],
                  "is-martian": <bool>,   # optional
                },
                ...
              },
              "string-sets": {
                <name>: {
                  "name": <str>,
                  "strings": [
                    {"value": <str>, "match-type": <str?>},
                    ...
                  ],
                },
              },
              "tag-sets": {
                <name>: {
                  "name": <str>,
                  "tags": [<int>, ...],
                },
              },
              "next-hop-sets": {
                <name>: {
                  "name": <str>,
                  "addresses": [<str>, ...],
                },
              },
            }
          }
        }
    """

    schema = {
        "routing-policy": {
            "defined-sets": {
                Optional("prefix-sets"): {
                    Any(): {
                        "name": str,
                        # Loosen validation: just require a list of prefixes; the
                        # parser already normalizes element structure.
                        "prefixes": list,
                        Optional("is-martian"): bool,
                    }
                },
                Optional("string-sets"): {
                    Any(): {
                        "name": str,
                        # Require only that strings is a list; individual elements
                        # are normalized by the parser logic and validated by unit tests.
                        "strings": list,
                    }
                },
                Optional("tag-sets"): {
                    Any(): {
                        "name": str,
                        # Likewise, just enforce list type here.
                        "tags": list,
                    }
                },
                Optional("next-hop-sets"): {
                    Any(): {
                        "name": str,
                        # And for next-hop-sets, only require a list of addresses.
                        "addresses": list,
                    }
                },
                Optional("ext-community-sets"): {
                    Any(): {
                        "name": str,
                        "members": list,
                    }
                },
                Optional("community-sets"): {
                    Any(): {
                        "name": str,
                        "members": list,
                    }
                },
                Optional("as-path-sets"): {
                    Any(): {
                        "name": str,
                        "members": list,
                    }
                },
            }
        }
    }


class ShowRoutingPolicyDefinedSets(ShowRoutingPolicyDefinedSetsSchema):
    """Parser for ArcOS ``show routing-policy defined-sets`` (JSON format).

    The parser expects JSON output of the form::

        data[OPENCONFIG_ROUTING_POLICY]["defined-sets"]

    When no explicit output is provided, the parser runs::

        show routing-policy defined-sets | display json | nomore
    """

    cli_command = "show routing-policy defined-sets"

    def cli(self, output: TypeOptional[TypeAny] = None) -> TypeDict[str, TypeAny]:  # type: ignore[override]
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowRoutingPolicyDefinedSets: empty output")

        logger.debug("Parsing output: %s", output)

        ret: TypeDict[str, TypeAny] = {"routing-policy": {"defined-sets": {}}}
        defined_sets_out: TypeDict[str, TypeAny] = ret["routing-policy"][
            "defined-sets"
        ]

        parsed_json = load_json_robust(output)
        data = parsed_json.get("data", {})
        rp_root = data.get(OPENCONFIG_ROUTING_POLICY, {}) or {}
        defined_sets_raw = rp_root.get("defined-sets", {}) or {}

        # --------------------------------------------------------------
        # Prefix-sets
        # --------------------------------------------------------------
        prefix_sets_container = defined_sets_raw.get("prefix-sets", {}) or {}
        prefix_sets_list = prefix_sets_container.get("prefix-set", []) or []

        prefix_sets: TypeDict[str, TypeAny] = {}
        for ps in prefix_sets_list:
            name = ps.get("prefix-set-name")
            if not name:
                continue

            prefixes_block = (ps.get("prefixes", {}) or {}).get("prefix", []) or []
            prefixes = []
            for pref in prefixes_block:
                node = pref.get("state") or pref.get("config") or pref
                ip_prefix = node.get("ip-prefix")
                mask_range = node.get("masklength-range")
                if ip_prefix is None or mask_range is None:
                    continue
                prefixes.append(
                    {"ip-prefix": str(ip_prefix), "masklength-range": str(mask_range)}
                )

            if not prefixes:
                continue

            entry: TypeDict[str, TypeAny] = {"name": str(name), "prefixes": prefixes}
            if name in {"__IPV4_MARTIAN_PREFIX_SET__", "__IPV6_MARTIAN_PREFIX_SET__"}:
                entry["is-martian"] = True

            prefix_sets[str(name)] = entry

        if prefix_sets:
            defined_sets_out["prefix-sets"] = prefix_sets

        # --------------------------------------------------------------
        # String-sets (ArcOS augments)
        # --------------------------------------------------------------
        string_sets_container = defined_sets_raw.get(ARCOS_RP_STRING_SETS, {}) or {}
        string_sets_list = string_sets_container.get("string-set", []) or []

        string_sets: TypeDict[str, TypeAny] = {}
        for ss in string_sets_list:
            name = ss.get("name")
            if not name:
                continue

            strings_block = (ss.get("strings", {}) or {}).get("string", []) or []
            strings = []
            for s in strings_block:
                node = s.get("state") or s.get("config") or s
                value = node.get("string-value")
                if value is None:
                    continue
                entry: TypeDict[str, TypeAny] = {"value": str(value)}
                match_type = node.get("type")
                if match_type is not None:
                    entry["match-type"] = str(match_type)
                strings.append(entry)

            if not strings:
                continue

            string_sets[str(name)] = {"name": str(name), "strings": strings}

        if string_sets:
            defined_sets_out["string-sets"] = string_sets

        # --------------------------------------------------------------
        # Tag-sets
        # --------------------------------------------------------------
        tag_sets_container = defined_sets_raw.get("tag-sets", {}) or {}
        tag_sets_list = tag_sets_container.get("tag-set", []) or []

        tag_sets: TypeDict[str, TypeAny] = {}
        for ts in tag_sets_list:
            name = ts.get("tag-set-name")
            if not name:
                continue

            node = ts.get("state") or ts.get("config") or ts
            raw_values = node.get("tag-value") or []
            if not isinstance(raw_values, list):
                raw_values = [raw_values]

            tags = []
            for tv in raw_values:
                try:
                    tags.append(int(tv))
                except Exception:
                    continue

            if not tags:
                continue

            tag_sets[str(name)] = {"name": str(name), "tags": tags}

        if tag_sets:
            defined_sets_out["tag-sets"] = tag_sets

        # --------------------------------------------------------------
        # Next-hop-sets (ArcOS augments)
        # --------------------------------------------------------------
        next_hop_sets_container = defined_sets_raw.get(ARCOS_RP_NEXT_HOP_SETS, {}) or {}
        next_hop_sets_list = next_hop_sets_container.get("next-hop-set", []) or []

        next_hop_sets: TypeDict[str, TypeAny] = {}
        for nh in next_hop_sets_list:
            name = nh.get("next-hop-set-name")
            if not name:
                continue

            node = nh.get("state") or nh.get("config") or nh
            raw_addrs = node.get("address") or []
            if not isinstance(raw_addrs, list):
                raw_addrs = [raw_addrs]

            addresses = [str(a) for a in raw_addrs if a is not None]
            if not addresses:
                continue

            next_hop_sets[str(name)] = {"name": str(name), "addresses": addresses}

        if next_hop_sets:
            defined_sets_out["next-hop-sets"] = next_hop_sets

        # --------------------------------------------------------------
        # BGP Defined-Sets (ext-community, community, as-path)
        # --------------------------------------------------------------
        bgp_ds = defined_sets_raw.get(
            "openconfig-bgp-policy:bgp-defined-sets", {}
        ) or {}

        # Ext-community-sets
        ecs_container = bgp_ds.get("ext-community-sets", {}) or {}
        ecs_list = ecs_container.get("ext-community-set", []) or []
        ext_community_sets = {}
        for ecs in ecs_list:
            name = ecs.get("ext-community-set-name")
            if not name:
                continue
            node = ecs.get("config") or ecs.get("state") or ecs
            members = node.get("ext-community-member", [])
            if not isinstance(members, list):
                members = [members]
            ext_community_sets[name] = {
                "name": name,
                "members": members,
            }
        if ext_community_sets:
            defined_sets_out["ext-community-sets"] = ext_community_sets

        # Community-sets
        cs_container = bgp_ds.get("community-sets", {}) or {}
        cs_list = cs_container.get("community-set", []) or []
        community_sets = {}
        for cs in cs_list:
            name = cs.get("community-set-name")
            if not name:
                continue
            node = cs.get("config") or cs.get("state") or cs
            members = node.get("community-member", [])
            if not isinstance(members, list):
                members = [members]
            community_sets[name] = {
                "name": name,
                "members": members,
            }
        if community_sets:
            defined_sets_out["community-sets"] = community_sets

        # AS-path-sets
        as_container = bgp_ds.get("as-path-sets", {}) or {}
        as_list = as_container.get("as-path-set", []) or []
        as_path_sets = {}
        for aps in as_list:
            name = aps.get("as-path-set-name")
            if not name:
                continue
            node = aps.get("config") or aps.get("state") or aps
            members = node.get("as-path-set-member", [])
            if not isinstance(members, list):
                members = [members]
            as_path_sets[name] = {
                "name": name,
                "members": members,
            }
        if as_path_sets:
            defined_sets_out["as-path-sets"] = as_path_sets

        return ret


class ShowRoutingPolicyPolicyDefinitionSchema(MetaParser):
    schema = {
        "routing-policy": {
            Optional("policy-definitions"): {
                Any(): {
                    "name": str,
                    "statements": {
                        Any(): {
                            "name": str,
                            Optional("auto-seq-num"): int,
                            Optional("conditions"): {
                                Optional("match-prefix-set"): {
                                    Optional("prefix-set"): str,
                                    "match-set-options": str,
                                },
                                Optional("match-next-hop-set"): dict,
                                Optional("match-tag-set"): dict,
                                Optional("match-interface"): dict,
                                Optional("install-protocol-eq"): str,
                                Optional("call-policy"): dict,
                                Optional("call-policy-expression"): str,
                                Optional("bgp-conditions"): dict,
                                Optional("igp-conditions"): dict,
                            },
                            Optional("actions"): {
                                Optional("accept-route"): bool,
                                Optional("reject-route"): bool,
                                Optional("next-policy"): bool,
                                Optional("igp-actions"): {
                                    Optional("set-tag"): int,
                                    Optional("isis-actions"): {
                                        Optional("set-level"): int,
                                    },
                                },
                                Optional("bgp-actions"): dict,
                                Optional("ospf-actions"): {
                                    Optional("set-metric"): int,
                                },
                                Optional("srv6-oam-actions"): dict,
                            },
                        }
                    },
                }
            }
        }
    }


class ShowRoutingPolicyPolicyDefinition(ShowRoutingPolicyPolicyDefinitionSchema):
    cli_command = "show routing-policy policy-definition"

    def cli(self, output: TypeOptional[TypeAny] = None) -> TypeDict[str, TypeAny]:  # type: ignore[override]
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowRoutingPolicyPolicyDefinition: empty output")

        logger.debug("Parsing output: %s", output)

        ret: TypeDict[str, TypeAny] = {"routing-policy": {"policy-definitions": {}}}
        policy_definitions: TypeDict[str, TypeAny] = ret["routing-policy"]["policy-definitions"]

        parsed_json = load_json_robust(output)
        data = parsed_json.get("data", {})
        rp_root = data.get(OPENCONFIG_ROUTING_POLICY, {}) or {}
        pd_container = rp_root.get("policy-definitions", {}) or {}
        pd_list = pd_container.get("policy-definition", []) or []

        for pd in pd_list:
            name = pd.get("name")
            if not name:
                continue

            policy_name = str(name)
            policy_entry: TypeDict[str, TypeAny] = {"name": policy_name, "statements": {}}

            statements_container = pd.get("statements", {}) or {}
            statements_list = statements_container.get("statement", []) or []

            for st in statements_list:
                stmt_name = st.get("name")
                if stmt_name is None:
                    continue

                stmt_key = str(stmt_name)
                stmt_entry: TypeDict[str, TypeAny] = {"name": stmt_key}

                state_block = st.get("state") or {}
                auto_seq = state_block.get("auto-seq-num")
                if auto_seq is not None:
                    try:
                        stmt_entry["auto-seq-num"] = int(auto_seq)
                    except Exception:
                        pass

                conditions_raw = st.get("conditions") or {}
                conditions = self._parse_conditions(conditions_raw)
                if conditions:
                    stmt_entry["conditions"] = conditions

                actions_raw = st.get("actions") or {}
                actions = self._parse_actions(actions_raw)
                if actions:
                    stmt_entry["actions"] = actions

                policy_entry["statements"][stmt_key] = stmt_entry

            if policy_entry["statements"]:
                policy_definitions[policy_name] = policy_entry

        if not policy_definitions:
            ret["routing-policy"].pop("policy-definitions", None)

        return ret

    def _parse_conditions(self, conditions_raw: TypeDict[str, TypeAny]) -> TypeDict[str, TypeAny]:
        conditions: TypeDict[str, TypeAny] = {}

        match_prefix_set_raw = conditions_raw.get("match-prefix-set") or {}
        node = match_prefix_set_raw.get("state") or match_prefix_set_raw.get("config") or match_prefix_set_raw
        source = node or {}

        prefix_set = source.get("prefix-set")
        match_set_options = source.get("match-set-options")

        if prefix_set is not None or match_set_options is not None:
            entry: TypeDict[str, TypeAny] = {}
            if prefix_set is not None:
                entry["prefix-set"] = str(prefix_set)
            if match_set_options is not None:
                entry["match-set-options"] = str(match_set_options)
            else:
                entry["match-set-options"] = "ANY"
            conditions["match-prefix-set"] = entry

        # Match tag-set
        match_tag_set_raw = conditions_raw.get("match-tag-set") or {}
        node = match_tag_set_raw.get("state") or match_tag_set_raw.get("config") or match_tag_set_raw
        source = node or {}

        mts_options = source.get("match-set-options")
        if mts_options is not None:
            conditions["match-tag-set"] = {"match-set-options": str(mts_options)}

        # Match next-hop-set (ArcOS augments use a namespaced key)
        nh_key_ns = "arcos-openconfig-routing-policy-augments:match-next-hop-set"
        match_nh_raw = conditions_raw.get(nh_key_ns) or conditions_raw.get("match-next-hop-set") or {}
        node = match_nh_raw.get("state") or match_nh_raw.get("config") or match_nh_raw
        source = node or {}

        mnh_options = source.get("match-set-options")
        if mnh_options is not None:
            conditions["match-next-hop-set"] = {"match-set-options": str(mnh_options)}

        return conditions

    def _parse_actions(self, actions_raw: TypeDict[str, TypeAny]) -> TypeDict[str, TypeAny]:
        actions: TypeDict[str, TypeAny] = {}

        node = actions_raw.get("state") or actions_raw.get("config") or actions_raw
        cfg = node or {}

        if "accept-route" in cfg:
            actions["accept-route"] = bool(cfg.get("accept-route"))
        if "reject-route" in cfg:
            actions["reject-route"] = bool(cfg.get("reject-route"))

        # ArcOS augments: next-policy may appear under a namespaced key
        next_policy_ns_key = "arcos-openconfig-routing-policy-augments:next-policy"
        if next_policy_ns_key in cfg:
            actions["next-policy"] = True
        elif "next-policy" in cfg:
            actions["next-policy"] = bool(cfg.get("next-policy"))

        igp_raw = actions_raw.get("igp-actions") or {}
        igp_actions: TypeDict[str, TypeAny] = {}

        # ArcOS may place igp-actions under either "config" or "state";
        # prefer "config" but fall back to "state" to support both
        # running-config and operational JSON representations.
        igp_cfg = igp_raw.get("config") or igp_raw.get("state") or {}
        set_tag = igp_cfg.get("set-tag")
        if set_tag is not None:
            try:
                igp_actions["set-tag"] = int(set_tag)
            except Exception:
                pass

        isis_raw = igp_raw.get("openconfig-isis-policy:isis-actions") or {}
        # Likewise, ISIS actions can be under "config" or "state".
        isis_cfg = isis_raw.get("config") or isis_raw.get("state") or {}
        set_level = isis_cfg.get("set-level")
        isis_actions: TypeDict[str, TypeAny] = {}
        if set_level is not None:
            try:
                isis_actions["set-level"] = int(set_level)
            except Exception:
                pass
        if isis_actions:
            igp_actions["isis-actions"] = isis_actions

        if igp_actions:
            actions["igp-actions"] = igp_actions

        ospf_raw = actions_raw.get("arcos-ospf-policy:ospf-actions") or {}
        ospf_actions: TypeDict[str, TypeAny] = {}

        set_metric_container = ospf_raw.get("set-metric") or {}
        # OSPF set-metric may also use either "config" or "state" nodes.
        metric_cfg = (
            set_metric_container.get("config")
            or set_metric_container.get("state")
            or {}
        )
        metric = metric_cfg.get("metric")
        if metric is not None:
            try:
                ospf_actions["set-metric"] = int(metric)
            except Exception:
                pass

        if ospf_actions:
            actions["ospf-actions"] = ospf_actions

        return actions


def _get_schema_value(schema_dict, target_key):
    """Look up a value in a schema dict where the key may be wrapped in Optional().

    MetaParser schema dicts use ``Optional("key")`` objects as keys, so a
    plain ``schema["key"]`` lookup fails with a ``KeyError``.  This helper
    iterates the dict and matches by the string representation of the key.
    """
    for k, v in schema_dict.items():
        key_str = k.schema if isinstance(k, Optional) else k
        if key_str == target_key:
            return v
    raise KeyError(f"{target_key!r} not found in schema dict")


class ShowRoutingPolicyConfigSchema(MetaParser):
    """Schema for ``show running-config routing-policy`` on ArcOS.

    This parser combines the normalized ``defined_sets`` and
    ``policy_definitions`` models into a single ``routing_policy`` tree.
    """

    schema = {
        "routing-policy": {
            Optional("defined-sets"): ShowRoutingPolicyDefinedSetsSchema.schema["routing-policy"][
                "defined-sets"
            ],
            Optional("policy-definitions"): _get_schema_value(
                ShowRoutingPolicyPolicyDefinitionSchema.schema["routing-policy"],
                "policy-definitions",
            ),
        }
    }


class ShowRoutingPolicyConfig(ShowRoutingPolicyConfigSchema):
    cli_command = "show running-config routing-policy"

    def cli(self, output: TypeOptional[TypeAny] = None) -> TypeDict[str, TypeAny]:  # type: ignore[override]
        if output is None:
            cmd = f"{self.cli_command} | display json | nomore"
            logger.debug("Executing command: %s", cmd)
            output = self.device.execute(cmd)

        if not output or not output.strip():
            raise SchemaEmptyParserError("ShowRoutingPolicyConfig: empty output")

        logger.debug("Parsing output: %s", output)

        ret: TypeDict[str, TypeAny] = {"routing-policy": {}}

        # Reuse the existing parsers on the same JSON output so that
        # running-config uses the exact same normalization logic.
        ds_parser = ShowRoutingPolicyDefinedSets(device=self.device)
        ds_result = ds_parser.cli(output=output)
        ds_root = ds_result.get("routing-policy", {})
        defined_sets = ds_root.get("defined-sets") or {}
        if defined_sets:
            ret["routing-policy"]["defined-sets"] = defined_sets

        pd_parser = ShowRoutingPolicyPolicyDefinition(device=self.device)
        pd_result = pd_parser.cli(output=output)
        pd_root = pd_result.get("routing-policy", {})
        policy_definitions = pd_root.get("policy-definitions") or {}
        if policy_definitions:
            ret["routing-policy"]["policy-definitions"] = policy_definitions

        return ret
