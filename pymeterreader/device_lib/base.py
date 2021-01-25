"""
Base Reader (ABC)
Created 2020.10.12 by Oliver Schwaneberg
"""
import typing as tp
from abc import ABC, abstractmethod
from logging import warning

from pymeterreader.device_lib.common import Sample, Device, strip


class BaseReader(ABC):
    """
    Implementation Base for a Meter Protocol
    """
    PROTOCOL = "ABSTRACT"

    @abstractmethod
    def __init__(self, meter_id: tp.Union[str, int, None] = None, **kwargs) -> None:
        """
        Initialize Meter Reader object
        :param meter_id: optional meter identification string (e.g. '1 EMH00 12345678')
        :kwargs: implementation specific parameters
        """
        self.meter_id: tp.Optional[str] = None
        if meter_id is not None:
            self.meter_id = str(meter_id)
        if kwargs:
            warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
                    f' {", ".join(kwargs.keys())}')

    @staticmethod
    @abstractmethod
    def detect(**kwargs) -> tp.List[Device]:
        """
        Detect available devices on all possible interfaces
        :kwargs: parameters for the classes that implement detection
        """
        raise NotImplementedError("This is just an abstract class.")

    @abstractmethod
    def poll(self) -> tp.Optional[Sample]:
        """
        Poll the reader and retrieve a new sample
        :return: Sample, if successful else None
        """
        raise NotImplementedError("This is just an abstract class.")

    def meter_id_matches(self, sample: Sample) -> bool:
        """
        Compare the meter_id of this Reader to the one supplied in the sample
        """
        if self.meter_id is None or strip(self.meter_id) in strip(sample.meter_id):
            return True
        warning(f"Meter ID in {self.PROTOCOL} sample {sample.meter_id} does not match expected ID {self.meter_id}")
        return False
