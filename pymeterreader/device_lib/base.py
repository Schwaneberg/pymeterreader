"""
Base Reader (ABC)
Created 2020.10.12 by Oliver Schwaneberg
"""
import logging
import typing as tp
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock

from prometheus_client import Metric, Histogram, Counter
from prometheus_client.metrics_core import InfoMetricFamily

from pymeterreader.device_lib.common import Sample, Device, strip, humanfriendly_time_parser, ChannelValue
from pymeterreader.metrics.prefix import METRICS_PREFIX

logger = logging.getLogger(__name__)


class BaseReader(ABC):
    """
    Implementation Base for a Meter Protocol
    """
    PROTOCOL = "ABSTRACT"
    FETCH_HISTOGRAM = Histogram(METRICS_PREFIX + "fetch_duration_seconds",
                                "Runtime of fetching measurement from meters", ["meter_name"])
    FETCH_SUCCESS_COUNTER = Counter(METRICS_PREFIX + "fetch_success",
                                    "Number of successful measurement fetches", ["meter_name"])

    @abstractmethod
    def __init__(self, meter_id: tp.Union[str, int, None] = None, meter_name: str = "",
                 cache_interval: tp.Optional[tp.Union[int, float, str]] = None, **kwargs) -> None:
        """
        Initialize Meter Reader object
        :param meter_id: optional meter identification string (e.g. '1 EMH00 12345678')
        :param meter_name: meter name as specified in the config
        :param cache_interval: enables the caching of samples in the specified timestamp
        :kwargs: implementation specific parameters
        """
        self.meter_id: tp.Optional[str] = None
        self.meter_name = meter_name
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
        # Metrics
        self.fetch_histogram = BaseReader.FETCH_HISTOGRAM.labels(self.meter_name)
        self.fetch_success_counter = BaseReader.FETCH_SUCCESS_COUNTER.labels(self.meter_name)

    @staticmethod
    @abstractmethod
    def detect(**kwargs) -> tp.List[Device]:
        """
        Detect available devices on all possible interfaces
        :kwargs: parameters for the classes that implement detection
        """
        raise NotImplementedError("This is just an abstract class.")

    @abstractmethod
    def _fetch_untracked(self) -> tp.Optional[Sample]:
        """
        Fetch a sample from any connected meter that is reachable with the current settings.
        Intended only for usage in BaseReader! Use fetch() instead!
        :return: Sample, if successful else None
        """
        raise NotImplementedError("This method has to be implemented by readers.")

    def fetch(self) -> tp.Optional[Sample]:
        """
        Fetch a sample from any connected meter that is reachable with the current settings.
        This is a wrapper Method used to create metrics
        :return: Sample, if successful else None
        """
        with self.fetch_histogram.time():
            sample = self._fetch_untracked()
        if sample is not None:
            self.fetch_success_counter.inc()
        return sample

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

    def metrics(self) -> tp.Iterator[Metric]:
        """
        Generate implementation specific Metrics from Samples
        :return: yields Metrics
        """
        # Retrieve sample
        sample = self.retrieve()
        if sample is not None:
            # Extract info labels from Sample
            sample_info_dict = self.sample_info_metric_dict(sample)
            # Try extracting Metric from each Channel
            for channel in sample.channels:
                yield from self.channel_metric(channel, sample.meter_id, self.meter_name, sample.time.timestamp())
        else:
            sample_info_dict = {}
        # Create Info Metric
        reader_info_dict = self.reader_info_metric_dict()
        info_dict = {**sample_info_dict, **reader_info_dict}
        info_metric = InfoMetricFamily(METRICS_PREFIX + "meter", "Additional information about this Meter",
                                       value=info_dict)
        yield info_metric

    def reader_info_metric_dict(self) -> tp.Dict[str, str]:
        """
        Recursively add information labels about this Reader instance
        :return: dict containing labels
        """
        info_dict = {
            "meter_name": self.meter_name,
            "protocol": self.PROTOCOL,
            "cache_interval": str(self.cache_interval.total_seconds()),
        }
        if self.meter_id is not None:
            info_dict["expected_meter_id"] = self.meter_id
        return info_dict

    def sample_info_metric_dict(self, sample: Sample) -> tp.Dict[str, str]:
        """
        Extract information labels about this Reader from a Sample
        :return: dict containing labels
        """
        return {"meter_id": sample.meter_id}

    @abstractmethod
    def channel_metric(self, channel: ChannelValue, meter_id: str, meter_name: str, epochtime: float) -> tp.Iterator[
        Metric]:
        """
        Extract a metric from channels generated by this Reader
        :return: yields Metric
        """
        raise NotImplementedError("Reader subclasses need to implement this method!")

    def meter_id_matches(self, sample: Sample) -> bool:
        """
        Compare the meter_id of this Reader to the one supplied in the sample
        """
        if self.meter_id is None or strip(self.meter_id) in strip(sample.meter_id):
            return True
        logger.warning(
            f"Meter ID in {self.PROTOCOL} sample {sample.meter_id} does not match expected ID {self.meter_id}")
        return False
