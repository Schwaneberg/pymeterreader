"""
Base Reader (ABC)
Created 2020.10.12 by Oliver Schwaneberg
"""
import typing as tp
from abc import ABC, abstractmethod
from logging import warning
from device_lib.common import Sample


class BaseReader(ABC):
    """
    Reads meters with SML output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with EMH eHZ electrical meters
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "ABSTRACT"
    BOUND_INTERFACES = {}

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
        self.tty_path = None
        if kwargs:
            warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
                    f' {", ".join(kwargs.keys())}')

    @abstractmethod
    def poll(self) -> tp.Optional[Sample]:
        """
        Poll the reader and retrievee a new sample
        :return: Sample, if successful else None
        """
        raise NotImplementedError("This is just an abstract class.")
