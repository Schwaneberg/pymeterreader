"""
Uploader for the Volkszaehler middleware
"""
from time import time
import typing as tp
import requests
import json
from contextlib import suppress
from abc import ABC, abstractmethod
from logging import error, debug, info


class BaseGateway(ABC):
    def __init__(self, url, interpolate):
        """
        Gateway base clas
        :param url: address of middleware
        :param interpolate: If true, hourly values will be interpolated and ushed
        """
        self.url = url
        self.interpolate = interpolate

    @abstractmethod
    def post(self, uuid: str, value: tp.Union[int, float], timestamp: int) -> bool:
        raise NotImplementedError("Abstract Base for POST")

    @abstractmethod
    def get(self, uuid: str) -> tp.Optional[tp.Tuple[int, tp.Union[int, float]]]:
        raise NotImplementedError("Abstract Base for GET")


class VolkszaehlerGateway(BaseGateway):
    """
    This class implements an uploader
    to a Volkszahler midlleware server.
    """
    DATA_PATH = "data"
    SUFFIX = ".json"

    def __init__(self, url, interpolate=True):
        super().__init__(url, interpolate)

    def post(self, uuid: str, value: tp.Union[int, float], timestamp: tp.Union[int, float]) -> bool:
        rest_url = self.urljoin(self.url, self.DATA_PATH, uuid, self.SUFFIX)
        if isinstance(timestamp, float):
            timestamp = int(timestamp * 1000)
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

    @staticmethod
    def urljoin(*args):
        url = '/'.join([arg.strip('/') for arg in args])
        if not url.startswith('http'):
            url = f'http://{url}'
        url = url.replace('/.', '.')
        return url
