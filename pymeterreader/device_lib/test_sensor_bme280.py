import typing as tp
import unittest
from dataclasses import dataclass
from unittest import mock

from pymeterreader.device_lib.common import ChannelValue, Device, ConfigurationError
from pymeterreader.device_lib.sensor_bme280 import Bme280Reader
from pymeterreader.device_lib.test_meter import TestData


@dataclass(frozen=True)
class I2CTestData(TestData):
    static_registers: tp.Dict[int, int]


class MockBus:
    # pylint: disable=unused-argument
    def __init__(self, i2c_addr: int, test_data: I2CTestData) -> None:
        self.i2c_addr = i2c_addr
        self.test_data = test_data
        self.written = []
        self.open = False

    def write_byte_data(self, i2c_addr, register, value, force=None) -> None:
        assert self.open is True
        self.written.append((i2c_addr, register, value))

    def read_byte_data(self, i2c_addr, register, force=None) -> int:
        if i2c_addr != self.i2c_addr:
            raise OSError(f"Can not access SMBus@{i2c_addr}")
        assert self.open is True
        try:
            return self.test_data.static_registers[register]
        except KeyError as err:
            raise AssertionError(f"Register address {register} is not in the I2CTestData!") from err

    def read_i2c_block_data(self, i2c_addr, register, length, force=None) -> tp.List[int]:
        output_list: tp.List[int] = []
        for offset in range(0, length):
            output_list.append(self.read_byte_data(i2c_addr, register + offset, force))
        return output_list

    def __enter__(self):
        self.open = True
        return self

    def __exit__(self, exit_type, value, traceback) -> None:
        self.open = False


REG_ADDR_CHIP_ID = 0xD0
REG_ADDR_MEASUREMENT_START = 0xF7
REG_ADDR_CALIBRATION1_START = 0x88
REG_ADDR_CALIBRATION2_START = 0xE1
REG_ADDR_STATUS = 0xF3

bm280_testdata = I2CTestData(meter_id="BME280-078fc53ee157b535d787a94e8ac2f05ed6083c8d21ef77389021ae97961d7d0a",
                             channels=[ChannelValue(channel_name="TEMPERATURE", value=19.272266477266385, unit="°C"),
                                       ChannelValue(channel_name="PRESSURE", value=99855.59723964224, unit="Pa"),
                                       ChannelValue(channel_name="HUMIDITY", value=50.935725617532256, unit="%")],
                             static_registers={REG_ADDR_CHIP_ID: 0x60,
                                               REG_ADDR_STATUS: 0b00000000,
                                               REG_ADDR_MEASUREMENT_START + 0: 83,
                                               REG_ADDR_MEASUREMENT_START + 1: 224,
                                               REG_ADDR_MEASUREMENT_START + 2: 0,
                                               REG_ADDR_MEASUREMENT_START + 3: 126,
                                               REG_ADDR_MEASUREMENT_START + 4: 41,
                                               REG_ADDR_MEASUREMENT_START + 5: 128,
                                               REG_ADDR_MEASUREMENT_START + 6: 97,
                                               REG_ADDR_MEASUREMENT_START + 7: 8,
                                               REG_ADDR_CALIBRATION1_START + 0: 109,
                                               REG_ADDR_CALIBRATION1_START + 1: 111,
                                               REG_ADDR_CALIBRATION1_START + 2: 157,
                                               REG_ADDR_CALIBRATION1_START + 3: 104,
                                               REG_ADDR_CALIBRATION1_START + 4: 50,
                                               REG_ADDR_CALIBRATION1_START + 5: 0,
                                               REG_ADDR_CALIBRATION1_START + 6: 33,
                                               REG_ADDR_CALIBRATION1_START + 7: 142,
                                               REG_ADDR_CALIBRATION1_START + 8: 248,
                                               REG_ADDR_CALIBRATION1_START + 9: 214,
                                               REG_ADDR_CALIBRATION1_START + 10: 208,
                                               REG_ADDR_CALIBRATION1_START + 11: 11,
                                               REG_ADDR_CALIBRATION1_START + 12: 201,
                                               REG_ADDR_CALIBRATION1_START + 13: 28,
                                               REG_ADDR_CALIBRATION1_START + 14: 230,
                                               REG_ADDR_CALIBRATION1_START + 15: 255,
                                               REG_ADDR_CALIBRATION1_START + 16: 249,
                                               REG_ADDR_CALIBRATION1_START + 17: 255,
                                               REG_ADDR_CALIBRATION1_START + 18: 172,
                                               REG_ADDR_CALIBRATION1_START + 19: 38,
                                               REG_ADDR_CALIBRATION1_START + 20: 10,
                                               REG_ADDR_CALIBRATION1_START + 21: 216,
                                               REG_ADDR_CALIBRATION1_START + 22: 189,
                                               REG_ADDR_CALIBRATION1_START + 23: 16,
                                               REG_ADDR_CALIBRATION1_START + 24: 0,
                                               REG_ADDR_CALIBRATION1_START + 25: 75,
                                               REG_ADDR_CALIBRATION2_START + 0: 135,
                                               REG_ADDR_CALIBRATION2_START + 1: 1,
                                               REG_ADDR_CALIBRATION2_START + 2: 0,
                                               REG_ADDR_CALIBRATION2_START + 3: 15,
                                               REG_ADDR_CALIBRATION2_START + 4: 46,
                                               REG_ADDR_CALIBRATION2_START + 5: 3,
                                               REG_ADDR_CALIBRATION2_START + 6: 30,
                                               })


