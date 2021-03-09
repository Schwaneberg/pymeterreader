"""
Common code for all readers
"""
import typing as tp
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from string import digits, ascii_letters, punctuation

import humanfriendly

LEGAL_CHARACTERS = digits + ascii_letters + punctuation


@dataclass(frozen=True)
class ChannelValue:
    """
    Data storage object to represent a channel
    """
    channel_name: str
    value: tp.Union[str, int, float, bytes]
    unit: tp.Optional[str] = None


@dataclass()
class Sample:
    """
    Data storage object to represent a readout
    """
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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

class ConfigurationError(Exception):
    pass

def strip(string: str) -> str:
    """
    Strip irrelevant characters from identification
    :rtype: object
    :param string: original string
    :return: stripped string
    """
    return ''.join([char for char in string if char in LEGAL_CHARACTERS]).strip().upper()


def humanfriendly_time_parser(humanfriendly_input: tp.Optional[tp.Union[int, float, str]]) -> timedelta:
    """
    Convert a time definition from a string to a int.
    :param humanfriendly_input: Strings like '5s', '10m', '24h' or '1d'
    :returns the input time in seconds as int
    """
    time_seconds: int = 0
    if humanfriendly_input is not None:
        if isinstance(humanfriendly_input, str):
            time_seconds = humanfriendly.parse_timespan(humanfriendly_input)
        elif isinstance(humanfriendly_input, (int, float)):
            time_seconds = int(humanfriendly_input)
    return timedelta(0, time_seconds)
