import logging
from time import time
import typing as tp
from pymeterreader.device_lib import BaseReader, Sample, strip
from pymeterreader.gateway import BaseGateway


class MeterReaderNode:
    """
    MeterReaderNode represents a mapping of a meter's channels to uuids.
    """
    class ChannelInfo:
        def __init__(self, uuid, interval, factor, last_upload, last_value):
            """
            Channel info structure
            :param uuid: uuid of db entry to feed
            :param interval: interval between readings in seconds
            :param factor: multiply to original values, e.g. to conver kWh to Wh
            :param last_upload: time of last upload to middleware
            :param last_value: last value in middleware
            """
            # pylint: disable=too-many-arguments
            self.uuid = uuid
            self.interval = interval
            self.factor = factor
            self.last_upload = last_upload
            self.last_value = last_value

    def __init__(self, channels: tp.Dict[str, tp.Tuple[str, tp.Union[int, float], tp.Union[int, float]]],
                 reader: BaseReader, gateway: BaseGateway):
        """
        Reader node object connects one or more channels
        from a meter to uuids and upload interval times.
        :param channels: map channel ids to uuids, interval times and value multiplication factors
        :param reader: MeterReader object used to poll the meter
        :param gateway: Gateway object used for uploads to the middleware
        """
        self.__channels = {}
        for channel, values in channels.items():
            middleware_entry = gateway.get(values[0])
            if middleware_entry is None:
                logging.warning(f"Cannot get last entry for {values[0]}")
                last_upload = -1
                last_value = -1
            else:
                last_upload = middleware_entry[0]
                last_value = middleware_entry[1]
            self.__channels[channel] = MeterReaderNode.ChannelInfo(uuid=values[0],
                                                                   interval=values[1],
                                                                   factor=values[2],
                                                                   last_upload=last_upload,
                                                                   last_value=last_value)
        self.__reader = reader
        self.__gateway = gateway

    @property
    def poll_interval(self):
        """
        This property indicates the optimal interval to poll this node
        :return: greatest common divisor
        """

        def hcf_naive(a, b):
            if b == 0:
                return a
            return hcf_naive(b, a % b)

        intervals = [channel.interval for channel in self.__channels.values()]
        while len(intervals) > 1:
            intervals = [hcf_naive(intervals[i], intervals[i + 1])
                         if i + 1 < len(intervals) else intervals[i]
                         for i in range(0, len(intervals), 2)]
        return intervals[0]

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
        # pylint: disable=too-many-arguments, too-many-nested-blocks
        now = time()
        posted = 0
        if sample is None:
            sample = self.__reader.poll()
        if sample is not None:
            for entry in sample.channels:
                cur_unit = entry.get('unit', '')
                try:
                    if cur_unit is not None:
                        cur_channel = strip(entry.get('objName', ''))
                        if cur_channel in self.__channels:
                            cur_value = self.__cast_value(entry.get('value', ''),
                                                          self.__channels[cur_channel].factor)
                            if self.__channels[cur_channel].last_upload + self.__channels[cur_channel].interval <= now:
                                # Push hourly interpolated values to enable line plotting in volkszaehler middleware
                                if self.__gateway.interpolate:
                                    self.__push_interpolated_data(cur_value,
                                                                  now,
                                                                  self.__channels[cur_channel])
                                if self.__gateway.post(self.__channels[cur_channel].uuid,
                                                       cur_value,
                                                       sample.time):
                                    self.__channels[cur_channel].last_upload = now
                                    self.__channels[cur_channel].last_value = cur_value
                                    logging.debug(f"POST {cur_value}{cur_unit} to {self.__channels[cur_channel].uuid}")
                                    posted += 1
                                else:
                                    logging.error(f"POST to {self.__channels[cur_channel].uuid} failed!")
                            else:
                                logging.info(f"Skipping upload for {self.__channels[cur_channel].uuid}.")
                                posted += 1
                except ValueError:
                    logging.error(f'Unable to cast {entry.get("value", "N/A")}.')
                    continue
        else:
            logging.error("No data from meter. Skipping interval.")
        return posted == len(self.__channels)

    def __push_interpolated_data(self, cur_value: tp.Union[float, int], cur_time: float, channel: ChannelInfo):
        hours = round((cur_time - channel.last_upload) / 3600)
        diff = cur_value - channel.last_value
        if hours <= 24:
            for hour in range(1, hours):
                btw_time = channel.last_upload + hour * 3600
                btw_value = channel.last_value + diff * (hour / hours)
                self.__gateway.post(channel.uuid,
                                    btw_value,
                                    btw_time)
