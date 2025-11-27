# Test Sample Files

This directory contains sample JSON outputs from Arrcus routers used for parser validation tests.

## Files

### isis_interface.json
Sample output for `show network-instance * protocol ISIS * interface | display json | nomore`
- Tests: `ShowIsisInterface` parser
- Contains: Interface state, network types (POINT_TO_POINT, LOOPBACK), adjacency data

### isis_adjacency.json
Sample output for `show network-instance * protocol ISIS * interface * level * adjacency | display json | nomore`
- Tests: `ShowIsisAdjacency` parser
- Contains: ISIS neighbor adjacencies, states, hold times

### isis_lsp.json
Sample output for `show network-instance * protocol ISIS * level * link-state-database | display json | nomore`
- Tests: `ShowIsisLsp` parser
- Contains: Link State PDUs, sequence numbers, checksums, TLVs

### version.json
Sample output for `show version | display json | nomore`
- Tests: `ShowVersion` parser
- Contains: Software version, platform info, uptime

### isis_config.json
Sample output for `show running-config network-instance default protocol ISIS default | display json | nomore`
- Tests: `ShowIsisConfig` parser
- Contains: ISIS global config (NET, level-capability), AFI-SAFI, interface configurations

### isis_routes.json
Sample output for `show network-instance * protocol ISIS * global af * UNICAST route | display json | nomore`
- Tests: `ShowIsisRoutes` parser
- Contains: ISIS routing table with IPv4/IPv6 prefixes, metrics, flags, next-hops

## Usage

The test script (`test_parsers.py`) loads these JSON files and validates that the parsers correctly extract and structure the data.

```python
# Example usage in test
sample_json = load_sample('isis_routes.json')
parser = ShowIsisRoutes(device=MockDevice())
result = parser.cli(output=sample_json)
```

## Adding New Samples

To add a new sample:
1. Capture JSON output from Arrcus router using `display json | nomore`
2. Save to this directory with descriptive filename
3. Add corresponding test function in `test_parsers.py`
4. Validate the parser extracts expected fields
