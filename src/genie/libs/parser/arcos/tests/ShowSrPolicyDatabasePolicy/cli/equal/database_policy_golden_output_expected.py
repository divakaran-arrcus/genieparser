expected_output = {
    'policies': {
        '2.2.2.2 100': {
            'endpoint': '2.2.2.2',
            'color': 100,
            'oper-state': 'DOWN',
            'transition-count': 0,
            'down-time': '2026-04-01T10:21:07+00:00',
            'candidate-paths': {
                'LOCAL:0:0.0.0.0:10': {
                    'protocol-origin': 'LOCAL',
                    'originator': '0:0.0.0.0',
                    'discriminator': 10,
                    'preference': 200,
                    'type': 'EXPLICIT_SEGMENT_LIST',
                    'best-candidate-path': False,
                    'valid': False,
                    'segment-lists': [
                        {'index': 2, 'name': 'sl1', 'valid': False},
                    ],
                },
            },
        },
    },
}
