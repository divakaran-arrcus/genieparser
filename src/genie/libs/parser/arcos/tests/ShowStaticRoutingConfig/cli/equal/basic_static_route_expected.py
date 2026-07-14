expected_output = {
    "network-instances": {
        "default": {
            "protocols": {
                "static-routes": {
                    "identifier": "openconfig-policy-types:STATIC",
                    "name": "static-routes",
                    "static-routes": {
                        "192.168.100.0/24": {
                            "prefix": "192.168.100.0/24",
                            "description": "Basic static route test",
                            "next-hops": {
                                "1": {
                                    "index": "1",
                                    "next-hop": "10.9.201.1",
                                    "interface": "swp1",
                                }
                            },
                        }
                    },
                }
            }
        }
    }
}
