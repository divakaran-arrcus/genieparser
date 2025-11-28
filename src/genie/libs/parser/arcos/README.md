# ArcOS Parsers

This directory contains Genie parsers for Arrcus ArcOS.

## Overview

The parsers in this module are designed to handle JSON output from ArcOS OpenConfig-based commands. They leverage the `display json` pipe option available in the ArcOS CLI.

## Supported Commands

| Parser Class | CLI Command |
|--------------|-------------|
| `ShowInterface` | `show interface` |
| `ShowIsisAdjacency` | `show network-instance * protocol ISIS * interface * level * adjacency` |
| `ShowIsisConfig` | `show running-config network-instance * protocol ISIS` |
| `ShowIsisLsp` | `show network-instance * protocol ISIS * level * link-state-database` |
| `ShowIsisInterface` | `show network-instance * protocol ISIS * interface` |
| `ShowIsisRoute` | `show network-instance * protocol ISIS * route` |
| `ShowIsisGlobal` | `show network-instance * protocol ISIS * global state` |
| `ShowSrv6Config` | `show running-config network-instance * srv6` |
| `ShowSrv6Locator` | `show network-instance * srv6 locator` |
| `ShowVersion` | `show version` |

## OpenConfig Namespaces

These parsers rely on OpenConfig YANG models. Key namespaces used include:
- `openconfig-interfaces`
- `openconfig-network-instance`
- `openconfig-system`

ArcOS-specific augments are also handled, typically prefixed with `arcos-`.

## Testing

Unit tests are located in the `tests/` subdirectory. To run them:

```bash
python -m pytest src/genie/libs/parser/arcos/tests/ -v
```
