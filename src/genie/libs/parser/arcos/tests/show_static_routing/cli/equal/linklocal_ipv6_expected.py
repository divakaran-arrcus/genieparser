expected_output = {
    "network_instances": {
        "default": {
            "protocols": {
                "static-routes": {
                    "identifier": "openconfig-policy-types:STATIC",
                    "name": "static-routes",
                    "static_routes": {
                        "192:168:100::/64": {
                            "prefix": "192:168:100::/64",
                            "next_hops": {
                                "next-hop1": {
                                    "index": "next-hop1",
                                    "next_hop": "fe80::5054:ff:fef7:8d0e",
                                    "interface": "swp3",
                                    "subinterface": 0,
                                },
                            },
                        }
                    },
                }
            }
        }
    }
}
