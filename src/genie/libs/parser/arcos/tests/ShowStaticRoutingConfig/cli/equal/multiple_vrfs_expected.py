expected_output = {
    "network-instances": {
        "default": {
            "protocols": {
                "static-routes": {
                    "identifier": "openconfig-policy-types:STATIC",
                    "name": "static-routes",
                    "static-routes": {
                        "10.0.0.0/8": {
                            "prefix": "10.0.0.0/8",
                            "next-hops": {
                                "1": {"index": "1", "next-hop": "192.168.1.1"},
                            },
                        },
                        "192.168.100.1/32": {
                            "prefix": "192.168.100.1/32",
                            "description": "Static route with BFD",
                            "bfd": {"profile": "GLOBAL"},
                            "next-hops": {
                                "next-hop1": {
                                    "index": "next-hop1",
                                    "interface": "swp3",
                                    "bfd": {"destination-address": "10.0.0.2"},
                                },
                            },
                        },
                        "192.168.200.0/24": {
                            "prefix": "192.168.200.0/24",
                            "description": "ECMP static route",
                            "preference": 10,
                            "next-hops": {
                                "nh1": {"index": "nh1", "next-hop": "10.9.201.1", "interface": "swp1"},
                                "nh2": {"index": "nh2", "next-hop": "10.9.202.1", "interface": "swp2"},
                                "nh3": {"index": "nh3", "next-hop": "10.9.203.1", "interface": "swp3"},
                            },
                        },
                        "2001:db8:100::/64": {
                            "prefix": "2001:db8:100::/64",
                            "description": "IPv6 static route",
                            "next-hops": {
                                "1": {"index": "1", "next-hop": "2001:db8:1::1", "interface": "swp1"},
                            },
                        },
                    },
                }
            }
        }
    }
}
