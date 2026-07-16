expected_output = {
    'vrrp-groups': {
        'swp1:0:ipv4:10.12.1.1:10': {
            'interface': 'swp1',
            'sub-id': 0,
            'af': 'ipv4',
            'address': '10.12.1.1',
            'virtual-router-id': 10,
            'virtual-address': ['10.12.1.100'],
            'priority': 200,
            'current-priority': 200,
            'preempt': True,
            'accept-mode': True,
            'advertisement-interval': 300,
            'vrrp-version': 'VRRP_V3',
            'virtual-router-mode': 'MASTER',
            'virtual-mac-address': '00:00:5e:00:01:0a',
            'advertisement-sent': '12',
            'advertisement-received': '0',
            'advertisement-dropped': '0',
        }
    }
}
