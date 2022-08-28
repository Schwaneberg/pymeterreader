"""
Uploader for the Volkszaehler middleware
"""
import json
import logging
import typing as tp
from contextlib import suppress
from datetime import timedelta, datetime, timezone
from time import time

import requests
from prometheus_client import Info, Counter

from pymeterreader.core.channel_description import ChannelDescription
from pymeterreader.core.channel_upload_info import ChannelUploadInfo
from pymeterreader.gateway.basegateway import BaseGateway
from pymeterreader.metrics.prefix import METRICS_PREFIX

logger = logging.getLogger(__name__)


class VolkszaehlerGateway(BaseGateway):
    """
    This class implements an uploader to a Volkszahler midlleware server.
    """
    DATA_PATH = "data"
    SUFFIX = ".json"
    REQUEST_TIMEOUT = 20
    VOLKSZAEHLER_INFO = Info(METRICS_PREFIX + "volkszahler_gateway", "Information about the Volkszaehler Gateway")
    POST_COUNTER = Counter(METRICS_PREFIX + "volkszahler_gateway_uploads", "Number of successful POST requests")
    POST_FAILURE_COUNTER = Counter(METRICS_PREFIX + "volkszahler_gateway_failed_uploads",
                                   "Number of failed POST requests")

    def __init__(self, middleware_url: str, interpolate: bool = True, **kwargs) -> None:
        """
         Initialize Volkszaehler Gateway
         :param middleware_url: address of middleware
         :param interpolate: If true, hourly values will be interpolated and ushed
         """
        super().__init__(**kwargs)
        self.url = middleware_url
        self.interpolate = interpolate
        # Metrics
        self.VOLKSZAEHLER_INFO.info({"url": middleware_url, "interpolation": str(interpolate)})

    def post(self, channel: ChannelUploadInfo, value: tp.Union[int, float], sample_timestamp: datetime,
             poll_timestamp: datetime) -> bool:
        # Push hourly interpolated values to enable line plotting in volkszaehler middleware
        if self.interpolate:
            time_between_uploads: timedelta = poll_timestamp - channel.last_upload
            hours = time_between_uploads.seconds // 3600
            diff = value - channel.last_value
            if hours <= 24:
                for hour in range(1, hours):
                    btw_time = channel.last_upload + timedelta(0, hour * 3600)
                    btw_value = channel.last_value + diff * (hour / hours)
                    self.__post_value(channel.uuid, btw_value, btw_time)
        return self.__post_value(channel.uuid, value, sample_timestamp)

    def __post_value(self, uuid: str, value: tp.Union[int, float], timestamp: datetime) -> bool:
        self.POST_COUNTER.inc()
        rest_url = VolkszaehlerGateway.urljoin(self.url, self.DATA_PATH, uuid, self.SUFFIX)
        try:
            timestamp_utc_milliseconds = int(timestamp.timestamp() * 1000)
            data = {"ts": timestamp_utc_milliseconds, "value": value}
            response = requests.post(rest_url, data=data, timeout=VolkszaehlerGateway.REQUEST_TIMEOUT)
            response.raise_for_status()
            logger.info(f'POST {data} to {rest_url}: {response}')
            return True
        except requests.exceptions.RequestException as req_err:
            logger.error(f'POST {data} to {rest_url}: {req_err}')
        self.POST_FAILURE_COUNTER.inc()
        return False

    def get_upload_info(self, channel_info: ChannelUploadInfo) -> tp.Optional[ChannelUploadInfo]:
        rest_url = VolkszaehlerGateway.urljoin(self.url, self.DATA_PATH, channel_info.uuid, self.SUFFIX)
        params = {"options": 'raw', "to": int(time() * 1000)}
        try:
            response = requests.get(rest_url, params=params, timeout=VolkszaehlerGateway.REQUEST_TIMEOUT)
            response.raise_for_status()
            parsed = json.loads(response.content.decode('utf-8'))
            if 'data' in parsed and parsed.get('data').get('rows', 0) > 0:
                with suppress(IndexError):
                    tuples = parsed.get('data').get('tuples')
                    tuples.sort(key=lambda x: x[0])
                    latest_entry = tuples[-1]
                    timestamp = datetime.fromtimestamp((latest_entry[0] / 1000), timezone.utc)
                    value = latest_entry[1]
                    if not isinstance(value, (int, float)):
                        logger.error(f"{value} is not of type int or float!")
                        return None
                    logger.info(f"GET {channel_info.uuid} returned timestamp={timestamp} value={value}")
                    return ChannelUploadInfo(channel_info.uuid, channel_info.interval, channel_info.factor, timestamp,
                                             value)
        except requests.exceptions.HTTPError as http_err:
            logger.error(f'Invalid HTTP Response for GET from {rest_url}: {http_err}')
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f'Could not connect for GET from {rest_url}: {conn_err}')
        except requests.exceptions.RequestException as req_err:
            logger.error(f'Unexpected requests error: {req_err}')
        return None

    def get_channels(self) -> tp.List[ChannelDescription]:
        """
        Retrieve a dict of channels from the middleware
        """
        channel_url = VolkszaehlerGateway.urljoin(self.url, 'channel.json')
        extracted_channels: tp.List[ChannelDescription] = []
        try:
            response = requests.get(channel_url, timeout=VolkszaehlerGateway.REQUEST_TIMEOUT)
            response.raise_for_status()
            channels_list: tp.List[dict] = json.loads(response.content)['channels']
            logger.debug(f'GET from {channel_url}: {response}')
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
                    logger.error(f"Could not parse Channel with uuid:{channel_uuid},"
                                 f"title:{channel_title},"
                                 f"type:{channel_type},"
                                 f"description:{channel_description}")
        except requests.exceptions.HTTPError as http_err:
            logger.error(f'Invalid HTTP Response for GET from {channel_url}: {http_err}')
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f'Could not connect for GET: {conn_err}')
        except requests.exceptions.RequestException as req_err:
            logger.error(f'Unexpected requests error: {req_err}')
        return extracted_channels

    @staticmethod
    def urljoin(*args: str) -> str:
        url = '/'.join([arg.strip('/') for arg in args])
        if not url.startswith('http'):
            url = f'http://{url}'
        url = url.replace('/.', '.')
        return url
