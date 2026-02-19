expected_output = {
    "network_instances": {
        "default": {
            "protocols": {
                "static-routes": {
                    "identifier": "openconfig-policy-types:STATIC",
                    "name": "static-routes",
                    "static_routes": {
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
                        "192.168.250.1/32": {
                            "prefix": "192.168.250.1/32",
                            "description": "Route with MPLS labels",
                            "local_label_index": 100,
                            "next_hops": {
                                "NH": {
                                    "index": "NH",
                                    "next_hop": "10.9.250.1",
                                    "interface": "swp3",
                                    "remote_label_stack": [1000, 2000, 3000],
                                },
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
