"""
Implementation of a SMA Webconnect module
"""
import logging
import typing as tp
import asyncio
import aiohttp
import pysma
from prometheus_client import Metric
from prometheus_client.metrics_core import CounterMetricFamily

from pymeterreader.device_lib.base import BaseReader
from pymeterreader.device_lib.common import Device, Sample, ChannelValue
from pymeterreader.metrics.prefix import METRICS_PREFIX

logger = logging.getLogger(__name__)


class SMAWebconnectReader(BaseReader):
    """
    Implementaiton of a webconnect reader
    """
    PROTOCOL = "WEBCONNECT"

    def __init__(self, meter_address: str, password: tp.Optional[str] = None, **kwargs):
        """
        Initialize SMA Webconnection
        """
        self.url = meter_address
        self.password = password

    @property
    def meter_id(self):
        return f"WEBCONNECT@{self.url}"

    def detect(**kwargs) -> tp.List[Device]:
        """
        Not implemented for SMA webconnect!
        """
        logger.warning("SMA device discovery is currently not implemented!")
        return []

    async def async_poll(self) -> tp.Optional[Sample]:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            webconnect_session = pysma.SMA(session=session,
                                           url=self.url,
                                           password=self.password)
            sample = Sample(meter_id=self.url)
            sensors = await webconnect_session.get_sensors()
            for sensor in sensors:
                sensor.enabled = True
            await webconnect_session.read(sensors)
            for sensor in sensors:
                sample.channels.append(ChannelValue(sensor.name, sensor.value, sensor.unit))
            await session.close()
        return sample if sample.channels else None

    def poll(self) -> tp.Optional[Sample]:
        return asyncio.run(self.async_poll())

    def channel_metric(self, channel: ChannelValue, meter_id: str, meter_name: str, epochtime: float) \
            -> tp.Iterator[Metric]:
        if channel.unit is not None:
            energy = CounterMetricFamily(
                METRICS_PREFIX + channel.channel_name,
                f"{channel.channel_name.replace('_', ' ')} in {channel.unit}",
                labels=["meter_id", "meter_name"],
            )
            energy.add_metric([meter_id, meter_name], channel.value, timestamp=epochtime)
            yield energy
        else:
            yield from ()

    def _fetch_untracked(self) -> tp.Optional[Sample]:
        return self.poll()
