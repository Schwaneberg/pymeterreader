"""
Plain Reader
Created 2020.10.12 by Oliver Schwaneberg
"""
import logging
import re
import typing as tp

import serial
from prometheus_client import Metric
from prometheus_client.metrics_core import CounterMetricFamily

from pymeterreader.device_lib.common import Sample, Device, ChannelValue
from pymeterreader.device_lib.serial_reader import SerialReader
from pymeterreader.metrics.prefix import METRICS_PREFIX

logger = logging.getLogger(__name__)


class PlainReader(SerialReader):
    """
    Polls meters with plain text output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with Landis+Gyr ULTRAHEAT T550 (UH50…)
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "PLAIN"
    __START_SEQ = b"/?!\x0D\x0A"

    # pylint: disable=too-many-arguments
    def __init__(self, meter_address: str, baudrate: int = 2400, bytesize=7, initial_baudrate: int = 300,
                 parity="EVEN", send_wakeup_zeros: int = 40, **kwargs) -> None:
        """
        Initialize Plain Meter Reader object
        (See https://wiki.volkszaehler.org/software/obis for OBIS code mapping)
        :param meter_address: URL specifying the serial Port as required by pySerial serial_for_url()
        :param baudrate: baudrate used to receive the measurement (Default: 2400)
        :param bytesize: word size on the serial port (Default: 7)
        :param initial_baudrate: baudrate used to request a measurement (Default: 300)
        :param parity: serial parity, EVEN, ODD or NONE (Default: EVEN)
        :param send_wakeup_zeros: number of zeros to send ahead of the request string (Default: 40)
        :kwargs: parameters for the SerialReader superclass
        """
        super().__init__(meter_address, baudrate=initial_baudrate, bytesize=bytesize, parity=parity, **kwargs)
        self.__wakeup_zeros = send_wakeup_zeros
        self.__initial_baudrate = initial_baudrate
        self.__baudrate = baudrate

    def _fetch_untracked(self) -> tp.Optional[Sample]:
        try:
            # Acquire Lock to prevent pySerial exceptions when trying to access the serial port concurrently
            with self._serial_lock:
                # Open, Use and Close tty_instance
                with self.initialize_serial_port() as serial_port:
                    # Send wakeup Sequence
                    if self.__wakeup_zeros > 0:
                        # Set wakeup baudrate
                        serial_port.baudrate = self.__initial_baudrate
                        # Send wakeup sequence
                        serial_port.write(b"\x00" * self.__wakeup_zeros)
                        # Send request message
                        serial_port.write(self.__START_SEQ)
                        # Clear send buffer
                        serial_port.flush()
                        # Read identification message
                        init_bytes: bytes = serial_port.readline()
                    # Change baudrate to higher speed
                    serial_port.baudrate = self.__baudrate
                    # Read response
                    response_bytes: bytes = serial_port.readline()
            # Decode response
            init: str = init_bytes.decode("utf-8")
            response: str = response_bytes.decode("utf-8")
            logger.debug(f"Plain response: ({init}){response}")
            sample = PlainReader.__parse(response)
            if sample is not None:
                return sample
            logger.error("Parsing the response did not yield a Sample!")
        except UnicodeError as err:
            logger.error(f"Decoding the Bytes as Unicode failed: {err}\n{response_bytes}")
        except serial.SerialException as err:
            logger.error(f"Serial Interface error: {err}")
        return None

    @staticmethod
    def detect(**kwargs) -> tp.List[Device]:
        # Instantiate this Reader class and call SerialReader.detect_serial_devices()
        # pylint: disable=protected-access
        return PlainReader("loop://")._detect_serial_devices(**kwargs)

    def _discover(self) -> tp.Optional[Device]:
        """
        Returns a Device if the class extending SerialReader can discover a meter with the configured settings
        """
        sample = self.fetch()
        if sample is not None:
            return Device(sample.meter_id, self.serial_url, self.PROTOCOL, sample.channels)
        return None

    def reader_info_metric_dict(self) -> tp.Dict[str, str]:
        info_dict = super().reader_info_metric_dict()
        info_dict["initial_baudrate"] = str(self.__initial_baudrate)
        info_dict["baudrate"] = str(self.__baudrate)
        info_dict["wakeup_zeros"] = str(self.__wakeup_zeros)
        return info_dict

    def channel_metric(self, channel: ChannelValue, meter_id: str, meter_name: str, epochtime: float) -> tp.Iterator[
        Metric]:
        if channel.unit is not None:
            if "kWh" in channel.unit and "6.8" in channel.channel_name:
                # Adhere to Prometheus unit convention
                # Watt Hours * 3600 Seconds/Hour == Watt Seconds == Joules
                joules = channel.value * 3600
                energy = CounterMetricFamily(
                    METRICS_PREFIX + "energy_consumption_joules",
                    "Energy consumption in joules",
                    labels=["meter_id", "meter_name"],
                )
                energy.add_metric([meter_id, meter_name], joules, timestamp=epochtime)
                yield energy
            if "m3" in channel.unit and "6.26" in channel.channel_name:
                volume = CounterMetricFamily(
                    METRICS_PREFIX + "flow_volume_cubic_meters",
                    "Flow volume in cubic meters",
                    labels=["meter_id", "meter_name"],
                )
                volume.add_metric([meter_id, meter_name], channel.value, timestamp=epochtime)
                yield volume
        yield from ()

    @staticmethod
    def __parse(response: str) -> tp.Optional[Sample]:
        """
        Internal helper to extract relevant information
        :param response: decoded line
        """
        parsed = None
        for ident, value, unit in re.findall(r"([\d.]+)\(([\d.]+)\*?([\w\d.]+)?\)", response):
            if parsed is None:
                parsed = Sample()
            if not unit and ident == "9.21":
                parsed.meter_id = value
            else:
                parsed.channels.append(ChannelValue(ident, float(value), unit))
        return parsed
