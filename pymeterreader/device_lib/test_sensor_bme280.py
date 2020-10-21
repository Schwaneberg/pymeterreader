import unittest
from unittest import mock
from pymeterreader.device_lib.sensor_bme280 import Bme280Reader

pres_raw = 343552
temp_raw = 516760
humi_raw = 24840

class mock_bus:
    cal1 = [109, 111, 157, 104, 50, 0, 33, 142, 248, 214, 208, 11,
            201, 28, 230, 255, 249, 255, 172, 38, 10, 216, 189, 16]
    cal2 = [75]
    cal3 = [135, 1, 0, 15, 46, 3, 30]
    data = [83, 224, 0, 126, 41, 128, 97, 8]

    def __init__(self):
        self.written = []
        self.closed = False

    def write_byte_data(self, addr, reg, val):
        assert not self.closed
        self.written.append((addr, reg, val))

    def read_i2c_block_data(self, addr, reg, length):
        assert addr == 0x76
        assert not self.closed
        if reg == 0x88 and length == 24:
            return self.cal1
        elif reg == 0xA1 and length == 1:
            return self.cal2
        elif reg == 0xE1 and length == 7:
            return self.cal3
        elif reg == 0xF7 and length == 8:
            return self.data
        raise AssertionError("Unknown request")

    def close(self):
        self.closed = True


ref_channels = [{'objName': 'TEMPERATURE', 'value': 19.27, 'unit': '°C'},
                {'objName': 'PRESSURE', 'value': 998.5556593146621, 'unit': 'hPa'},
                {'objName': 'HUMIDITY', 'value': 50.93572133159069, 'unit': '%'}]


class TestBme280(unittest.TestCase):
    @mock.patch('pymeterreader.device_lib.sensor_bme280.smbus', autospec=True)
    def test_readout(self, mock_smbus):
        mock_smbus.SMBus.return_value = mock_bus()
        reader = Bme280Reader("0x76")
        sample = reader.poll()
        self.assertEqual(ref_channels, sample.channels)


if __name__ == '__main__':
    unittest.main()
