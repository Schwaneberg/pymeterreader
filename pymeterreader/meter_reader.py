#!/usr/bin/python3
"""
Primary module
"""
# pylint: disable=wildcard-import
import logging
import signal
import typing as tp
import argparse
import humanfriendly
from yaml import load, FullLoader
from pymeterreader.core import MeterReaderTask, MeterReaderNode
from pymeterreader.device_lib import strip, SmlReader, PlainReader, Bme280Reader, BaseReader
from pymeterreader.gateway import *

PARSER = argparse.ArgumentParser(description='MeterReader reads out supported devices '
                                             'and forwards the data to a middleware '
                                             '(e.g. see https://volkszaehler.org/).')

PARSER.add_argument('-d', '--debug', help='Make process chatty.', action='store_true')
PARSER.add_argument('-c', '--configfile', help="Path to the config file", default='/etc/meter_reader.yaml')


def humanfriendly_time_parser(humanfriendly_input: tp.Union[int, float, str]) -> int:
    """
    Convert a time definition from a string to a int.
    :param humanfriendly_input: Strings like '5s', '10m', '24h' or '1d'
    :returns the input time in seconds as int
    """
    if isinstance(humanfriendly_input, str):
        return humanfriendly.parse_timespan(humanfriendly_input)
    return int(humanfriendly_input)


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
            middleware_type = config.get('middleware').pop('type')
            middleware_configuration: dict = config.get('middleware')
            if middleware_type == 'volkszaehler':
                gateway: tp.Optional[BaseGateway] = VolkszaehlerGateway(**middleware_configuration)
            elif middleware_type == 'debug':
                gateway = DebugGateway(**middleware_configuration)
            else:
                logging.error(f'Middleware "{middleware_type}" not supported!')
                gateway = None
            if gateway is not None:
                for device in config.get('devices').values():
                    meter_id = strip(str(device.pop('id')))
                    protocol = strip(device.pop('protocol'))
                    configuration_channels = device.pop('channels')
                    if protocol == 'SML':
                        reader: tp.Optional[BaseReader] = SmlReader(meter_id, **device)
                    elif protocol == 'PLAIN':
                        reader = PlainReader(meter_id, **device)
                    elif protocol == 'BME280':
                        reader = Bme280Reader(meter_id, **device)
                    else:
                        logging.error(f'Unsupported protocol {protocol}')
                        reader = None
                    if reader is not None:
                        sample = reader.poll()
                        if sample is not None:
                            available_channels = {}
                            for sample_channel in sample.channels:
                                for configuration_channel_name, configuration_channel in configuration_channels.items():
                                    interval = humanfriendly_time_parser(configuration_channel.get('interval', '1h'))
                                    uuid = configuration_channel.get('uuid')
                                    factor = configuration_channel.get('factor', 1)
                                    if strip(str(configuration_channel_name)) in strip(sample_channel.channel_name):
                                        # Replacing config string with exact match
                                        available_channels[sample_channel.channel_name] = (uuid, interval, factor)
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
