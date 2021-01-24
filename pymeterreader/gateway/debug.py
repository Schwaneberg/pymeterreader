"""
Uploader that prints to the Console instead of uploading
"""
import typing as tp
from logging import debug

from pymeterreader.core.channel_description import ChannelDescription
from pymeterreader.core.channel_upload_info import ChannelUploadInfo
from pymeterreader.gateway.basegateway import BaseGateway


class DebugGateway(BaseGateway):
    """
    This class is used for debugging uploads to a middleware
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.post_timestamps = {}

    def post(self, channel: ChannelUploadInfo, value: tp.Union[int, float], sample_timestamp: tp.Union[int, float],
             poll_timestamp: tp.Union[int, float]) -> bool:
        timestamp = self.timestamp_to_int(sample_timestamp)
        self.post_timestamps[channel.uuid] = timestamp, value
        debug("Sent Channel %s @ %s=%s", channel.uuid, timestamp, value)
        return True

    def get(self, uuid: str) -> tp.Optional[tp.Tuple[int, tp.Union[int, float]]]:
        timestamp, value = self.post_timestamps.get(uuid, (0, 0))
        debug("Received Channel %s @ %s=%s", uuid, timestamp, value)
        return timestamp, value

    def get_channels(self) -> tp.List[ChannelDescription]:
        return []
