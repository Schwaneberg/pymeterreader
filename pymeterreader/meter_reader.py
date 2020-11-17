#!/usr/bin/python3
"""
Primary module
"""
# pylint: disable=wildcard-import
import logging
import signal
from time import time, sleep
from threading import Thread, Event
from yaml import load, FullLoader
import typing as tp
import humanfriendly
import argparse
from pymeterreader.device_lib import *
from pymeterreader.gateway import *

PARSER = argparse.ArgumentParser(description='MeterReader reads out supported devices '
                                             'and forwards the data to a middleware '
                                             '(e.g. see https://volkszaehler.org/).')

PARSER.add_argument('-d', '--debug', help='Make process chatty.', action='store_true')
PARSER.add_argument('-c', '--configfile', help="User for Jama login", default='/etc/meter_reader.yaml')


def humanfriendly_time_parser(humanfriendly_input: tp.Union[int, float, str]) -> int:
    """
    Convert a time definition from a string to a int.
    :param humanfriendly_input: Strings like '5s', '10m', '24h' or '1d'
    :returns the input time in seconds as int
    """
    if isinstance(humanfriendly_input, str):
        return humanfriendly.parse_timespan(humanfriendly_input)
    return int(humanfriendly_input)


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
        if sample:
            for entry in sample.channels:
                cur_unit = entry.get('unit', '')
                try:
                    if cur_unit:
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


class MeterReaderTask(Thread):
    class Timer(Thread):
        """
        Precise event timer
        """
        def __init__(self, interval: float or int, event: Event):
            Thread.__init__(self)
            self.__interval = interval
            self.__event = event
            self.daemon = True
            self.__stop_event = Event()

        def run(self):
            while not self.__stop_event.is_set():
                sleep(self.__interval)
                self.__event.set()

        def stop(self):
            self.__stop_event.set()

    def __init__(self, meter_reader_node: MeterReaderNode):
        """
        Worker thread will call "poll and push" as often
        as required.
        :param meter_reader_node:
        """
        Thread.__init__(self)
        self.__meter_reader_mode = meter_reader_node
        self.__timer = Event()
        self.stop_event = Event()
        self.__timer_thread = self.Timer(self.__meter_reader_mode.poll_interval,
                                         self.__timer)
        self.daemon = True
        self.__timer_thread.start()
        super().start()

    def __block(self):
        self.__timer.wait()
        self.__timer.clear()
        return True

    def stop(self):
        """
        Call to stop the thread
        """
        self.stop_event.set()
        self.__timer.set()

    def run(self):
        """
        Start the worker thread.
        """
        self.__block()  # initial sample polled during initialization
        while not self.stop_event.is_set():
            self.__meter_reader_mode.poll_and_push()
            self.__block()


def map_configuration(config: dict) -> tp.List[MeterReaderNode]:  # noqa MC0001
    """
    Parsed configuration
    :param config: dict from
    :return:
    """
    # pylint: disable=too-many-locals, too-many-nested-blocks
    meter_reader_nodes = []
    if 'devices' in config and 'middleware' in config:
        try:
            if config.get('middleware').get('type') == 'volkszaehler':
                gateway = VolkszaehlerGateway(config.get('middleware').get('middleware_url'),
                                              config.get('middleware').get('interpolate', True))
            else:
                logging.error(f'Middleware "{config.get("middleware").get("type")}" not supported!')
                gateway = None
            if gateway:
                for device in config.get('devices').values():
                    meter_id = strip(str(device.pop('id')))
                    protocol = strip(device.pop('protocol'))
                    channels = device.pop('channels')
                    if protocol == 'SML':
                        reader = SmlReader(meter_id, **device)
                    elif protocol == 'PLAIN':
                        reader = PlainReader(meter_id, **device)
                    elif protocol == 'BME280':
                        reader = Bme280Reader(meter_id, **device)
                    else:
                        logging.error(f'Unsupported protocol {protocol}')
                        reader = None
                    sample = reader.poll()
                    if sample is not None:
                        available_channels = {}
                        for variable in sample.channels:
                            obj_name = variable.get('objName', '')
                            for channel_name, channel in channels.items():
                                interval = humanfriendly_time_parser(channel.get('interval', '1h'))
                                uuid = channel.get('uuid')
                                factor = channel.get('factor', 1)
                                if strip(str(channel_name)) in strip(str(obj_name)):
                                    # Replacing config string with exact match
                                    available_channels[obj_name] = (uuid, interval, factor)
                        if available_channels:
                            meter_reader_node = MeterReaderNode(available_channels,
                                                                reader,
                                                                gateway)
                            # Perform first push to middleware
                            if meter_reader_node.poll_and_push(sample):
                                meter_reader_nodes.append(meter_reader_node)
                            else:
                                logging.error(f"Not registering node for meter id {reader.meter_id}.")
                        else:
                            logging.warning(f"Cannot register channels for meter {meter_id}.")
                    else:
                        logging.warning(f"Could not read meter id {meter_id} using protocol {protocol}.")
        except KeyError as err:
            logging.error(f"Error while processing configuration: {err}")
    else:
        logging.error("Config file is incomplete.")
    return meter_reader_nodes


class MeterReader:
    """
    Meter Reader main class
    Loads configuration and starts worker threads.
    """
    def __init__(self, config_file):
        signal.signal(signal.SIGINT, self.__keyboard_interrupt_handler)
        config = self.__read_config_file(config_file)
        meter_reader_nodes = map_configuration(config)
        logging.info(f"Starting {len(meter_reader_nodes)} worker threads...")
        self.worker_threads = []
        for meter_reader_node in meter_reader_nodes:
            self.worker_threads.append(MeterReaderTask(meter_reader_node))

    def block_main(self):
        for task in self.worker_threads:
            task.join()

    def __keyboard_interrupt_handler(self, stop_signal, frame):
        del stop_signal
        del frame
        logging.info("<< STOP REQUEST >>")
        for task in self.worker_threads:
            task.stop()

    @staticmethod
    def __read_config_file(file_name: str) -> dict:
        """
        Read a yaml config file and return it as dict
        :param file_name: name of configuration yaml file
        :return: dict with all configuration entries
        """
        try:
            with open(file_name, 'r') as conf_file:
                return load(conf_file, Loader=FullLoader)
        except OSError as err:
            if isinstance(err, FileNotFoundError):
                logging.error(f"File {file_name} can't be found.")
            elif isinstance(err, PermissionError):
                logging.error(f"Not allowed to read {file_name}.")
            else:
                logging.error(f'Error occurred when trying to open {file_name}.')
        return {}


def main():
    ARGS = PARSER.parse_args()
    logging.basicConfig(level=logging.DEBUG if ARGS.debug else logging.INFO)
    meter_reader = MeterReader(ARGS.configfile)
    meter_reader.block_main()


if __name__ == '__main__':
    main()
