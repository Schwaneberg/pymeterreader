import logging
import typing as tp
from datetime import datetime, timezone

from pymeterreader.core.channel_upload_info import ChannelUploadInfo
from pymeterreader.device_lib import BaseReader, Sample, strip
from pymeterreader.gateway import BaseGateway


class MeterReaderNode:
    """
    MeterReaderNode represents a mapping of a meter's channels to uuids.
    """

    def __init__(self, channels: tp.Dict[str, ChannelUploadInfo], reader: BaseReader, gateway: BaseGateway):
        """
        Reader node object connects one or more channels
        from a meter to uuids and upload interval times.
        :param channels: map channel ids to uuids, interval times and value multiplication factors
        :param reader: MeterReader object used to poll the meter
        :param gateway: Gateway object used for uploads to the middleware
        """
        self.__channels: tp.Dict[str, ChannelUploadInfo] = {}
        for channel_name, channel_info in channels.items():
            gateway_upload_info = gateway.get_upload_info(channel_info)
            if gateway_upload_info is not None:
                self.__channels[channel_name] = gateway_upload_info
            else:
                logging.warning(f"Cannot get last entry for uuid {channel_info.uuid}")
                self.__channels[channel_name] = channel_info
        self.__reader = reader
        self.__gateway = gateway

    @property
    def poll_interval(self) -> int:
        """
        This property indicates the optimal interval to poll this node
        :return: greatest common divisor
        """

        def hcf_naive(a: int, b: int) -> int:
            if b == 0:
                return a
            return hcf_naive(b, a % b)

        intervals = [int(channel.interval.total_seconds()) for channel in self.__channels.values()]
        while len(intervals) > 1:
            intervals = [hcf_naive(intervals[i], intervals[i + 1])
                         if i + 1 < len(intervals) else intervals[i]
                         for i in range(0, len(intervals), 2)]
        # Poll every 5 minutes if polling is disabled
        return next(iter(intervals), 600)

    @staticmethod
    def __cast_value(value_orig: tp.Union[str, int, float], factor) -> tp.Union[int, float]:
        """
        Cast to int if possible, else float
        :param value_orig: value as str, int or float
        :return: value as int or float
        """
        if isinstance(value_orig, str):
            value = int(value_orig) if value_orig.isnumeric() else float(value_orig)
        else:
            value = value_orig
        return value * factor

    def poll_and_push(self, sample: Sample = None) -> bool:
        """
        Poll a channel and push it by it's uuid
        :param sample: optional sample data (skip polling)
        :returns True if successful
        """
        # pylint: disable=too-many-nested-blocks
        now = datetime.now(timezone.utc)
        posted = 0
        if sample is None:
            sample = self.__reader.poll()
        if sample is not None:
            for channel in sample.channels:
                cur_unit = channel.unit
                try:
                    if cur_unit is not None:
                        cur_channel = strip(channel.channel_name)
                        if cur_channel in self.__channels:
                            cur_value = MeterReaderNode.__cast_value(channel.value, self.__channels[cur_channel].factor)
                            next_scheduled_upload = self.__channels[cur_channel].last_upload \
                                                    + self.__channels[cur_channel].interval
                            if next_scheduled_upload <= now:
                                if self.__gateway.post(self.__channels[cur_channel],
                                                       cur_value,
                                                       sample.time,
                                                       now):
                                    self.__channels[cur_channel].last_upload = now
                                    self.__channels[cur_channel].last_value = cur_value
                                    logging.debug(f"POST {cur_value}{cur_unit} to {self.__channels[cur_channel]}")
                                    posted += 1
                                else:
                                    logging.error(f"POST to {self.__channels[cur_channel].uuid} failed!")
                            else:
                                logging.info(f"Skipping upload for {self.__channels[cur_channel].uuid}.")
                                posted += 1
                except ValueError:
                    logging.error(f'Unable to cast {channel.value}.')
                    continue
        else:
            logging.error("No data from meter. Skipping interval.")
        return posted == len(self.__channels)
