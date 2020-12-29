"""
Commmon code for all readers
"""
from time import time
import typing as tp
from string import digits, ascii_letters, punctuation
legal_characters = digits + ascii_letters + punctuation


class Sample:
    """
    Data storage object to represent a readout
    """

    def __init__(self):
        self.time = time()
        self.meter_id = None
        self.channels = []


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
    Strip irrelevant characters from identifiaction
    :rtype: object
    :param string: original string
    :return: stripped string
    """
    return ''.join([char for char in string if char in legal_characters]).strip().upper()
