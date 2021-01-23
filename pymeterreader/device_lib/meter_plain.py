"""
Plain Reader
Created 2020.10.12 by Oliver Schwaneberg
"""
import re
from logging import debug, error
import typing as tp
import serial
from pymeterreader.device_lib.common import Sample, Device, ChannelValue
from pymeterreader.device_lib.serial_reader import SerialReader


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

    def poll(self) -> tp.Optional[Sample]:
        """
        Public method for polling a Sample from the meter. Enforces that the meter_id matches.
        :return: Sample, if successful
        """
        sample = self.__fetch_sample()
        if sample is not None:
            if self.meter_id_matches(sample):
                return sample
        return None

    def __fetch_sample(self) -> tp.Optional[Sample]:
        """
        Try to retrieve a Sample from any connected meter with the current configuration
        :return: Sample, if successful
        """
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
            debug(f"Plain response: ({init}){response}")
            sample = self.__parse(response)
            if sample is not None:
                return sample
            error("Parsing the response did not yield a Sample!")
        except UnicodeError as err:
            error(f"Decoding the Bytes as Unicode failed: {err}\n{response_bytes}")
        except serial.SerialException as err:
            error(f"Serial Interface error: {err}")
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
        sample = self.__fetch_sample()
        if sample is not None:
            return Device(sample.meter_id, self.serial_url, self.PROTOCOL, sample.channels)
        return None

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
