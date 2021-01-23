"""
SML Reader
Created 2020.10.12 by Oliver Schwaneberg
"""
from logging import error
import typing as tp
import serial
from sml import SmlBase, SmlFrame, SmlListEntry
from pymeterreader.device_lib.serial_reader import SerialReader
from pymeterreader.device_lib.common import Sample, Device, ChannelValue


class SmlReader(SerialReader):
    """
    Reads meters with SML output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with EMH eHZ electrical meters
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "SML"
    __START_SEQ = b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01'
    __END_SEQ = b'\x1b\x1b\x1b\x1b'

    def __init__(self, meter_address: str, **kwargs) -> None:
        """
        Initialize SML Meter Reader object
        (See https://wiki.volkszaehler.org/software/obis for OBIS code mapping)
        :param meter_address: URL specifying the serial Port as required by pySerial serial_for_url()
        :kwargs: parameters for the SerialReader superclass
        """
        super().__init__(meter_address, **kwargs)

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
                    # Discard Data until finding a Start Sequence in the buffer
                    serial_port.read_until(expected=self.__START_SEQ)
                    # Read Data up to End Sequence
                    payload = serial_port.read_until(expected=self.__END_SEQ)
                    # Read the four subsequent Bytes(Checksum+Number of Fill Bytes)
                    trailer = serial_port.read(4)
            # Reconstruct original SML Structure by combining the extracted sections
            sml_reconstructed = self.__START_SEQ + payload + trailer
            # Test if SML Start is well formatted
            assert sml_reconstructed.startswith(
                self.__START_SEQ), "Reconstructed SML sequence has malformed Start Sequence!"
            # Test if SML End Sequence is present
            assert sml_reconstructed[8:-4].endswith(
                self.__END_SEQ), "Reconstructed SML sequence has malformed End Sequence!"
            _, frame = SmlBase.parse_frame(sml_reconstructed)
            if frame is not None:
                sample = self.__parse(frame)
                if sample is not None:
                    return sample
                error("Parsing the SML frame did not yield a Sample!")
            error("Could not parse the binary SML data")
        except AssertionError as err:
            error(f"SML parsing failed: {err}")
        except serial.SerialException as err:
            error(f"Serial Interface error: {err}")
        return None

    @staticmethod
    def detect(**kwargs) -> tp.List[Device]:
        # Instantiate this Reader class and call SerialReader.detect_serial_devices()
        # pylint: disable=protected-access
        return SmlReader("loop://")._detect_serial_devices(**kwargs)

    def _discover(self) -> tp.Optional[Device]:
        """
        Returns a Device if the class extending SerialReader can discover a meter with the configured settings
        """
        sample = self.__fetch_sample()
        if sample is not None:
            return Device(sample.meter_id, self.serial_url, self.PROTOCOL, sample.channels)
        return None

    @staticmethod
    def __parse(sml_frame: SmlFrame) -> tp.Optional[Sample]:
        """
        Internal helper to extract relevant information
        :param sml_frame: SmlFrame from parser
        """
        sample = None
        for sml_mesage in sml_frame:
            if 'messageBody' in sml_mesage:
                sml_list: tp.List[SmlListEntry] = sml_mesage['messageBody'].get('valList', [])
                for sml_entry in sml_list:
                    if sample is None:
                        sample = Sample()
                    obis_code: str = sml_entry.get('objName', '')
                    value = sml_entry.get('value', '')
                    # Differentiate SML Messages based on whether they contain a unit
                    if 'unit' in sml_entry:
                        sample.channels.append(ChannelValue(obis_code, value, sml_entry.get('unit')))
                    else:
                        # Determine the meter_id from OBIS code
                        if '1-0:0.0.9' in obis_code:
                            sample.meter_id = value
                        # Add Channels without unit
                        else:
                            sample.channels.append(ChannelValue(obis_code, value))
        return sample
