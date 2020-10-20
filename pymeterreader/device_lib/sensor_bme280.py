"""
Reader for BOSCH BME280 sensor.
Based on Matt Hawkins's implementation on
https://www.raspberrypi-spy.co.uk/
Created 2020.10.17 by Oliver Schwaneberg
"""
from logging import debug, error, warning
import typing as tp
import smbus
import time
from ctypes import c_short
from threading import Lock
from pymeterreader.device_lib.base import BaseReader
from pymeterreader.device_lib.common import Sample


class Bme280Reader(BaseReader):
    """
    Polls meters with plain text output via
    EN 62056-21:2002 compliant optical interfaces.
    Tested with Landis+Gyr ULTRAHEAT T550 (UH50…)
    See https://en.wikipedia.org/wiki/IEC_62056
    """
    PROTOCOL = "BME280"

    __I2C_LOCK = Lock()

    def __init__(self, meter_id: str, tty=r'/dev/ttyUSB\d+', **kwargs: int):
        """
        Initialize BME280 Reader object
        :param meter_id: is a i2c bus id in this case
        :param tty: Name or regex pattern of the tty node to use
        :param send_wakeup_zeros: number of zeros to send ahead of the request string
        :param initial_baudrate: Baudrate used to send the request
        :param baudrate: Baudrate used to read the answer
        """
        if isinstance(meter_id, str):
            if meter_id.lower().startswith('0x'):
                meter_id = int(meter_id.lower(), 16)
            elif meter_id.isnumeric():
                meter_id = int(meter_id)
            else:
                meter_id = 0x76
                error(f'Bme280Reader: Cannot convert id {meter_id} to int.')
        if 127 < meter_id < 256:
            warning("Bme280Reader: 8 bit address defined!")
        elif 255 < meter_id < 1024:
            warning("Bme280Reader: 10 bit address defined!")
        elif meter_id >= 1024:
            error("Bme380Reader: Illegal I2C address defined. Default to 0x76.")
            meter_id = 0x76
        super().__init__(meter_id, tty)

    def poll(self) -> tp.Optional[Sample]:
        """
        Poll device
        :return: True, if successful
        """
        # pylint: disable=too-many-locals, too-many-statements
        # TODO Refactoring required
        sample = Sample()
        with self.__I2C_LOCK:
            try:
                bus = smbus.SMBus(1)
                # Register Addresses
                reg_data = 0xF7
                reg_control = 0xF4

                reg_control_hum = 0xF2

                # Oversample setting - page 27
                oversample_temp = 2
                oversample_pres = 2
                mode = 1

                # Oversample setting for humidity register - page 26
                oversample_hum = 2
                bus.write_byte_data(self.meter_id, reg_control_hum, oversample_hum)

                control = oversample_temp << 5 | oversample_pres << 2 | mode
                bus.write_byte_data(self.meter_id, reg_control, control)

                # Read blocks of calibration data from EEPROM
                # See Page 22 data sheet
                cal1 = bus.read_i2c_block_data(self.meter_id, 0x88, 24)
                cal2 = bus.read_i2c_block_data(self.meter_id, 0xA1, 1)
                cal3 = bus.read_i2c_block_data(self.meter_id, 0xE1, 7)

                # Convert byte data to word values
                dig_t1 = self.__to_uin16(cal1, 0)
                dig_t2 = self.__to_int16(cal1, 2)
                dig_t3 = self.__to_int16(cal1, 4)

                dig_p1 = self.__to_uin16(cal1, 6)
                dig_p2 = self.__to_int16(cal1, 8)
                dig_p3 = self.__to_int16(cal1, 10)
                dig_p4 = self.__to_int16(cal1, 12)
                dig_p5 = self.__to_int16(cal1, 14)
                dig_p6 = self.__to_int16(cal1, 16)
                dig_p7 = self.__to_int16(cal1, 18)
                dig_p8 = self.__to_int16(cal1, 20)
                dig_p9 = self.__to_int16(cal1, 22)

                dig_h1 = self.__to_uint8(cal2, 0)
                dig_h2 = self.__to_int16(cal3, 0)
                dig_h3 = self.__to_uint8(cal3, 2)

                dig_h4 = self.__to_int8(cal3, 3)
                dig_h4 = (dig_h4 << 24) >> 20
                dig_h4 = dig_h4 | (self.__to_int8(cal3, 4) & 0x0F)

                dig_h5 = self.__to_int8(cal3, 5)
                dig_h5 = (dig_h5 << 24) >> 20
                dig_h5 = dig_h5 | (self.__to_uint8(cal3, 4) >> 4 & 0x0F)

                dig_h6 = self.__to_int8(cal3, 6)

                # Wait in ms (Datasheet Appendix B: Measurement time and current calculation)
                wait_time = 1.25 + (2.3 * oversample_temp) + ((2.3 * oversample_pres) + 0.575) + (
                        (2.3 * oversample_hum) + 0.575)
                time.sleep(wait_time / 1000)  # Wait the required time

                # Read temperature/pressure/humidity
                data = bus.read_i2c_block_data(self.meter_id, reg_data, 8)
                pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
                temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
                hum_raw = (data[6] << 8) | data[7]

                # Refine temperature
                var1 = (((temp_raw >> 3) - (dig_t1 << 1)) * (dig_t2)) >> 11
                var2 = (((((temp_raw >> 4) - (dig_t1)) * ((temp_raw >> 4) - (dig_t1))) >> 12) * (dig_t3)) >> 14
                t_fine = var1 + var2
                temperature = float(((t_fine * 5) + 128) >> 8)
                sample.channels.append({'objName': 'TEMPERATURE',
                                        'value': temperature / 100.0,
                                        'unit': '°C'})

                # Refine pressure and adjust for temperature
                var1 = t_fine / 2.0 - 64000.0
                var2 = var1 * var1 * dig_p6 / 32768.0
                var2 = var2 + var1 * dig_p5 * 2.0
                var2 = var2 / 4.0 + dig_p4 * 65536.0
                var1 = (dig_p3 * var1 * var1 / 524288.0 + dig_p2 * var1) / 524288.0
                var1 = (1.0 + var1 / 32768.0) * dig_p1
                if var1 == 0:
                    pressure = 0
                else:
                    pressure = 1048576.0 - pres_raw
                    pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
                    var1 = dig_p9 * pressure * pressure / 2147483648.0
                    var2 = pressure * dig_p8 / 32768.0
                    pressure = pressure + (var1 + var2 + dig_p7) / 16.0
                sample.channels.append({'objName': 'PRESSURE',
                                        'value': pressure / 100.0,
                                        'unit': 'hPa'})

                # Refine humidity
                humidity = t_fine - 76800.0
                humidity = (hum_raw - (dig_h4 * 64.0 + dig_h5 / 16384.0 * humidity)) * (
                        dig_h2 / 65536.0 * (1.0 + dig_h6 / 67108864.0 * humidity
                                            * (1.0 + dig_h3 / 67108864.0 * humidity)))
                humidity = humidity * (1.0 - dig_h1 * humidity / 524288.0)
                if humidity > 100:
                    humidity = 100
                elif humidity < 0:
                    humidity = 0
                sample.channels.append({'objName': 'HUMIDITY',
                                        'value': humidity,
                                        'unit': '%'})
            except OSError as err:
                if isinstance(err, PermissionError):
                    error("Bme280Reader: Insufficient permissions to access I2C bus.")
                else:
                    error(f"Bme280Reader: Cannot detect BME280 at add {self.meter_id:02x}")
        return sample

    @staticmethod
    def __to_int16(data: bytes, index: int) -> int:
        """
        return two bytes from data as a signed 16-bit value
        :param data:
        :param index:
        :return:
        """
        return c_short((data[index + 1] << 8) + data[index]).value

    @staticmethod
    def __to_uin16(data: bytes, index: int) -> int:
        """
        return two bytes from data as an unsigned 16-bit value
        :param data:
        :param index:
        :return:
        """
        return (data[index + 1] << 8) + data[index]

    @staticmethod
    def __to_int8(data: bytes, index: int) -> int:
        # return one byte from data as a signed char
        result = data[index]
        if result > 127:
            result -= 256
        return result

    @staticmethod
    def __to_uint8(data: bytes, index: int) -> int:
        # return one byte from data as an unsigned char
        result = data[index] & 0xFF
        return result

    def read_chip_info(self) -> tp.Optional[tp.Tuple[int, int]]:
        """
        Read chip info if BME280 is available
        :return: chip id and version, if available
        """
        reg_id = 0xD0
        try:
            bus = smbus.SMBus(1)
            chip_id, chip_version = bus.read_i2c_block_data(self.meter_id, reg_id, 2)
            debug(f"BME280 detected with chip id {chip_id} and version {chip_version}.")
            bus.close()
            return chip_id, chip_version
        except OSError as err:
            if isinstance(err, PermissionError):
                error("Bme280Reader: Insufficient permissions to access I2C bus.")
            else:
                error(f"Bme280Reader: Cannot detect BME280 at add {self.meter_id:02x}")
        return None
