"""
Base Reader (ABC)
Created 2020.10.12 by Oliver Schwaneberg
"""
import logging
import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock

from pymeterreader.device_lib.common import Sample, Device, strip, humanfriendly_time_parser

logger = logging.getLogger(__name__)


class BaseReader(ABC):
    """
    Implementation Base for a Meter Protocol
    """
    PROTOCOL = "ABSTRACT"

    @abstractmethod
    def __init__(self, meter_id: tp.Union[str, int, None] = None,
                 cache_interval: tp.Optional[tp.Union[int, float, str]] = None, **kwargs) -> None:
        """
        Initialize Meter Reader object
        :param meter_id: optional meter identification string (e.g. '1 EMH00 12345678')
        :param cache_interval: enables the caching of samples in the specified timestamp
        :kwargs: implementation specific parameters
        """
        self.meter_id: tp.Optional[str] = None
        self.cache_interval = humanfriendly_time_parser(cache_interval)
        # Warn to avoid confusion from long cache runtimes
        cache_interval_seconds = self.cache_interval.total_seconds()
        if cache_interval_seconds > 5:
            logger.warning(f"Measurements will be cached for {cache_interval_seconds} seconds!")
        self.__cache_lock = Lock()
        self.__sample_cache: tp.Optional[Sample] = None
        if meter_id is not None:
            self.meter_id = str(meter_id)
        if kwargs:
            logger.warning(f'Unknown parameter{"s" if len(kwargs) > 1 else ""}:'
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
    def fetch(self) -> tp.Optional[Sample]:
        """
        Fetch a sample from any connected meter that is reachable with the current settings
        :return: Sample, if successful else None
        """
        raise NotImplementedError("This is just an abstract class.")

    def poll(self) -> tp.Optional[Sample]:
        """
        Poll a sample from a connected meter if the meter id matches
        :return: Sample, if successful else None
        """
        sample = self.fetch()
        if sample is not None:
            if self.meter_id_matches(sample):
                self.__sample_cache = sample
                return sample
        return None

    def retrieve(self) -> tp.Optional[Sample]:
        """
        Retrieve a sample from cache or polled from the meter with matching meter id
        :return: Sample, if successful else None
        """
        # Prevent queuing of multiple long poll() calls with a Lock
        with self.__cache_lock:
            # Trigger a cache update in poll() if necessary
            if self.__sample_cache is None or self.__sample_cache.time + self.cache_interval < datetime.now(
                    timezone.utc):
                self.poll()
            return self.__sample_cache

    def meter_id_matches(self, sample: Sample) -> bool:
        """
        Compare the meter_id of this Reader to the one supplied in the sample
        """
        if self.meter_id is None or strip(self.meter_id) in strip(sample.meter_id):
            return True
        logger.warning(
            f"Meter ID in {self.PROTOCOL} sample {sample.meter_id} does not match expected ID {self.meter_id}")
        return False
