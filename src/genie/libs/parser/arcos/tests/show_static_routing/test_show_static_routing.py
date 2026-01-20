"""Unit tests for ArcOS Static Routing parsers."""

import os
import unittest
from unittest.mock import Mock

from genie.libs.parser.arcos.show_static_routing import ShowStaticRoutingConfig


class TestShowStaticRoutingConfig(unittest.TestCase):
    """Test cases for ShowStaticRoutingConfig parser."""

    def setUp(self):
        """Set up test fixtures."""
        self.device = Mock()
        self.parser = ShowStaticRoutingConfig(device=self.device)
        self.maxDiff = None
        self.test_dir = os.path.dirname(os.path.abspath(__file__))

    def load_golden(self, filename):
        """Load golden output from file."""
        filepath = os.path.join(self.test_dir, "cli", "equal", filename)
        with open(filepath, "r") as f:
            content = f.read()
            # Strip the command line if present
            if content.startswith("root@"):
                lines = content.split("\n", 1)
                if len(lines) > 1:
                    return lines[1]
            return content

    def load_expected(self, filename):
        """Load expected output from file."""
        filepath = os.path.join(self.test_dir, "cli", "equal", filename)
        expected_module = {}
        with open(filepath, "r") as f:
            exec(f.read(), expected_module)
        return expected_module["expected_output"]

    def test_basic_static_route(self):
        """Test parsing basic static route with single next-hop."""
        output = self.load_golden("basic_static_route_golden.txt")
        expected = self.load_expected("basic_static_route_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_ecmp_static_route(self):
        """Test parsing static route with multiple next-hops (ECMP)."""
        output = self.load_golden("ecmp_static_route_golden.txt")
        expected = self.load_expected("ecmp_static_route_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_drop_nexthop(self):
        """Test parsing static route with DROP next-hop."""
        output = self.load_golden("drop_nexthop_golden.txt")
        expected = self.load_expected("drop_nexthop_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_ipv6_static_route(self):
        """Test parsing IPv6 static route."""
        output = self.load_golden("ipv6_static_route_golden.txt")
        expected = self.load_expected("ipv6_static_route_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_mpls_labels(self):
        """Test parsing static route with MPLS labels."""
        output = self.load_golden("mpls_labels_golden.txt")
        expected = self.load_expected("mpls_labels_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_bfd_configuration(self):
        """Test parsing static route with BFD configuration."""
        output = self.load_golden("bfd_static_route_golden.txt")
        expected = self.load_expected("bfd_static_route_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_vrf_leaking(self):
        """Test parsing static route with next-network-instance."""
        output = self.load_golden("vrf_leaking_golden.txt")
        expected = self.load_expected("vrf_leaking_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_linklocal_ipv6(self):
        """Test parsing link-local IPv6 next-hop with subinterface."""
        output = self.load_golden("linklocal_ipv6_golden.txt")
        expected = self.load_expected("linklocal_ipv6_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_multiple_vrfs(self):
        """Test parsing static routes in multiple VRFs."""
        output = self.load_golden("multiple_vrfs_golden.txt")
        expected = self.load_expected("multiple_vrfs_expected.py")

        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )

        self.assertEqual(result, expected)

    def test_empty_output(self):
        """Test parser with empty JSON output."""
        output = '{"data": {}}'
        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )
        
        self.assertEqual(result, {"network_instances": {}})

    def test_invalid_json(self):
        """Test parser with invalid JSON output."""
        output = "invalid json"
        result = self.parser.cli(
            network_instance="default",
            protocol_instance="static-routes",
            output=output
        )
        
        # Should return empty dict on JSON parse error
        self.assertEqual(result, {"network_instances": {}})


if __name__ == "__main__":
    unittest.main()
