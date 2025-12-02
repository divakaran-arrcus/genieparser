# ArcOS Parsers

This directory contains Genie parsers for Arrcus ArcOS.

## Overview

The parsers in this module are designed to handle JSON output from ArcOS OpenConfig-based commands. They leverage the `display json` pipe option available in the ArcOS CLI. This project is part of the larger Genie network automation framework.

## Supported Commands

### Interface Parsers

| Parser Class | CLI Command | Module |
|--------------|-------------|--------|
| `ShowInterface` | `show interface [<interface>]` | `show_interface` |

### ISIS Parsers

| Parser Class | CLI Command | Module |
|--------------|-------------|--------|
| `ShowIsisAdjacency` | `show network-instance * protocol ISIS * interface * level * adjacency [<adj_router>]` | `show_isis` |
| `ShowIsisLsp` | `show network-instance * protocol ISIS * level * link-state-database [lsp <lsp_id>]` | `show_isis` |
| `ShowIsisInterface` | `show network-instance * protocol ISIS * interface` | `show_isis` |
| `ShowIsisConfig` | `show running-config network-instance * protocol ISIS` | `show_isis` |
| `ShowIsisRoute` | `show network-instance * protocol ISIS * route` | `show_isis` |
| `ShowIsisRedistributeRoute` | `show network-instance * protocol ISIS * redistribute-route` | `show_isis` |
| `ShowIsisGlobal` | `show network-instance * protocol ISIS * global state` | `show_isis` |
| `ShowIsisFastReroute` | `show network-instance * protocol ISIS * fast-reroute` | `show_isis` |
| `ShowIsisFlexAlgoFastReroute` | `show network-instance * protocol ISIS * flexible-algorithm * fast-reroute` | `show_isis` |
| `ShowIsisFlexAlgoRoute` | `show network-instance * protocol ISIS * flexible-algorithm * route` | `show_isis` |

### SRv6 Parsers

| Parser Class | CLI Command | Module |
|--------------|-------------|--------|
| `ShowSrv6Config` | `show running-config network-instance {instance} srv6 [locator <locator>]` | `show_srv6` |
| `ShowSrv6Locator` | `show network-instance {instance} srv6 locator [<locator_name>]` | `show_srv6` |

### Routing Policy Parsers

| Parser Class | CLI Command | Module |
|--------------|-------------|--------|
| `ShowRoutingPolicyDefinedSets` | `show routing-policy defined-sets` | `show_routing_policy` |
| `ShowRoutingPolicyPolicyDefinition` | `show routing-policy policy-definition` | `show_routing_policy` |
| `ShowRunningConfigRoutingPolicy` | `show running-config routing-policy` | `show_routing_policy` |

### System Parsers

| Parser Class | CLI Command | Module |
|--------------|-------------|--------|
| `ShowVersion` | `show version` | `show_version` |

## Usage Examples

### Basic Interface Usage

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

### ISIS LSP Database

```python
from genie.libs.parser.arcos.show_isis import ShowIsisLsp

parser = ShowIsisLsp(device=device)
# Get all LSPs
output = parser.cli()
# Get specific LSP
output = parser.cli(lsp_id="0000.0000.0001.00-00")
```

### Routing Policy

```python
from genie.libs.parser.arcos.show_routing_policy import (
    ShowRoutingPolicyDefinedSets,
    ShowRoutingPolicyPolicyDefinition,
    ShowRunningConfigRoutingPolicy,
)

# Parse defined-sets (prefix-sets, string-sets, tag-sets, next-hop-sets)
parser = ShowRoutingPolicyDefinedSets(device=device)
output = parser.cli()

# Parse policy definitions with statements, conditions, and actions
parser = ShowRoutingPolicyPolicyDefinition(device=device)
output = parser.cli()

# Parse full running-config (combines defined-sets and policy-definitions)
parser = ShowRunningConfigRoutingPolicy(device=device)
output = parser.cli()
```

### SRv6 Locator

```python
from genie.libs.parser.arcos.show_srv6 import ShowSrv6Config, ShowSrv6Locator

# ShowSrv6Config - all instances (default)
parser = ShowSrv6Config(device=device)
output = parser.cli()

# ShowSrv6Config - specific instance
output = parser.cli(instance="default")

# ShowSrv6Config - specific instance and locator
output = parser.cli(instance="default", locator="LOC1")

# ShowSrv6Locator - all instances (default)
parser = ShowSrv6Locator(device=device)
output = parser.cli()

# ShowSrv6Locator - specific instance
output = parser.cli(instance="default")

# ShowSrv6Locator - specific instance and locator name
output = parser.cli(instance="default", locator_name="LOC1")
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

## Architecture

### Module Structure

```
arcos/
├── constants.py          # Shared OpenConfig namespace constants
├── utils.py              # Utility functions (JSON parsing, input validation)
├── show_interface.py     # Interface parsers
├── show_isis.py          # ISIS protocol parsers
├── show_routing_policy.py # Routing policy parsers
├── show_srv6.py          # SRv6 parsers
├── show_version.py       # System version parser
└── tests/                # Unit tests
    ├── test_arcos_interface.py
    ├── test_arcos_isis.py
    ├── test_arcos_routing_policy.py
    ├── test_arcos_show_version.py
    ├── test_arcos_srv6.py
    └── test_samples/     # Sample JSON test data
```

### Development Conventions

- Parsers inherit from `genie.metaparser.MetaParser` with a corresponding schema class
- Each parser class corresponds to a specific `show` command on an ArcOS device
- Parsers expect JSON output from the device (via `| display json | nomore`)
- Use `load_json_robust()` from `utils.py` to handle both raw JSON strings and pre-decoded dicts

## OpenConfig Namespaces

These parsers rely on OpenConfig YANG models. Key namespaces defined in `constants.py`:

| Constant | Namespace |
|----------|-----------|
| `OPENCONFIG_INTERFACES` | `openconfig-interfaces:interfaces` |
| `OPENCONFIG_NETWORK_INSTANCES` | `openconfig-network-instance:network-instances` |
| `ARCOS_ISIS_AUGMENTS` | `arcos-openconfig-isis-augments` |
| `ARCOS_SRV6` | `arcos-srv6:srv6` |

ArcOS-specific augments are also handled, typically prefixed with `arcos-`.

## Testing

Each parser has a corresponding test file in the `tests/` directory. Tests use sample JSON data stored in `tests/test_samples/` to verify parser output.

To run unit tests from the root of the `genieparser` project:

```bash
python -m pytest src/genie/libs/parser/arcos/tests/ -v
```

Run a specific test file:

```bash
python -m pytest src/genie/libs/parser/arcos/tests/test_arcos_isis.py -v
```
