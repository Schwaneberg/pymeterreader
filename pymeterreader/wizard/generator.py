import yaml


SERVICE_TEMPLATE = '[Unit]\n' \
                   'Description=pymeterreader\n' \
                   'After=network.target\n' \
                   'StartLimitIntervalSec=0\n' \
                   '\n' \
                   '[Service]\n' \
                   'Type=simple\n' \
                   'Restart=always\n' \
                   'RestartSec=5\n' \
                   'User=root\n' \
                   'ExecStart={}\n' \
                   '\n' \
                   '[Install]\n' \
                   'WantedBy=multi-user.target\n'


def generate_yaml(devices: dict, url: str) -> str:
    config = {'middleware': {'type': 'volkszaehler',
                             'middleware_url': url,
                             'interpolate': False},
              'devices': devices}
    return yaml.dump(config, Dumper=yaml.SafeDumper)
