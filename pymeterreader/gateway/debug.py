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

    def get_upload_info(self, channel_info: ChannelUploadInfo) -> tp.Optional[ChannelUploadInfo]:
        timestamp, value = self.post_timestamps.get(channel_info.uuid, (None, None))
        if timestamp is not None and value is not None:
            debug("Received Channel %s @ %s=%s", channel_info.uuid, timestamp, value)
            return ChannelUploadInfo(channel_info.uuid, channel_info.interval, channel_info.factor, timestamp, value)
        return None

    def get_channels(self) -> tp.List[ChannelDescription]:
        return []
