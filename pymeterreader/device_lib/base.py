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
        self._meter_id = meter_id
        self.tty_pattern = tty
        self.tty_path = None
        if kwargs:
            warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
                    f' {", ".join(kwargs.keys())}')

    @property
    def meter_id(self):
        return self._meter_id

    @meter_id.setter
    def meter_id(self, meter_id):
        if self._meter_id is not None:
            self.BOUND_INTERFACES.remove(self._meter_id)
        if meter_id in self.BOUND_INTERFACES:
            raise KeyError(f"{meter_id} already in use.")
        self.BOUND_INTERFACES.add(meter_id)
        self._meter_id = meter_id

    @abstractmethod
    def poll(self) -> tp.Optional[Sample]:
        """
        Poll the reader and retrievee a new sample
        :return: Sample, if successful else None
        """
        raise NotImplementedError("This is just an abstract class.")
