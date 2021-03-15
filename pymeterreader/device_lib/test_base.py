import time
import typing as tp
import unittest
from threading import Lock

from prometheus_client import Metric

from pymeterreader.device_lib import BaseReader, Sample
from pymeterreader.device_lib.common import ChannelValue, Device


class CountingReader(BaseReader):
    PROTOCOL = "Counter"

    def __init__(self, meter_address: str, sample_meter_id: str = "1234", **kwargs) -> None:
        super().__init__(**kwargs)
        self.implementation_meter_address = meter_address
        self.sample_meter_id = sample_meter_id
        self.__access_lock = Lock()
        self.__fetch_possible = True
        self.counter = 0

    def set_fetch_status(self, fetch_status: bool) -> None:
        with self.__access_lock:
            self.__fetch_possible = fetch_status

    def _fetch_untracked(self) -> tp.Optional[Sample]:
        with self.__access_lock:
            if self.__fetch_possible:
                self.counter += 1
                return Sample(meter_id=self.sample_meter_id, channels=[ChannelValue("COUNTER", self.counter)])
        return None

    @staticmethod
    def detect(**kwargs) -> tp.List[Device]:
        reader = CountingReader("Address")
        sample = reader.fetch()
        if sample is not None:
            return [
                Device(sample.meter_id, reader.implementation_meter_address, CountingReader.PROTOCOL, sample.channels)]
        return []

    def channel_metric(self, channel: ChannelValue, meter_id: str, meter_name: str, epochtime: float) -> tp.Iterator[
        Metric]:
        yield from ()


class TestBaseReader(unittest.TestCase):
    """
    These tests ensure the correct functionality of a Reader extending the BaseReader class
    """

    def test_protocol_defined(self) -> None:
        reader = CountingReader("Address")
        self.assertNotEqual(reader.PROTOCOL, BaseReader.PROTOCOL)

    def test_cache_disabled(self) -> None:
        reader = CountingReader("Address", cache_interval=None)
        self.assertEqual(reader.counter, 0)
        for _ in range(0, 100):
            reader.retrieve()
            # Add 1ms delay to prevent caching in the same millisecond
            time.sleep(0.001)
        self.assertEqual(reader.counter, 100)

    def test_cache_1s(self) -> None:
        cache_intervals = [1.0, 1, "1s"]
        for cache_interval in cache_intervals:
            with self.subTest(cache_interval=cache_interval):
                reader = CountingReader("Address", cache_interval=cache_interval)
                start_time = time.time()
                # Counter increments to 1 on first fetch()
                while reader.counter < 2:
                    reader.retrieve()
                runtime = time.time() - start_time
                delay_after_cache = runtime - 1
                self.assertEqual(reader.counter, 2)
                # Check runtime is within expected bounds
                self.assertGreaterEqual(delay_after_cache, 0)
                self.assertLessEqual(delay_after_cache, 0.5)

    def test_meter_id_matching(self) -> None:
        # (sample_id, search_id)
        match_tuples = [("1 2 3", "123"),
                        ("ABC", "B"),
                        ("ABC", None),
                        ("ABC", "abc")]
        for sample_id, search_id in match_tuples:
            with self.subTest(sample_id=sample_id, search_id=search_id):
                reader = CountingReader("Address", meter_id=search_id, sample_meter_id=sample_id)
                sample = reader.poll()
                self.assertIsNotNone(sample)
                self.assertEqual(sample.meter_id, sample_id)

    def test_meter_name_default(self) -> None:
        reader = CountingReader("Address")
        self.assertEqual(reader.meter_name, "")

    def test_meter_name(self) -> None:
        name = "my meter"
        reader = CountingReader("Address", meter_name=name)
        self.assertEqual(reader.meter_name, name)


if __name__ == '__main__':
    unittest.main()
