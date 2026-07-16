expected_output = {
    "network-instances": {
        "default": {
            "srms": {
                "mappings": {
                    "map-1": {
                        "local-id": "map-1",
                        "ipv4-prefixes": [
                            {
                                "prefix": "10.0.0.0/24",
                                "sid": 16000,
                                "range": 100
                            }
                        ],
                        "ipv6-prefixes": [
                            {
                                "prefix": "2001:db8::/32",
                                "sid": 17000,
                                "range": 50
                            }
                        ]
                    }
                }
            }
        }
    }
}
