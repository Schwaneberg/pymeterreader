"""
Reader for a BOSCH BME280 sensor
"""
import logging
import time
import typing as tp
from dataclasses import dataclass
from enum import Enum, unique
from hashlib import sha256
from sys import byteorder as endianness
from threading import Lock

from construct import Struct, BitStruct, Int16un as uShort, Int16sn as sShort, Int8un as uChar, Int8sn as sChar, \
    BitsInteger, Padding, Bit, ConstructError
from prometheus_client import Metric
from prometheus_client.metrics_core import GaugeMetricFamily

from pymeterreader.metrics.prefix import METRICS_PREFIX

try:
    from smbus2 import SMBus
except ImportError:
    # Redefine SMBus to prevent crashes when evaluation the typing annotations
    SMBus = None
from pymeterreader.device_lib.base import BaseReader
from pymeterreader.device_lib.common import Sample, Device, ChannelValue, ConfigurationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Bme280CalibrationData:
    dig_T1: int # nopep8
    dig_T2: int # nopep8
    dig_T3: int # nopep8
    dig_P1: int # nopep8
    dig_P2: int # nopep8
    dig_P3: int # nopep8
    dig_P4: int # nopep8
    dig_P5: int # nopep8
    dig_P6: int # nopep8
    dig_P7: int # nopep8
    dig_P8: int # nopep8
    dig_P9: int # nopep8
    dig_H1: int # nopep8
    dig_H2: int # nopep8
    dig_H3: int # nopep8
    dig_H4: int # nopep8
    dig_H5: int # nopep8
    dig_H6: int # nopep8


@unique
class Bme280SensorMode(Enum):
    SLEEP = 0
    FORCED = 1
    NORMAL = 3


