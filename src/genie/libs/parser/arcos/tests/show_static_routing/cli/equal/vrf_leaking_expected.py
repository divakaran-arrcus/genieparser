expected_output = {
    "network_instances": {
        "default": {
            "protocols": {
                "static-routes": {
                    "identifier": "openconfig-policy-types:STATIC",
                    "name": "static-routes",
                    "static_routes": {
                        "11.1.1.1/32": {
                            "prefix": "11.1.1.1/32",
                            "next_hops": {
                                "1": {"index": "1", "next_network_instance": "vrfA"},
                            },
                        },
                        "100.0.0.1/32": {
                            "prefix": "100.0.0.1/32",
                            "next_hops": {
                                "1": {"index": "1", "next_hop": "11.1.1.1"},
                            },
                        },
                        "192.168.100.1/32": {
                            "prefix": "192.168.100.1/32",
                            "description": "Static route with BFD",
                            "bfd": {"profile": "GLOBAL"},
                            "next_hops": {
                                "next-hop1": {
                                    "index": "next-hop1",
                                    "interface": "swp3",
                                    "bfd": {"destination_address": "10.0.0.2"},
                                },
                            },
                        },
                        "192.168.200.0/24": {
                            "prefix": "192.168.200.0/24",
                            "description": "ECMP static route",
                            "preference": 10,
                            "next_hops": {
                                "nh1": {"index": "nh1", "next_hop": "10.9.201.1", "interface": "swp1"},
                                "nh2": {"index": "nh2", "next_hop": "10.9.202.1", "interface": "swp2"},
                                "nh3": {"index": "nh3", "next_hop": "10.9.203.1", "interface": "swp3"},
                            },
                        },
                        "2001:db8:100::/64": {
                            "prefix": "2001:db8:100::/64",
                            "description": "IPv6 static route",
                            "next_hops": {
                                "1": {"index": "1", "next_hop": "2001:db8:1::1", "interface": "swp1"},
                            },
                        },
                    },
                }
            }
        }
    }
}
