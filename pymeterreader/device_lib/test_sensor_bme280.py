import unittest
from pymeterreader.device_lib.sensor_bme280 import Bme280Reader


class TestBme280(unittest.TestCase):
    def test_something(self):
        reader = Bme280Reader("0x76")



if __name__ == '__main__':
    unittest.main()