class Bme280Reader(BaseReader):
    """
    Reads the Bosch BME280 using I2C
    Measurements are interpreted using 64 bit floating point arithmetic
    Device Documentation: https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf
    """
    PROTOCOL = "BME280"
    # Shared Lock for access to all I2C Busses
    I2C_BUS_LOCK = Lock()
    # Register addresses
    REG_ADDR_MEASUREMENT_START = 0xF7
    REG_ADDR_CONFIG = 0xF5
    REG_ADDR_CONTROL_MEASUREMENT = 0xF4
    REG_ADDR_STATUS = 0xF3
    REG_ADDR_CONTROL_HUMIDITY = 0xF2
    REG_ADDR_CALIBRATION2_START = 0xE1
    REG_ADDR_RESET = 0xE0
    REG_ADDR_CHIP_ID = 0xD0
    REG_ADDR_CALIBRATION1_START = 0x88
    # construct Structs for parsing the binary data
    STRUCT_STATUS = BitStruct(Padding(4), "measuring" / Bit, Padding(2), "im_update" / Bit)
    STRUCT_MEASUREMENT = BitStruct("press_raw" / BitsInteger(20),
                                   Padding(4),
                                   "temp_raw" / BitsInteger(20),
                                   Padding(4),
                                   "hum_raw" / BitsInteger(16))
    STRUCT_CALIBRATION1 = Struct("dig_T1" / uShort,
                                 "dig_T2" / sShort,
                                 "dig_T3" / sShort,
                                 "dig_P1" / uShort,
                                 "dig_P2" / sShort,
                                 "dig_P3" / sShort,
                                 "dig_P4" / sShort,
                                 "dig_P5" / sShort,
                                 "dig_P6" / sShort,
                                 "dig_P7" / sShort,
                                 "dig_P8" / sShort,
                                 "dig_P9" / sShort,
                                 "dig_H1" / uChar)
    STRUCT_CALIBRATION2 = Struct("dig_H2" / sShort,
                                 "dig_H3" / uChar,
                                 "misaligned_bitsegment" / BitStruct("byte_0xE4" / BitsInteger(8),
                                                                     "bits_0xE5_left" / BitsInteger(4),
                                                                     "bits_0xE5_right" / BitsInteger(4),
                                                                     "byte_OxE6" / BitsInteger(8)),
                                 "dig_H6" / sChar)

    # pylint: disable=too-many-arguments
    def __init__(self,
                 meter_address: tp.Union[str, int],
                 mode: str = "forced",
                 i2c_bus: int = 1,
                 standby_time: float = 1000,
                 irr_filter_coefficient: int = 0,
                 temperature_oversampling: int = 2,
                 humidity_oversampling: int = 2,
                 pressure_oversampling: int = 2,
                 cache_calibration: bool = True,
                 **kwargs) -> None:
        """
        Initialize Bosch BME280 Reader object
        :param meter_address: I2C sensor address (Default: 0x76)
        :param mode: Operation mode of the sensor
        :param i2c_bus: I2C Bus id (Default: 1)
        :param standby_time: time in milliseconds between sensor measurements in normal mode (Default: 1000)
        :param irr_filter_coefficient: filter coefficient for measurement smoothing (Default: 0)
        :param temperature_oversampling: temperature oversampling setting (Default: 2)
        :param humidity_oversampling: humidity oversampling setting (Default: 2)
        :param pressure_oversampling: pressure oversampling setting (Default: 2)
        :param cache_calibration: controls caching of the sensors calibration data.
        If enabled hot swapping the sensor can not be detected! (Default: True)
        :kwargs: unparsed parameters
        """
        # Test if smbus library has been imported
        try:
            from smbus2 import SMBus # noqa: F401
        except NameError:
            logger.error(
                "Could not import smbus2 library!"
                " This library is missing and Bme280Reader can not function without it!")
            raise
        super().__init__(**kwargs)
        # Parse meter_address to a valid i2c address
        self.i2c_address = Bme280Reader.validate_meter_address(meter_address)
        # Interpret sensor mode
        self.mode = Bme280SensorMode.FORCED
        if "normal" in mode:
            self.mode = Bme280SensorMode.NORMAL
        elif "forced" in mode:
            pass
        else:
            raise ConfigurationError("Sensor mode can only be forced or normal!")
        self.i2c_bus = i2c_bus
        self.standby_time = standby_time
        self.irr_filter_coefficient = irr_filter_coefficient
        self.temperature_oversampling = temperature_oversampling
        self.humidity_oversampling = humidity_oversampling
        self.pressure_oversampling = pressure_oversampling
        self.cache_calibration = cache_calibration
        # Test inputs
        Bme280Reader.generate_register_config(standby_time, irr_filter_coefficient)
        Bme280Reader.generate_register_ctrl_meas(self.mode, temperature_oversampling, pressure_oversampling)
        Bme280Reader.generate_register_ctrl_hum(humidity_oversampling)
        # Reconfigure the sensor on first access
        self.__reconfiguration_required = True
        # Initialize calibration data cache
        self.__calibration_data: tp.Optional[Bme280CalibrationData] = None

    @staticmethod
    def interpret_meter_address(meter_address: tp.Union[str, int]) -> int:
        if isinstance(meter_address, int):
            return meter_address
        if isinstance(meter_address, str):
            address_segments = meter_address.split("@")
            if len(address_segments) > 1:
                logger.warning("@ seperator found in the meter_address!\n"
                               "If you want to specify the I2C Bus use the Parameter i2c_bus instead!")
            address_str = address_segments[0].lower()
            if address_str.startswith("0x"):
                return int(address_str, 16)
            if address_str.isnumeric():
                return int(address_str)
            raise ConfigurationError("meter_address str could not be parsed to an int!")
        raise ConfigurationError("meter_address could not be parsed as int or str!")

    @staticmethod
    def validate_meter_address(meter_address: tp.Union[str, int]) -> int:
        resolved_meter_address = Bme280Reader.interpret_meter_address(meter_address)
        if resolved_meter_address not in [0x76, 0x77]:
            logger.warning(f"Untypical address for BME280 specified:{resolved_meter_address}")
        if 0 <= resolved_meter_address < 1024:
            return resolved_meter_address
        raise ConfigurationError("I2C Address is out of the 10 Bit range")

    def _fetch_untracked(self) -> tp.Optional[Sample]:
        # pylint: disable=too-many-locals
        try:
            with Bme280Reader.I2C_BUS_LOCK:
                with SMBus(self.i2c_bus) as bus:
                    # Read Chip ID
                    chip_id = bus.read_byte_data(self.i2c_address, Bme280Reader.REG_ADDR_CHIP_ID)
                    if self.__calibration_data is None or not self.cache_calibration:
                        self.__calibration_data = self.__read_calibration_data(bus)
                    else:
                        logger.debug("Using cached calibration data")
                    calibration_data = self.__calibration_data
                    # Reconfigure sensor
                    if self.__reconfiguration_required or self.mode is Bme280SensorMode.FORCED:
                        # Reset sensor to sleep mode for reconfiguration
                        self.__reset(bus)
                        logger.debug("Reconfiguring sensor")
                        # Configure humidity
                        self.__set_register_ctrl_hum(bus, self.humidity_oversampling)
                        # Configure other measurement parameters
                        self.__set_register_config(bus, self.standby_time, self.irr_filter_coefficient)
                        # Activate configuration
                        self.__set_register_ctrl_meas(bus, self.mode, self.temperature_oversampling,
                                                      self.pressure_oversampling)
                        self.__reconfiguration_required = False
                    # Wait for the measurement if running in forced mode
                    if self.mode is Bme280SensorMode.FORCED:
                        logger.debug("Waiting for measurement to complete in forced mode")
                        osrs_t_time = 2.3 * self.temperature_oversampling
                        osrs_p_time = 2.3 * self.pressure_oversampling + 0.575
                        osrs_h_time = 2.3 * self.humidity_oversampling + 0.575
                        measurement_time = 1.25 + osrs_t_time + osrs_p_time + osrs_h_time
                        # Wait for measurement to complete
                        time.sleep(measurement_time / 1000)
                        # Read measuring status
                        measuring, _ = self.__read_status(bus)
                        if measuring:
                            logger.error("Measurement is still in progress after maximum measurement time! Aborting...")
                            return None
                    # Read measurement registers
                    logger.debug("Reading measurement registers")
                    measurement = bus.read_i2c_block_data(self.i2c_address, Bme280Reader.REG_ADDR_MEASUREMENT_START, 8)
            # Parse measurement
            logger.debug("Parsing measurement")
            measurement_container = Bme280Reader.STRUCT_MEASUREMENT.parse(bytes(measurement))
            # Calculate fine temperature to enable temperature compensation for the other measurements
            fine_temperature = Bme280Reader.calculate_fine_temperature(calibration_data, measurement_container.temp_raw)
            # Calculate measurement results
            temperature = Bme280Reader.calculate_temperature(fine_temperature)
            pressure = Bme280Reader.calculate_pressure(calibration_data, measurement_container.press_raw,
                                               fine_temperature)
            humidity = Bme280Reader.calculate_humidity(calibration_data, measurement_container.hum_raw,
                                                       fine_temperature)
            # Determine meter_id
            meter_id = Bme280Reader.derive_meter_id(calibration_data, chip_id)
            # Return Sample
            return Sample(meter_id=meter_id, channels=[ChannelValue('TEMPERATURE', temperature, '°C'),
                                                       ChannelValue('PRESSURE', pressure, 'Pa'),
                                                       ChannelValue('HUMIDITY', humidity, '%')])
        except OSError as err:
            logger.error(f"Accessing the smbus faild: {err}")
        except ConstructError as err:
            logger.error(f"Parsing the binary data failed: {err}")
        return None

    @staticmethod
    def calculate_temperature(t_fine: float) -> float:
        return t_fine / 5120.0

    @staticmethod
    def calculate_fine_temperature(calibration_data: Bme280CalibrationData, temp_raw: int) -> float:
        var1 = (temp_raw / 16384.0 - calibration_data.dig_T1 / 1024.0) * calibration_data.dig_T2
        var2 = (
                       (temp_raw / 131072.0 - calibration_data.dig_T1 / 8192.0)
                       * (temp_raw / 131072.0 - calibration_data.dig_T1 / 8192.0)
               ) * calibration_data.dig_T3
        return var1 + var2

    @staticmethod
    def calculate_pressure(calibration_data: Bme280CalibrationData, press_raw: int, t_fine: float) -> float:
        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * (calibration_data.dig_P6) / 32768.0
        var2 = var2 + var1 * (calibration_data.dig_P5) * 2.0
        var2 = (var2 / 4.0) + (calibration_data.dig_P4 * 65536.0)
        var1 = (calibration_data.dig_P3 * var1 * var1 / 524288.0 + calibration_data.dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * calibration_data.dig_P1
        if var1 == 0.0:
            return 0.0
        p = 1048576.0 - press_raw
        p = (p - (var2 / 4096.0)) * 6250.0 / var1
        var1 = calibration_data.dig_P9 * p * p / 2147483648.0
        var2 = p * calibration_data.dig_P8 / 32768.0
        p = p + (var1 + var2 + calibration_data.dig_P7) / 16.0
        return p

    @staticmethod
    def calculate_humidity(calibration_data: Bme280CalibrationData, hum_raw: int, t_fine: float) -> float:
        var_H = t_fine - 76800.0
        var_H = (hum_raw - (calibration_data.dig_H4 * 64.0 + calibration_data.dig_H5 / 16384.0 * var_H)) \
                * (
                        calibration_data.dig_H2 / 65536.0
                        * (
                                1.0 + calibration_data.dig_H6 / 67108864.0 * var_H
                                * (1.0 + calibration_data.dig_H3 / 67108864.0 * var_H)
                        )
                )
        var_H = var_H * (1.0 - calibration_data.dig_H1 * var_H / 524288.0)
        if var_H > 100.0:
            var_H = 100.0
        elif var_H < 0.0:
            var_H = 0.0
        return var_H

    @staticmethod
    def parse_calibration_bytes(calibration_segment1: bytes, calibration_segment2: bytes) -> Bme280CalibrationData:
        # Parse bytes to container
        calibration_segment1_container = Bme280Reader.STRUCT_CALIBRATION1.parse(calibration_segment1)
        calibration_segment2_container = Bme280Reader.STRUCT_CALIBRATION2.parse(calibration_segment2)
        # Bit order from the sensor does not allow for parsing dig_H4 and dig_h5 inside of a BitStruct with BitsInteger
        # Required order is 0xE4,0xE5[right 4 Bits],0xE6,0xE5[left 4 Bits]
        reorder_struct = BitStruct("byte_0xE4" / BitsInteger(8), "bits_0xE5_right" / BitsInteger(4),
                                   "byte_OxE6" / BitsInteger(8), "bits_0xE5_left" / BitsInteger(4))
        reorder_bitsegments = calibration_segment2_container.pop("misaligned_bitsegment")
        reorder_bitsegments.pop("_io")
        # Recreate bytes with correct order
        reordered_bytes = reorder_struct.build(reorder_bitsegments)
        # Parse the reordered bytes with a Bitstruct
        humidity_struct = BitStruct("dig_H4" / BitsInteger(12), "dig_H5" / BitsInteger(12))
        # Parse bytes to container
        humidity_container = humidity_struct.parse(reordered_bytes)
        # Unpack containers into dataclass
        calibration_dict = {**calibration_segment1_container, **calibration_segment2_container, **humidity_container}
        # Remove construct container _io object
        calibration_dict.pop("_io", None)
        return Bme280CalibrationData(**calibration_dict)

    def __read_calibration_data(self, bus: SMBus) -> Bme280CalibrationData:
        """
        This method reads the calibration data from the sensor
        :param bus: an open i2c bus that is already protected by a Lock
        """
        logger.debug("Reading sensor calibration data")
        # Read calibration registers from 0x88 to 0xA1
        calibration_segment1 = bus.read_i2c_block_data(self.i2c_address, Bme280Reader.REG_ADDR_CALIBRATION1_START, 26)
        # Remove unused register 0xA0
        calibration_segment1.pop(24)
        # Read calibration registers from 0xE1 to 0xE7
        calibration_segment2 = bus.read_i2c_block_data(self.i2c_address, Bme280Reader.REG_ADDR_CALIBRATION2_START, 7)
        # Parse bytes in separate function
        return Bme280Reader.parse_calibration_bytes(bytes(calibration_segment1), bytes(calibration_segment2))

    def __read_status(self, bus: SMBus) -> tp.Tuple[bool, bool]:
        """
        This method reads the status from the sensor
        :param bus: an open i2c bus that is already protected by a Lock
        """
        logger.debug("Reading sensor status")
        status_int = bus.read_byte_data(self.i2c_address, Bme280Reader.REG_ADDR_STATUS)
        status_struct = Bme280Reader.STRUCT_STATUS.parse(status_int.to_bytes(1, endianness))
        return bool(status_struct.measuring), bool(status_struct.im_update)

    def __reset(self, bus: SMBus) -> None:
        """
        This method triggers a reset of the sensor
        :param bus: an open i2c bus that is already protected by a Lock
        """
        logger.debug("Soft-Resetting sensor")
        # Write Reset Sequence 0xB6
        bus.write_byte_data(self.i2c_address, Bme280Reader.REG_ADDR_RESET, 0xB6)

    def __set_register_config(self, bus: SMBus, standby_time: float, irr_filter_coefficient: int) -> None:
        """
        This method configures the config register
        :param bus: an open i2c bus that is already protected by a Lock
        """
        config_int = Bme280Reader.generate_register_config(standby_time, irr_filter_coefficient)
        bus.write_byte_data(self.i2c_address, Bme280Reader.REG_ADDR_CONFIG, config_int)

    @staticmethod
    def generate_register_config(standby_time: float, irr_filter_coefficient: int) -> int:
        # Set the standby time
        if standby_time == 1000:
            t_sb = 0b101
        elif standby_time == 500:
            t_sb = 0b100
        elif standby_time == 250:
            t_sb = 0b011
        elif standby_time == 125:
            t_sb = 0b010
        elif standby_time == 62.5:
            t_sb = 0b001
        elif standby_time == 20:
            t_sb = 0b111
        elif standby_time == 10:
            t_sb = 0b110
        elif standby_time == 0.5:
            t_sb = 0b000
        else:
            raise ConfigurationError(f"Standby time value {standby_time} is invalid!")
        # Set irr filter coefficient
        if irr_filter_coefficient == 16:
            irr_filter = 0b100
        elif irr_filter_coefficient == 8:
            irr_filter = 0b011
        elif irr_filter_coefficient == 4:
            irr_filter = 0b010
        elif irr_filter_coefficient == 2:
            irr_filter = 0b001
        elif irr_filter_coefficient == 0:
            irr_filter = 0b000
        else:
            raise ConfigurationError(f"IRR filter coefficient value {irr_filter_coefficient} is invalid!")
        # Disable SPI Interface
        spi3wire_enable = 0
        # Concatenate bit sequences
        config_byte_struct = BitStruct("t_sb" / BitsInteger(3),
                                       "irr_filter" / BitsInteger(3),
                                       "spi3wire_enable" / BitsInteger(2))
        config_byte = config_byte_struct.build({"t_sb": t_sb,
                                                "irr_filter": irr_filter,
                                                "spi3wire_enable": spi3wire_enable})
        return int.from_bytes(config_byte, endianness)

    def __set_register_ctrl_hum(self, bus: SMBus, humidity_oversampling: int) -> None:
        """
        This method configures the ctrl_hum register
        :param bus: an open i2c bus that is already protected by a Lock
        """
        ctrl_hum_int = Bme280Reader.generate_register_ctrl_hum(humidity_oversampling)
        bus.write_byte_data(self.i2c_address, Bme280Reader.REG_ADDR_CONTROL_HUMIDITY, ctrl_hum_int)

    @staticmethod
    def generate_register_ctrl_hum(humidity_oversampling: int) -> int:
        # Set humidity oversampling
        if humidity_oversampling == 16:
            osrs_h = 0b101
        elif humidity_oversampling == 8:
            osrs_h = 0b100
        elif humidity_oversampling == 4:
            osrs_h = 0b011
        elif humidity_oversampling == 2:
            osrs_h = 0b010
        elif humidity_oversampling == 1:
            osrs_h = 0b001
        elif humidity_oversampling == 0:
            osrs_h = 0b000
        else:
            raise ConfigurationError(f"Humidity oversampling value {humidity_oversampling} is invalid!")
        return osrs_h

    def __set_register_ctrl_meas(self, bus: SMBus, mode_enum: Bme280SensorMode, temperature_oversampling: int,  # noqa
                                 pressure_oversampling: int) -> None:
        """
        This method configures the ctrl_meas register
        :param bus: an open i2c bus that is already protected by a Lock
        """
        ctrl_meas_int = Bme280Reader.generate_register_ctrl_meas(mode_enum, temperature_oversampling,
                                                                 pressure_oversampling)
        bus.write_byte_data(self.i2c_address, Bme280Reader.REG_ADDR_CONTROL_MEASUREMENT, ctrl_meas_int)

    # pylint: disable=too-many-branches
    @staticmethod # noqa: MC0001
    def generate_register_ctrl_meas(mode_enum: Bme280SensorMode, temperature_oversampling: int, # noqa: MC0001
                                    pressure_oversampling: int) -> None:
        # Set temperature oversampling
        if temperature_oversampling == 16:
            osrs_t = 0b101
        elif temperature_oversampling == 8:
            osrs_t = 0b100
        elif temperature_oversampling == 4:
            osrs_t = 0b011
        elif temperature_oversampling == 2:
            osrs_t = 0b010
        elif temperature_oversampling == 1:
            osrs_t = 0b001
        elif temperature_oversampling == 0:
            osrs_t = 0b000
        else:
            raise ConfigurationError(f"Pressure oversampling value {temperature_oversampling} is invalid!")
        # Set pressure oversampling
        if pressure_oversampling == 16:
            osrs_p = 0b101
        elif pressure_oversampling == 8:
            osrs_p = 0b100
        elif pressure_oversampling == 4:
            osrs_p = 0b011
        elif pressure_oversampling == 2:
            osrs_p = 0b010
        elif pressure_oversampling == 1:
            osrs_p = 0b001
        elif pressure_oversampling == 0:
            osrs_p = 0b000
        else:
            raise ConfigurationError(f"Pressure oversampling value {pressure_oversampling} is invalid!")
        # Determine operation mode
        if mode_enum is Bme280SensorMode.NORMAL:
            mode = 0b11
        elif mode_enum is Bme280SensorMode.FORCED:
            mode = 0b01
        elif mode_enum is Bme280SensorMode.SLEEP:
            mode = 0b00
        else:
            raise ConfigurationError(f"Measurement mode {mode_enum.name} is undefined!")
        # Concatenate bit sequences
        ctrl_meas_struct = BitStruct("osrs_t" / BitsInteger(3), "osrs_p" / BitsInteger(3), "mode" / BitsInteger(2))
        ctrl_meas_byte = ctrl_meas_struct.build({"osrs_t": osrs_t, "osrs_p": osrs_p, "mode": mode})
        return int.from_bytes(ctrl_meas_byte, endianness)

    @staticmethod
    def derive_meter_id(calibration_data: Bme280CalibrationData, chip_id: int = 0) -> str:
        """
        This method calculates a unique identifier for a sensor by hashing it´s calibration data
        :param calibration_data: Calibration Data from the sensor which should be identified by the meter_id
        :param chip_id: the optional chip id identifies the series of the sensor
        :return: str uniquely identifying the sensor
        """
        calibration_hash = sha256(str(calibration_data).encode())
        # Prefixing the sensor type guards against calibration data collisions between different sensor types
        sensor_type = Bme280Reader.type_from_chip_id(chip_id)
        if sensor_type is None:
            # meter_id matching will still succeed when the prefix is not explicitly specified
            sensor_type = ""
        return f"{sensor_type}-{calibration_hash.hexdigest()}"

    @staticmethod
    def type_from_chip_id(chip_id: int = 0) -> tp.Optional[str]:
        if chip_id == 0x60:
            return "BME280"
        if chip_id == 0x58:
            return "BMP280"
        if chip_id in [0x56, 0x57]:
            return "BMP280(Sample)"
        return None

    def reader_info_metric_dict(self) -> tp.Dict[str, str]:
        info_dict = {
            "meter_address": hex(self.i2c_address),
            "mode": self.mode.name,
            "i2c_bus": str(self.i2c_bus),
            "standby_time": str(self.standby_time),
            "irr_filter_coefficient": str(self.irr_filter_coefficient),
            "temperature_oversampling": str(self.temperature_oversampling),
            "humidity_oversampling": str(self.humidity_oversampling),
            "pressure_oversampling": str(self.pressure_oversampling),
            "cache_calibration": str(self.cache_calibration),
        }
        return {**info_dict, **super().reader_info_metric_dict()}

    def sample_info_metric_dict(self, sample: Sample) -> tp.Dict[str, str]:
        sensor_type, calibration_hash = sample.meter_id.split("-")
        return {
            "sensor_type": sensor_type,
            "calibration_hash": calibration_hash,
            **super().sample_info_metric_dict(sample),
        }

    def channel_metric(self, channel: ChannelValue, meter_id: str, meter_name: str, epochtime: float) -> tp.Iterator[
        Metric]:
        if channel.unit is not None:
            if "°C" in channel.unit and "TEMPERATURE" in channel.channel_name:
                temperature = GaugeMetricFamily(
                    METRICS_PREFIX + "temperature_celsius",
                    "Temperature in degrees celsius",
                    labels=["meter_id", "meter_name"],
                )
                temperature.add_metric([meter_id, meter_name], channel.value, timestamp=epochtime)
                yield temperature
            elif "Pa" in channel.unit and "PRESSURE" in channel.channel_name:
                pressure = GaugeMetricFamily(
                    METRICS_PREFIX + "air_pressure_pascal",
                    "Air pressure in pascal",
                    labels=["meter_id", "meter_name"]
                )
                pressure.add_metric([meter_id, meter_name], channel.value, timestamp=epochtime)
                yield pressure
            elif "%" in channel.unit and "HUMIDITY" in channel.channel_name:
                pressure = GaugeMetricFamily(
                    METRICS_PREFIX + "relative_humidity_percent",
                    "Relative humidity in percent",
                    labels=["meter_id", "meter_name"],
                )
                pressure.add_metric([meter_id, meter_name], channel.value, timestamp=epochtime)
                yield pressure
            yield from ()

    @staticmethod
    def detect(**kwargs) -> tp.List[Device]:
        """
        Return list of available devices
        """
        devices: tp.List[Device] = []
        addresses = [0x76, 0x77]
        # Only the first i2c_bus is scanned
        for address in addresses:
            reader = Bme280Reader(address, cache_calibration=False, **kwargs)
            sample = reader.fetch()
            if sample is not None:
                devices.append(
                    Device(sample.meter_id, f"{hex(address)}@I2C({reader.i2c_bus})", "BME280", sample.channels))
        return devices
