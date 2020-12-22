"""
Uploader for the Volkszaehler middleware
"""
import typing as tp
import json
from time import time
from contextlib import suppress
from logging import error, debug, info
import requests
from pymeterreader.gateway.basegateway import BaseGateway


class VolkszaehlerGateway(BaseGateway):
    """
    This class implements an uploader to a Volkszahler midlleware server.
    """
    DATA_PATH = "data"
    SUFFIX = ".json"

    def __init__(self, url: str, interpolate: bool = True):
        """
         Initialize Volkszaehler Gateway
         :param url: address of middleware
         :param interpolate: If true, hourly values will be interpolated and ushed
         """
        super().__init__()
        self.url = url
        self.interpolate = interpolate

    def post(self, uuid: str, value: tp.Union[int, float], timestamp: tp.Union[int, float]) -> bool:
        rest_url = self.urljoin(self.url, self.DATA_PATH, uuid, self.SUFFIX)
        timestamp = self.timestamp_to_int(timestamp)
        try:
            data = {"ts": timestamp, "value": value}
            response = requests.post(rest_url, data=data)
            if response.status_code != 200:
                error(f'POST {data} to {rest_url}: {response}')
            else:
                info(f'POST {data} to {rest_url}: {response}')
        except OSError as err:
            error(err)
            return False
        return True

    def get(self, uuid: str) -> tp.Optional[tp.Tuple[int, tp.Union[int, float]]]:
        rest_url = self.urljoin(self.url, self.DATA_PATH, uuid, self.SUFFIX)
        try:
            params = {"options": 'raw',
                      "to": int(time() * 1000)}
            response = requests.get(rest_url, params=params)
            if response.status_code != 200:
                error(f'GET {params} from {rest_url}: {response}')
            else:
                debug(f'GET {params} from {rest_url}: {response}')
        except OSError as err:
            error(f'Error during GET: {err}')
            return None
        parsed = json.loads(response.content.decode('utf-8'))
        if 'data' in parsed and parsed.get('data').get('rows') > 0:
            with suppress(IndexError):
                tuples = parsed.get('data').get('tuples')
                tuples.sort(key=lambda x: x[0])
                latest_entry = tuples[-1]
                time_stamp = int(latest_entry[0]) // 1000
                value = latest_entry[1]
                if not isinstance(value, (int, float)):
                    error(f"{value} is not of type int or float!")
                    return None
                info(f"GET {uuid} returned timestamp={time_stamp * 1000} value={value}")
                return time_stamp, value
        return None

    def get_channels(self) -> dict:
        """
        Retrieve a dict of channels from the middleware
        """
        rest_url = self.urljoin(self.url, 'channel.json')
        try:
            response = requests.get(rest_url)
            if response.status_code != 200:
                error(f'GET from {rest_url}: {response}')
            else:
                debug(f'GET from {rest_url}: {response}')
                return json.loads(response.content)['channels']
        except OSError as err:
            error(f'Error during GET: {err}')
        return {}

    @staticmethod
    def urljoin(*args):
        url = '/'.join([arg.strip('/') for arg in args])
        if not url.startswith('http'):
            url = f'http://{url}'
        url = url.replace('/.', '.')
        return url