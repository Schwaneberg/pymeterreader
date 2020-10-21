"""
Base Reader (ABC)
Created 2020.10.12 by Oliver Schwaneberg
"""
import typing as tp
from abc import ABC, abstractmethod
from logging import warning
from pymeterreader.device_lib.common import Sample


class BaseReader(ABC):
    """
    Reads meters with SML output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with EMH eHZ electrical meters
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "ABSTRACT"
    BOUND_INTERFACES = set()

    @abstractmethod
    def __init__(self, meter_id: tp.Union[str, int], tty=r'/dev/ttyUSB\d+', **kwargs):
        """
        Initialize Meter Reader object
        :param meter_id: meter identification string (e.g. '1 EMH00 12345678')
        :param tty: Name or regex pattern of the tty node to use
        :kwargs: device specific parameters
        """
        self.meter_id = meter_id
        self.tty_pattern = tty
        self._tty_path = None
        if kwargs:
            warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
                    f' {", ".join(kwargs.keys())}')

    def __del__(self):
        """
        Set bound interface free
        """
        self.tty_path = None

    @property
    def tty_path(self):
        return self._tty_path

    @tty_path.setter
    def tty_path(self, tty_path):
        if self._tty_path is not None:
            # Set current interface free
            self.BOUND_INTERFACES.remove(self._tty_path)
        if tty_path is not None:
            # Claim new interface
            if tty_path in self.BOUND_INTERFACES:
                raise KeyError(f"{tty_path} already in use.")
            self.BOUND_INTERFACES.add(tty_path)
        self._tty_path = tty_path

    @abstractmethod
    def poll(self) -> tp.Optional[Sample]:
        """
        Poll the reader and retrievee a new sample
        :return: Sample, if successful else None
        """
        raise NotImplementedError("This is just an abstract class.")
