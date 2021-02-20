"""
SML Reader
Created 2020.10.12 by Oliver Schwaneberg
"""
from time import time
import os
import re
from threading import Lock
from logging import info, debug, error
import typing as tp
import serial
from sml import SmlBase
from pymeterreader.device_lib.base import BaseReader
from pymeterreader.device_lib.common import Sample, strip, Device


class SmlReader(BaseReader):
    """
    Reads meters with SML output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with EMH eHZ electrical meters
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "SML"
    __SERIAL_LOCK = Lock()
    __START_SEQ = b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01'
    __END_SEQ = b'\x1b\x1b\x1b\x1b'

    def __init__(self, meter_id: str, tty=r'ttyUSB\d+', **kwargs):
        """
        Initialize SML Meter Reader object
        (See https://wiki.volkszaehler.org/software/obis for OBIS code mapping)
        :param meter_id: meter identification string (e.g. '1 EMH00 12345678')
        :param tty: Name or regex pattern of the tty node to use
        :baudrate: serial baudrate, defaults to 9600
        :bytesize: word size on serial port (Default: 8)
        :parity: serial parity, EVEN, ODD or NONE (Default: NONE)
        :stopbits: Number of stopbits (Default: 1)
        """
        try:
            self.baudrate = int(kwargs.pop('baudrate', 9600))
            self.bytesize = int(kwargs.pop('bytesize', 8))
            self.stopbits = int(kwargs.pop('stopbits', 1))
            self.parity = serial.PARITY_NONE
            if 'parity' in kwargs:
                parity = strip(kwargs.pop('parity'))
                if 'EVEN' in parity:
                    self.parity = serial.PARITY_EVEN
                elif 'ODD' in parity:
                    self.parity = serial.PARITY_ODD
        except ValueError:
            error(f'Illegal parameter set: {kwargs}')
            return
        super().__init__(meter_id, tty, **kwargs)

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
        frame = self.__read_frame(self.tty_path, self.baudrate, self.bytesize,
                                  self.parity, self.stopbits)
        if frame is not None and len(frame) > 1:
            sample = self.__parse(frame[1])
            if sample.meter_id is not None:
                return sample
        return None

    @staticmethod
    def __read_frame(tty, baudrate: int = 9600, bytesize: int = 8, parity: str = 'N', stopbits: int = 1):
        try:
            with SmlReader.__SERIAL_LOCK:
                ser = serial.Serial(tty,
                                    baudrate=baudrate,
                                    bytesize=bytesize,
                                    parity=parity,
                                    stopbits=stopbits,
                                    timeout=2)
                timeout = time() + 10.0
                buf = bytes()
                while buf != SmlReader.__START_SEQ and time() < timeout:
                    sign = ser.read()
                    if sign in {b'\x1b', b'\x01'}:
                        buf += sign
                    else:
                        buf = b''

                while not buf[8:-4].endswith(SmlReader.__END_SEQ) and time() < timeout:
                    sign = ser.read()
                    buf += sign
                ser.close()

            if buf[8:-4].endswith(SmlReader.__END_SEQ):
                return SmlBase.parse_frame(buf)
        except OSError as err:
            error(f'Exception occurred while accessing accessing {tty}: {err}')
        return None

    def __probe(self) -> tp.Optional[Sample]:
        sp = os.path.sep
        potential_ttys = [f'{sp}dev{sp}{file_name}'
                          for file_name in os.listdir(f'{sp}dev{sp}')
                          if re.match(self.tty_pattern, file_name)
                          and f'{sp}dev{sp}{file_name}' not in self.BOUND_INTERFACES]
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

    @staticmethod
    def detect(tty=r'ttyUSB\d+', **kwargs) -> tp.List[Device]:
        devices: tp.List[Device] = []
        """
        Detects all SML devices available at matching tty interfa
        :param devices: List of previously detected devices, that will be extendedces
        :param tty: Regex to find candidate interfaces
        """
        def walk_frame(sml_frame, entries):
            if isinstance(sml_frame, list):
                for elem in sml_frame:
                    walk_frame(elem, entries)
            elif isinstance(sml_frame, dict):
                if 'messageBody' in sml_frame:
                    var_list = sml_frame['messageBody'].get('valList', [])
                    for variable in var_list:
                        if 'unit' not in variable and 12 < len(variable.get('value')) < 32:
                            entries["identifier"] = variable.get('value')
                        elif 'unit' in variable:
                            entries[variable['objName']] = (variable['value'], variable['unit'])

        sp = os.path.sep
        used_interfaces = [device.tty for device in devices]
        potential_ttys = [f'{sp}dev{sp}{file_name}'
                          for file_name in os.listdir(f'{sp}dev{sp}')
                          if re.match(tty, file_name)
                          and f'{sp}dev{sp}{file_name}' not in used_interfaces]
        for tty_path in potential_ttys:
            frame = SmlReader.__read_frame(tty_path)
            if frame is not None and len(frame) > 1:
                entries = {}
                walk_frame(frame, entries)
                if 'identifier' in entries:
                    device = Device(entries.pop("identifier"),
                                    tty_path,
                                    'sml',
                                    entries)
                    devices.append(device)
        return devices

    def __parse(self, sml_frame: tp.Union[list, dict], parsed=None) -> Sample:
        """
        Internal helper to extract relevant information
        :param sml_frame: sml data from parser
        :param parsed: only for recursive object reference forwarding
        """
        if parsed is None:
            parsed = Sample()
        if isinstance(sml_frame, list):
            for elem in sml_frame:
                self.__parse(elem, parsed)
        elif isinstance(sml_frame, dict):
            if 'messageBody' in sml_frame:
                var_list = sml_frame['messageBody'].get('valList', [])
                for variable in var_list:
                    if 'unit' not in variable and strip(self.meter_id) in strip(str(variable.get('value', ''))):
                        parsed.meter_id = variable.get('value')
                        break
                if parsed.meter_id:
                    parsed.channels.extend(var_list)
        return parsed