class TestBme280(unittest.TestCase):
    @mock.patch("pymeterreader.device_lib.sensor_bme280.SMBus", autospec=True)
    def test_readout(self, mock_smbus):
        mock_smbus.return_value = MockBus(0x76, bm280_testdata)
        reader = Bme280Reader("0x76")
        sample = reader.retrieve()
        self.assertEqual(bm280_testdata.channels, sample.channels)
        self.assertEqual(bm280_testdata.meter_id, sample.meter_id)

    @mock.patch("pymeterreader.device_lib.sensor_bme280.SMBus", autospec=True)
    def test_read_wrong_address(self, mock_smbus):
        mock_smbus.return_value = MockBus(0x76, bm280_testdata)
        reader = Bme280Reader("0x77")
        sample = reader.retrieve()
        self.assertIsNone(sample)

    @mock.patch("pymeterreader.device_lib.sensor_bme280.SMBus", autospec=True)
    def test_detect(self, mock_smbus):
        mock_smbus.return_value = MockBus(0x76, bm280_testdata)
        devices = Bme280Reader.detect()
        self.assertEqual(len(devices), 1)
        self.assertIn(Device(bm280_testdata.meter_id, "0x76@I2C(1)", "BME280", bm280_testdata.channels), devices)

    def test_address_interpretation(self):
        # Test inputs resolving to 0x76
        inputs_0x76 = ["0x76", "118", "0x76@I2C(2)", 0x76, 118]
        for i in inputs_0x76:
            reader = Bme280Reader(meter_address=i)
            self.assertEqual(reader.i2c_address, 0x76)
        # Test inputs resolving to 0x76
        inputs_0x77 = ["0x77", "119", "0x77@I2C(2)", 0x77, 119]
        for i in inputs_0x77:
            reader = Bme280Reader(meter_address=i)
            self.assertEqual(reader.i2c_address, 0x77)
        # Test invalid inputs resolving to the default
        inputs_invalid = ["-", "0x400", "1024", 0x400, 1024]
        for i in inputs_invalid:
            with self.assertRaises(ConfigurationError):
                reader = Bme280Reader(meter_address=i)


def create_testdata_dictstr(self) -> None:
    seq = "REG_ADDR_CHIP_ID:0x60,"
    seq += "REG_ADDR_STATUS:0b00000000,"
    for k, value in enumerate(self.data):
        seq += f"REG_ADDR_MEASUREMENT_START+{k}:{value},"
    for k, value in enumerate(self.calibration1):
        seq += f"REG_ADDR_CALIBRATION1_START+{k}:{value},"
    for k, value in enumerate(self.calibration2):
        seq += f"REG_ADDR_CALIBRATION2_START+{k}:{value},"
    print(seq[:-1])


if __name__ == "__main__":
    unittest.main()
