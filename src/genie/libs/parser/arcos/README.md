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

## Usage Examples

### Basic Usage

```python
from genie.libs.parser.arcos.show_interface import ShowInterface

# Parse all interfaces
parser = ShowInterface(device=device)
parsed_output = parser.cli()

# Parse specific interface
parsed_output = parser.cli(interface="swp1")
```

### ISIS Adjacency

```python
from genie.libs.parser.arcos.show_isis import ShowIsisAdjacency

parser = ShowIsisAdjacency(device=device)
# Get all adjacencies
output = parser.cli()
# Get specific neighbor
output = parser.cli(adj_router="rtr2")
```

## Input Validation

To ensure security and stability, all parsers validate input parameters before executing commands. Inputs are checked for:
- Being non-empty strings
- Containing only safe characters: alphanumeric, `-`, `_`, `.`, `:`, `/`, `*`

Invalid inputs will raise a `ValueError`.

## Troubleshooting

All parsers emit logs at `DEBUG` level, which include:
- The exact command being executed
- The raw output received from the device

To enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

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
