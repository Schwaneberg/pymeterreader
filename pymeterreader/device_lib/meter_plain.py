"""
Plain Reader
Created 2020.10.12 by Oliver Schwaneberg
"""
import os
import re
from logging import info, debug, error
import typing as tp
import serial
from threading import Lock
from pymeterreader.device_lib.base import BaseReader
from pymeterreader.device_lib.common import Sample, strip


class PlainReader(BaseReader):
    """
    Polls meters with plain text output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with Landis+Gyr ULTRAHEAT T550 (UH50…)
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "PLAIN"
    __START_SEQ = b"/?!\x0D\x0A"
    __SERIAL_LOCK = Lock()

    def __init__(self, meter_id: str, tty=r'ttyUSB\d+', **kwargs: int):
        """
        Initialize Plain Meter Reader object
        (See https://wiki.volkszaehler.org/software/obis for OBIS code mapping)
        :param meter_id: meter identification string (e.g. '12345678')
        :param tty: Name or regex pattern of the tty node to use
        :param send_wakeup_zeros: number of zeros to send ahead of the request string
        :param initial_baudrate: Baudrate used to send the request
        :param baudrate: Baudrate used to read the answer
        """
        super().__init__(meter_id, tty)
        self.wakeup_zeros = kwargs.get('send_wakeup_zeros', 40)
        self.initial_baudrate = kwargs.get('initial_baudrate', 300)
        self.baudrate = kwargs.get('baudrate', 2400)

    def poll(self) -> tp.Optional[Sample]:
        """
        Poll device
        :return: Sample, if successful
        """
        if self.tty_path is None:
            sample = self.__probe()
            if sample:
                return sample
            error("This reader could not be bound to any device node!")
            return None
        try:
            with self.__SERIAL_LOCK:
                ser = serial.Serial(self.tty_path,
                                    baudrate=self.initial_baudrate, bytesize=7,
                                    parity=serial.PARITY_EVEN, stopbits=1,
                                    timeout=2)

                # send wakeup string
                if self.wakeup_zeros:
                    ser.write(b"\x00" * self.wakeup_zeros)

                # send request message
                ser.write(self.__START_SEQ)
                ser.flush()

                # read identification message
                init_msg = ser.readline()

                # change baudrate
                ser.baudrate = self.baudrate
                response = ser.readline().decode('utf-8')
                ser.close()
            debug(f'Plain response: ({init_msg.decode("utf-8")})"{response}"')
            sample = self.__parse(response)
            return sample if sample.meter_id is not None else None
        except OSError as err:
            error(f'Exception occurred while accessing accessing {self.tty_path}: {err}')
        return None

    def __probe(self) -> tp.Optional[Sample]:
        sp = os.path.sep
        potential_ttys = [f'{sp}dev{sp}{file_name}'
                          for file_name in os.listdir(f'{sp}dev{sp}')
                          if re.match(self.tty_pattern, file_name)
                          and file_name not in self.BOUND_INTERFACES]
        if not potential_ttys:
            error(f"Could not find any interfaces matching r'{self.tty_pattern}'!")
            return None
        for tty_path in potential_ttys:
            self.tty_path = tty_path
            sample = self.poll()
            if sample is not None:
                info(f'{self.meter_id} binding to {tty_path}.')
                return sample
            self.tty_path = None
            debug(f'{self.meter_id} not found at {tty_path}.')
        error(f"Could not detect meter {self.meter_id} "
              f"while scanning {', '.join(potential_ttys)}.")
        return None

    def __parse(self, response) -> Sample:
        """
        Internal helper to extract relevant information
        :param sml_frame: sml data from parser
        :param parsed: only for recursive object reference forwarding
        """
        parsed = Sample()
        for ident, value, unit in re.findall(r"([\d.]+)\(([\d.]+)\*?([\w\d.]+)?\)", response):
            if not unit:
                if strip(self.meter_id) in value:
                    parsed.meter_id = value
            else:
                parsed.channels.append({'objName': ident,
                                        'value': float(value),
                                        'unit': unit})
        return parsed
