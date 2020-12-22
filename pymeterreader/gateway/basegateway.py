"""
Base Gateway
"""
import typing as tp
from abc import ABC, abstractmethod
from logging import warning


class BaseGateway(ABC):
    """"
    Implementation Base for an upload Gateway
    """

    def __init__(self, **kwargs):
        if kwargs:
            warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
                    f' {", ".join(kwargs.keys())}')

    @abstractmethod
    def post(self, uuid: str, value: tp.Union[int, float], timestamp: int) -> bool:
        raise NotImplementedError("Abstract Base for POST")

    @abstractmethod
    def get(self, uuid: str) -> tp.Optional[tp.Tuple[int, tp.Union[int, float]]]:
        raise NotImplementedError("Abstract Base for GET")

    @abstractmethod
    def get_channels(self) -> dict:
        raise NotImplementedError("Abstract Base for get_channels")

    @staticmethod
    def timestamp_to_int(timestamp: tp.Union[int, float]) -> int:
        if isinstance(timestamp, float):
            timestamp = int(timestamp * 1000)
        return timestamp
