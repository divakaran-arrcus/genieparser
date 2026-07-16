expected_output = {
    'policies': {
        '2.2.2.2 100': {
            'endpoint': '2.2.2.2',
            'color': 100,
            'name': 'test-policy-to-rtr2',
            'description': 'Test SR-Policy towards rtr2',
            'enabled': True,
            'priority': 128,
            'candidate-paths': {
                '10': {
                    'discriminator': 10,
                    'preference': 200,
                    'originator-as': 0,
                    'originator-address': '0.0.0.0',
                    'type': 'EXPLICIT_SEGMENT_LIST',
                    'explicit-segment-lists': ['sl1'],
                },
            },
        },
    },
}
