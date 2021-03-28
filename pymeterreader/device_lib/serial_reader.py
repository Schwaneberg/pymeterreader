"""
Serial Reader (BaseReader)
"""
import logging
import typing as tp
from abc import abstractmethod
from threading import Lock

import serial
import serial.tools.list_ports
from prometheus_client import Counter

from pymeterreader.device_lib.base import BaseReader
from pymeterreader.device_lib.common import Device
from pymeterreader.metrics.prefix import METRICS_PREFIX

logger = logging.getLogger(__name__)


class SerialReader(BaseReader):
    """"
    Implementation Base for Meter Protocols that utilize a Serial Connection
    """
    SERIAL_INIT_COUNTER = Counter(METRICS_PREFIX + "serial_initializations",
                                  "Number of pyserial initializations", ["meter_name"])

    # pylint: disable=too-many-arguments
    @abstractmethod
    def __init__(self, meter_address: str, baudrate: int = 9600, bytesize: int = 8,
                 parity: str = "None", stopbits: int = 1, timeout: int = 5, **kwargs) -> None:
        """
        Initialize SerialReader object
        :param meter_address: URL specifying the serial Port as required by pySerial serial_for_url()
        :param baudrate: serial baudrate (Default: 9600)
        :param bytesize: word size on the serial port (Default: 8)
        :param parity: serial parity, EVEN, ODD or NONE (Default: NONE)
        :param stopbits: Number of stopbits (Default: 1)
        :param timeout: timeout for reading from the serial port (Default: 5s)
        :kwargs: unparsed parameters
        """
        super().__init__(**kwargs)
        self.serial_url = meter_address
        self._serial_instance = None
        self._serial_lock = Lock()
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.timeout = timeout
        self.parity = serial.PARITY_NONE
        if "EVEN" in parity:
            self.parity = serial.PARITY_EVEN
        elif "ODD" in parity:
            self.parity = serial.PARITY_ODD
        # Metrics
        self.serial_init_counter = SerialReader.SERIAL_INIT_COUNTER.labels(self.meter_name)

    def initialize_serial_port(self, do_not_open: bool = True) -> serial.SerialBase:
        """
        Initialize serial instance if it is uninitialized
        """
        if self._serial_instance is None:
            if self.serial_url.startswith("hwgrep://"):
                logger.warning("Relying on hwgrep for Serial port identification is not recommended!")
            self._serial_instance = serial.serial_for_url(self.serial_url,
                                                          baudrate=self.baudrate,
                                                          bytesize=self.bytesize,
                                                          parity=self.parity,
                                                          stopbits=self.stopbits,
                                                          timeout=self.timeout,
                                                          do_not_open=do_not_open)
            self.serial_init_counter.inc()
        return self._serial_instance

    def _detect_serial_devices(self, tty_regex: str = ".*", **kwargs) -> tp.List[Device]:
        """
        Test all available serial ports for a meter of the SerialReader implementation
        :param tty_regex: Regex to filter the output from serial.tools.list_ports()
        :kwargs: parameters that are passed to the SerialReader implementation that is instantiated to test every port
        """
        devices: tp.List[Device] = []
        # Test all matching tty ports
        for possible_port_info in serial.tools.list_ports.grep(tty_regex):
            try:
                discovered_tty_url = possible_port_info.device
                # Create new Instance of the current SerialReader implementation
                # This ensures that the internal state is reset for every discovery
                serial_reader_implementation = self.__class__(discovered_tty_url, **kwargs)
                # Utilize SubClass._discover() to handle implementation specific discovery
                # pylint: disable=protected-access
                device = serial_reader_implementation._discover()
                if device is not None:
                    devices.append(device)
                else:
                    logger.info(f"No {serial_reader_implementation.PROTOCOL} Meter found at {discovered_tty_url}")
            except Exception:
                logger.error(f"Uncaught Exception while tyring to detect {serial_reader_implementation.PROTOCOL} Meter!"
                             " Please report this to the developers.")
                raise
        return devices

    @abstractmethod
    def _discover(self) -> tp.Optional[Device]:
        """
        Returns a Device if the class extending SerialReader can discover a meter with the configured settings
        """
        raise NotImplementedError("This is just an abstract class.")

    def reader_info_metric_dict(self) -> tp.Dict[str, str]:
        info_dict = {
            "meter_address": self.serial_url,
            "baudrate": str(self.baudrate),
            "bytesize": str(self.bytesize),
            "stopbits": str(self.stopbits),
            "timeout": str(self.timeout),
            "parity": str(self.parity),
        }
        return {**info_dict, **super().reader_info_metric_dict()}
