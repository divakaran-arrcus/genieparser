expected_output = {
    "acl-sets": {
        "pyats-test-v4 ACL_IPV4": {
            "name": "pyats-test-v4",
            "type": "ACL_IPV4",
            "acl-entries": {
                "10": {
                    "sequence-id": "10",
                    "priority": 10,
                    "matched-ingress-packets": "0",
                    "matched-egress-packets": "0",
                    "matched-ingress-octets": "0",
                    "matched-egress-octets": "0",
                    "ipv4-source-address": "10.0.0.0/8",
                    "forwarding-action": "DROP",
                    "log-action": "LOG_NONE",
                },
                "1000": {
                    "sequence-id": "1000",
                    "priority": 1000,
                    "matched-ingress-packets": "0",
                    "matched-egress-packets": "0",
                    "matched-ingress-octets": "0",
                    "matched-egress-octets": "0",
                    "ipv4-source-address": "0.0.0.0/0",
                    "forwarding-action": "ACCEPT",
                    "log-action": "LOG_NONE",
                },
            },
        }
    }
}
