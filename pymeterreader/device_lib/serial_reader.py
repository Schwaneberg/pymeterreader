"""
Serial Reader (BaseReader)
"""
import typing as tp
from abc import abstractmethod
from logging import warning, info, error
import serial
import serial.tools.list_ports
from pymeterreader.device_lib.common import Device
from pymeterreader.device_lib.base import BaseReader


class SerialReader(BaseReader):
    """"
    Implementation Base for Meter Protocols that utilize a Serial Connection
    """

    # pylint: disable=too-many-arguments
    @abstractmethod
    def __init__(self, meter_id: tp.Union[str, int], tty: str, baudrate: int = 9600, bytesize: int = 8,
                 parity: str = "None", stopbits: int = 1, timeout: int = 5, **kwargs) -> None:
        """
        Initialize SerialReader object
        :param meter_id: meter identification string (e.g. '1 EMH00 12345678')
        :param tty: URL specifying the serial Port as required by pySerial serial_for_url()
        :param baudrate: serial baudrate (Default: 9600)
        :param bytesize: word size on the serial port (Default: 8)
        :param parity: serial parity, EVEN, ODD or NONE (Default: NONE)
        :param stopbits: Number of stopbits (Default: 1)
        :param timeout: timeout for reading from the serial port (Default: 5s)
        :kwargs: unparsed parameters
        """
        super().__init__(meter_id, **kwargs)
        self.serial_url = tty
        self._serial_instance = None
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.timeout = timeout
        self.parity = serial.PARITY_NONE
        if "EVEN" in parity:
            self.parity = serial.PARITY_EVEN
        elif "ODD" in parity:
            self.parity = serial.PARITY_ODD

    def initialize_serial_port(self, do_not_open: bool = True) -> serial.SerialBase:
        """
        Initialize serial instance if it is uninitialized
        """
        if self._serial_instance is None:
            if self.serial_url.startswith("hwgrep://"):
                warning("Relying on hwgrep for Serial port identification is not recommended!")
            self._serial_instance = serial.serial_for_url(self.serial_url,
                                                          baudrate=self.baudrate,
                                                          bytesize=self.bytesize,
                                                          parity=self.parity,
                                                          stopbits=self.stopbits,
                                                          timeout=self.timeout,
                                                          do_not_open=do_not_open)
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
                serial_reader_implementation = self.__class__("irrelevant", discovered_tty_url, **kwargs)
                # Utilize SubClass._discover() to handle implementation specific discovery
                # pylint: disable=protected-access
                device = serial_reader_implementation._discover()
                if device is not None:
                    devices.append(device)
                else:
                    info(f"No {serial_reader_implementation.PROTOCOL} Meter found at {discovered_tty_url}")
            except Exception:
                error(f"Uncaught Exception while tyring to detect {serial_reader_implementation.PROTOCOL} Meter!"
                      " Please report this to the developers.")
                raise
        return devices

    @abstractmethod
    def _discover(self) -> tp.Optional[Device]:
        """
        Returns a Device if the class extending SerialReader can discover a meter with the configured settings
        """
        raise NotImplementedError("This is just an abstract class.")