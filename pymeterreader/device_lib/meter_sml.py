"""
SML Reader
Created 2020.10.12 by Oliver Schwaneberg
"""
import logging
import re
import typing as tp

import serial
from prometheus_client import Metric
from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily
from sml import SmlBase, SmlFrame, SmlListEntry, SmlParserError

from pymeterreader.device_lib.common import Sample, Device, ChannelValue
from pymeterreader.device_lib.serial_reader import SerialReader
from pymeterreader.metrics.prefix import METRICS_PREFIX

logger = logging.getLogger(__name__)


class SmlReader(SerialReader):
    """
    Reads meters with SML output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with EMH ED300L and ISKRA MT631 electrical meters
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "SML"
    __START_SEQ = b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01'
    __END_SEQ = b'\x1b\x1b\x1b\x1b'
    OBIS_CODES_METER_ID = ["1-0:0.0.9*255", "1-0:96.1.0*255"]
    OBIS_CODES_MANUFACTURER_ID = ["129-129:199.130.3", "1-0:96.50.1*1"]

    def __init__(self, meter_address: str, **kwargs) -> None:
        """
        Initialize SML Meter Reader object
        (See https://wiki.volkszaehler.org/software/obis for OBIS code mapping)
        :param meter_address: URL specifying the serial Port as required by pySerial serial_for_url()
        :kwargs: parameters for the SerialReader superclass
        """
        super().__init__(meter_address, **kwargs)

    def _fetch_untracked(self) -> tp.Optional[Sample]:
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
            result = SmlBase.parse_frame(sml_reconstructed)
            if len(result) == 2:
                _, frame = result
                if frame is not None:
                    sample = self.__parse(frame)
                    if sample is not None:
                        return sample
                    logger.error("Parsing the SML frame did not yield a Sample!")
            logger.error("Could not parse the binary SML data")
        except AssertionError as err:
            logger.error(f"SML parsing failed: {err}")
        except SmlParserError as err:
            logger.error(f"SML parsing library failed decoding the frame: {err}")
        except serial.SerialException as err:
            logger.error(f"Serial Interface error: {err}")
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
        sample = self.fetch()
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
                        if obis_code in SmlReader.OBIS_CODES_METER_ID:
                            sample.meter_id = value
                        # Add Channels without unit
                        else:
                            sample.channels.append(ChannelValue(obis_code, value))
        return sample

    def sample_info_metric_dict(self, sample: Sample) -> tp.Dict[str, str]:
        info_dict = {}
        for channel in sample.channels:
            # Extract Manufacturer
            if channel.channel_name in SmlReader.OBIS_CODES_MANUFACTURER_ID:
                if isinstance(channel.value, str):
                    info_dict["manufacturer"] = channel.value
                elif isinstance(channel.value, bytes):
                    # Decode bytes
                    info_dict["manufacturer"] = str(channel.value, 'utf-8')
        return {**info_dict, **super().sample_info_metric_dict(sample)}

    def channel_metric(self, channel: ChannelValue, meter_id: str, meter_name: str, epochtime: float) -> tp.Iterator[
        Metric]:
        # Create metrics based on OBIS codes
        if channel.unit is not None:
            if "W" in channel.unit and "1-0:16.7.0*255" in channel.channel_name:
                power_consumption = GaugeMetricFamily(
                    METRICS_PREFIX + "power_consumption_watts",
                    "Momentary power consumption in watts.",
                    labels=["meter_id", "meter_name"],
                )
                power_consumption.add_metric([meter_id, meter_name], channel.value, timestamp=epochtime)
                yield power_consumption
            elif "Wh" in channel.unit:
                match = re.fullmatch(r"1-0:(?P<type_id>1|2)\.8\.(?P<tariff_id>0|1|2)\*255", channel.channel_name)
                if match is not None:
                    # Adhere to Prometheus unit convention
                    # Watt Hours * 3600 Seconds/Hour == Watt Seconds == Joules
                    joules = channel.value * 3600
                    if match.groupdict()["type_id"] == "1":
                        energy_type = "consumption"
                    else:
                        energy_type = "export"
                    if match.groupdict()["tariff_id"] == 1:
                        tariff_id = "1"
                    elif match.groupdict()["tariff_id"] == 2:
                        tariff_id = "2"
                    else:
                        tariff_id = "aggregated"
                    energy = CounterMetricFamily(
                        METRICS_PREFIX + f"energy_{energy_type}_joules_total",
                        f"Energy {energy_type} in joules",
                        labels=["meter_id", "meter_name", "tariff"],
                    )
                    energy.add_metric([meter_id, meter_name, tariff_id], joules, timestamp=epochtime)
                    yield energy
        yield from ()
