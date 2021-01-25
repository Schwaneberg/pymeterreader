"""
Common code for all readers
"""
import typing as tp
from dataclasses import dataclass, field
from string import digits, ascii_letters, punctuation
from time import time

LEGAL_CHARACTERS = digits + ascii_letters + punctuation


@dataclass(frozen=True)
class ChannelValue:
    """
    Data storage object to represent a channel
    """
    channel_name: str
    value: tp.Union[str, int, float]
    unit: tp.Optional[str] = None


@dataclass()
class Sample:
    """
    Data storage object to represent a readout
    """
    time: float = field(default_factory=time)
    meter_id: str = ""
    channels: tp.List[ChannelValue] = field(default_factory=list)


@dataclass(frozen=True)
class Device:
    """
    Representation of a device
    """
    meter_id: str
    meter_address: str
    protocol: str
    channels: tp.List[ChannelValue] = field(default_factory=list)


def strip(string: str) -> str:
    """
    Strip irrelevant characters from identification
    :rtype: object
    :param string: original string
    :return: stripped string
    """
    return ''.join([char for char in string if char in LEGAL_CHARACTERS]).strip().upper()
