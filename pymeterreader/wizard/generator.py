import yaml
import typing as tp
from pymeterreader.device_lib.common import Device


def generate_yaml(devices: tp.List[Device], url: str):
    config = {'middleware': {'type': 'volkszahler',
                             'middleware_url': url,
                             'interpolate': False},
              'devices': {}}

    for device in devices:
        if any('uuid' in channel for channel in device.channels.values()):
            config[device.identifier] = {'id': device.identifier}
            if device.tty:
                config[device.identifier]['tty'] = device.tty
            channels = {}
            for channel, content in device.channels.items():
                if 'uuid' in content:
                    channels[channel] = {'uuid': content['uuid'],
                                         'interval': content['interval']}
            config[device.identifier]['channels'] = channels
    return yaml.dump(config, Dumper=yaml.SafeDumper)
