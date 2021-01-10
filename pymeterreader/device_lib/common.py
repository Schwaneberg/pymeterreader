"""
Common code for all readers
"""
from dataclasses import dataclass, field
from time import time
import typing as tp
from string import digits, ascii_letters, punctuation

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


class Device:
    """
    Representation of a device
    """
    def __init__(self, identifier: str = "", tty: str = "", protocol: str = "",
                 channels: tp.Optional[tp.Dict[str, tp.Tuple[str, str]]] = None):
        self.identifier = identifier
        self.tty = tty
        self.protocol = protocol
        self.channels = channels if channels is not None else {}


def strip(string: str) -> str:
    """
    Strip irrelevant characters from identification
    :rtype: object
    :param string: original string
    :return: stripped string
    """
    return ''.join([char for char in string if char in LEGAL_CHARACTERS]).strip().upper()
