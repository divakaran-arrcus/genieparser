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

All ISIS parsers accept optional filtering parameters (default `*` for all). Parameters in `{}` are optional with defaults.

| Parser Class | CLI Command | Parameters |
|--------------|-------------|------------|
| `ShowIsisAdjacency` | `show network-instance {network_instance} protocol ISIS {protocol_instance} interface {interface} level {level} adjacency [<adj_router>]` | `network_instance`, `protocol_instance`, `interface`, `level`, `adj_router` |
| `ShowIsisLsp` | `show network-instance {network_instance} protocol ISIS {protocol_instance} level {level} link-state-database lsp [<lsp_id>]` | `network_instance`, `protocol_instance`, `level`, `lsp_id` |
| `ShowIsisInterface` | `show network-instance {network_instance} protocol ISIS {protocol_instance} interface [<interface>]` | `network_instance`, `protocol_instance`, `interface` |
| `ShowIsisConfig` | `show running-config network-instance {network_instance} protocol ISIS {protocol_instance}` | `network_instance`, `protocol_instance` |
| `ShowIsisRoute` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST route [<prefix>]` | `network_instance`, `protocol_instance`, `afi`, `prefix` |
| `ShowIsisRedistributeRoute` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST redistribute-route [<prefix>]` | `network_instance`, `protocol_instance`, `afi`, `prefix` |
| `ShowIsisGlobal` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global state` | `network_instance`, `protocol_instance` |
| `ShowIsisFastReroute` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST fast-reroute [<prefix>]` | `network_instance`, `protocol_instance`, `afi`, `prefix` |
| `ShowIsisFlexAlgoFastReroute` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} fast-reroute [<prefix>]` | `network_instance`, `protocol_instance`, `afi`, `algo`, `prefix` |
| `ShowIsisFlexAlgoRoute` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global af {afi} UNICAST flexible-algorithm {algo} route [<prefix>]` | `network_instance`, `protocol_instance`, `afi`, `algo`, `prefix` |
| `ShowIsisMplsLabelDb` | `show network-instance {network_instance} protocol ISIS {protocol_instance} global mpls` | `network_instance`, `protocol_instance` |

### MPLS Parsers

| Parser Class | CLI Command | Parameters |
|--------------|-------------|------------|
| `ShowMplsReservedLabelBlockConfig` | `show running-config network-instance {network_instance} mpls global reserved-label-block [<local_id>]` | `network_instance`, `local_id` |
| `ShowMplsReservedLabelBlock` | `show network-instance {network_instance} mpls global reserved-label-block [<local_id>]` | `network_instance`, `local_id` |

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
| `ShowRoutingPolicyConfig` | `show running-config routing-policy` | `show_routing_policy` |

### Static Routing Parsers

| Parser Class | CLI Command | Parameters |
|--------------|-------------|------------|
| `ShowStaticRoutingConfig` | `show running-config network-instance {network_instance} protocol STATIC {protocol_instance}` | `network_instance`, `protocol_instance` |

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

# Get all adjacencies (all instances, interfaces, levels)
output = parser.cli()

# Filter by network instance and protocol instance
output = parser.cli(network_instance="default", protocol_instance="default")

# Filter by interface and level
output = parser.cli(interface="swp1", level="2")

# Get specific neighbor
output = parser.cli(adj_router="rtr2")
```

### ISIS LSP Database

```python
from genie.libs.parser.arcos.show_isis import ShowIsisLsp

parser = ShowIsisLsp(device=device)

# Get all LSPs
output = parser.cli()

# Filter by instance and level
output = parser.cli(network_instance="default", protocol_instance="default", level="2")

# Get specific LSP
output = parser.cli(lsp_id="0000.0000.0001.00-00")
```

### ISIS Routes with AFI Filter

```python
from genie.libs.parser.arcos.show_isis import ShowIsisRoute, ShowIsisFastReroute

parser = ShowIsisRoute(device=device)

# Get all routes
output = parser.cli()

# Filter by AFI (IPV4 or IPV6)
output = parser.cli(afi="IPV4")

# Filter by instance and AFI
output = parser.cli(network_instance="default", protocol_instance="default", afi="IPV6")

# Get specific prefix
output = parser.cli(prefix="10.0.0.0/24")
```

### ISIS FlexAlgo

```python
from genie.libs.parser.arcos.show_isis import ShowIsisFlexAlgoRoute, ShowIsisFlexAlgoFastReroute

parser = ShowIsisFlexAlgoRoute(device=device)

# Get all FlexAlgo routes
output = parser.cli()

# Filter by algorithm ID
output = parser.cli(algo="128")

# Filter by instance, AFI, and algorithm
output = parser.cli(network_instance="default", protocol_instance="default", afi="IPV6", algo="129")
```

### MPLS Reserved Label Blocks

```python
from genie.libs.parser.arcos.show_mpls import (
    ShowMplsReservedLabelBlockConfig,
    ShowMplsReservedLabelBlock,
)

# Get running-config for all label blocks
parser = ShowMplsReservedLabelBlockConfig(device=device)
output = parser.cli()

# Filter by network instance
output = parser.cli(network_instance="default")

# Get specific label block config
output = parser.cli(network_instance="default", local_id="rb1")

# Get operational state for label blocks
parser = ShowMplsReservedLabelBlock(device=device)
output = parser.cli()

# Filter by network instance and block ID
output = parser.cli(network_instance="default", local_id="rb2")
```

### ISIS MPLS Label Database

```python
from genie.libs.parser.arcos.show_isis import ShowIsisMplsLabelDb

parser = ShowIsisMplsLabelDb(device=device)

# Get all ISIS MPLS label database
output = parser.cli()

# Filter by network instance and protocol instance
output = parser.cli(network_instance="default", protocol_instance="default")
```

### Routing Policy

```python
from genie.libs.parser.arcos.show_routing_policy import (
    ShowRoutingPolicyDefinedSets,
    ShowRoutingPolicyPolicyDefinition,
    ShowRoutingPolicyConfig,
)

# Parse defined-sets (prefix-sets, string-sets, tag-sets, next-hop-sets)
parser = ShowRoutingPolicyDefinedSets(device=device)
output = parser.cli()

# Parse policy definitions with statements, conditions, and actions
parser = ShowRoutingPolicyPolicyDefinition(device=device)
output = parser.cli()

# Parse full running-config (combines defined-sets and policy-definitions)
parser = ShowRoutingPolicyConfig(device=device)
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

### Static Routing Configuration

```python
from genie.libs.parser.arcos.show_static_routing import ShowStaticRoutingConfig

# Parse all static routing configurations (all network instances and protocol instances)
parser = ShowStaticRoutingConfig(device=device)
output = parser.cli()

# Parse specific network instance
output = parser.cli(network_instance="default", protocol_instance="static-routes")

# Parse specific VRF
output = parser.cli(network_instance="vrfA", protocol_instance="static-routes")

# Parse all static routes in all network instances using wildcard
output = parser.cli(network_instance="*", protocol_instance="*")
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
├── show_mpls.py          # MPLS parsers
├── show_routing_policy.py # Routing policy parsers
├── show_segment_routing.py # Segment Routing parsers
├── show_srv6.py          # SRv6 parsers
├── show_static_routing.py # Static routing parsers
├── show_version.py       # System version parser
└── tests/                # Unit tests
    ├── test_arcos_interface.py
    ├── test_arcos_isis.py
    ├── test_arcos_mpls.py
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
