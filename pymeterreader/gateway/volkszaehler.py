"""
Uploader for the Volkszaehler middleware
"""
import json
import typing as tp
from contextlib import suppress
from logging import error, debug, info
from time import time

import requests

from pymeterreader.core.channel_description import ChannelDescription
from pymeterreader.core.channel_upload_info import ChannelUploadInfo
from pymeterreader.gateway.basegateway import BaseGateway


class VolkszaehlerGateway(BaseGateway):
    """
    This class implements an uploader to a Volkszahler midlleware server.
    """
    DATA_PATH = "data"
    SUFFIX = ".json"

    def __init__(self, middleware_url: str, interpolate: bool = True, **kwargs) -> None:
        """
         Initialize Volkszaehler Gateway
         :param middleware_url: address of middleware
         :param interpolate: If true, hourly values will be interpolated and ushed
         """
        super().__init__(**kwargs)
        self.url = middleware_url
        self.interpolate = interpolate

    def post(self, channel: ChannelUploadInfo, value: tp.Union[int, float], sample_timestamp: tp.Union[int, float],
             poll_timestamp: tp.Union[int, float]) -> bool:
        # Push hourly interpolated values to enable line plotting in volkszaehler middleware
        if self.interpolate:
            hours = round((poll_timestamp - channel.last_upload) / 3600)
            diff = value - channel.last_value
            if hours <= 24:
                for hour in range(1, hours):
                    btw_time = channel.last_upload + hour * 3600
                    btw_value = channel.last_value + diff * (hour / hours)
                    self.__post_value(channel.uuid, btw_value, btw_time)
        return self.__post_value(channel.uuid, value, sample_timestamp)

    def __post_value(self, uuid: str, value: tp.Union[int, float], timestamp: tp.Union[int, float]) -> bool:
        rest_url = self.urljoin(self.url, self.DATA_PATH, uuid, self.SUFFIX)
        timestamp = self.timestamp_to_int(timestamp)
        try:
            data = {"ts": timestamp, "value": value}
            response = requests.post(rest_url, data=data)
            response.raise_for_status()
            info(f'POST {data} to {rest_url}: {response}')
            return True
        except requests.exceptions.RequestException as req_err:
            error(f'POST {data} to {rest_url}: {req_err}')
        return False

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

    def get_channels(self) -> tp.List[ChannelDescription]:
        """
        Retrieve a dict of channels from the middleware
        """
        channel_url = self.urljoin(self.url, 'channel.json')
        extracted_channels: tp.List[ChannelDescription] = []
        try:
            response = requests.get(channel_url)
            response.raise_for_status()
            channels_list: tp.List[dict] = json.loads(response.content)['channels']
            debug(f'GET from {channel_url}: {response}')
            # Transform untyped response into ChannelDescriptions
            for channel_dict in channels_list:
                # Mandatory arguments
                channel_uuid = channel_dict.get("uuid", None)
                channel_title = channel_dict.get("title", None)
                # Optional arguments
                channel_type = channel_dict.get("type", "")
                channel_description = channel_dict.get("description", "")
                if channel_uuid is not None and channel_title is not None:
                    extracted_channels.append(
                        ChannelDescription(channel_uuid, channel_title, channel_type, channel_description))
                else:
                    error(f"Could not parse Channel with uuid:{channel_uuid},"
                          f"title:{channel_title},"
                          f"type:{channel_type},"
                          f"description:{channel_description}")
        except requests.exceptions.HTTPError as http_err:
            error(f'Invalid HTTP Response for GET from {channel_url}: {http_err}')
        except requests.exceptions.ConnectionError as conn_err:
            error(f'Could not connect for GET: {conn_err}')
        except requests.exceptions.RequestException as req_err:
            error(f'Unexpected requests error: {req_err}')
        return extracted_channels

    @staticmethod
    def urljoin(*args: str) -> str:
        url = '/'.join([arg.strip('/') for arg in args])
        if not url.startswith('http'):
            url = f'http://{url}'
        url = url.replace('/.', '.')
        return url
