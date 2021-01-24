"""
Base Gateway
"""
import typing as tp
from abc import ABC, abstractmethod
from logging import warning

from pymeterreader.core.channel_description import ChannelDescription
from pymeterreader.core.channel_upload_info import ChannelUploadInfo


class BaseGateway(ABC):
    """"
    Implementation Base for an upload Gateway
    """

    def __init__(self, **kwargs) -> None:
        if kwargs:
            warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
                    f' {", ".join(kwargs.keys())}')

    @abstractmethod
    def post(self, channel: ChannelUploadInfo, value: tp.Union[int, float], sample_timestamp: tp.Union[int, float],
             poll_timestamp: tp.Union[int, float]) -> bool:
        raise NotImplementedError("Abstract Base for POST")

    @abstractmethod
    def get(self, uuid: str) -> tp.Optional[tp.Tuple[int, tp.Union[int, float]]]:
        raise NotImplementedError("Abstract Base for GET")

    @abstractmethod
    def get_channels(self) -> tp.List[ChannelDescription]:
        raise NotImplementedError("Abstract Base for get_channels")

    @staticmethod
    def timestamp_to_int(timestamp: tp.Union[int, float]) -> int:
        if isinstance(timestamp, float):
            timestamp = int(timestamp * 1000)
        return timestamp
