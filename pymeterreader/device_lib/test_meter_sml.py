import unittest
from unittest import mock

from serial import serial_for_url
from serial.tools.list_ports_common import ListPortInfo

from pymeterreader.device_lib import SmlReader
from pymeterreader.device_lib.common import ChannelValue, Device
from pymeterreader.device_lib.test_meter import StaticMeterSimulator, SerialTestData


class SmlMeterSimulator(StaticMeterSimulator):
    """
    Simulate a SML Meter that sends a measurement unsolicited
    """

    def __init__(self) -> None:
        test_data = SerialTestData(
            binary=b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01v\x07\x00\x07\r\xf8\xb2\xd7b\x00b\x00rc\x01\x01v\x01\x01\x07\x00\x07\x0b?;\x9d\x0b\t\x01EMH\x00\x00K\x18\xe2\x01\x01cXk\x00v\x07\x00\x07\r\xf8\xb2\xd8b\x00b\x00rc\x07\x01w\x01\x0b\t\x01EMH\x00\x00K\x18\xe2\x07\x01\x00b\n\xff\xffrb\x01e\x0b?\xeejzw\x07\x81\x81\xc7\x82\x03\xff\x01\x01\x01\x01\x04EMH\x01w\x07\x01\x00\x00\x00\t\xff\x01\x01\x01\x01\x0b\t\x01EMH\x00\x00K\x18\xe2\x01w\x07\x01\x00\x01\x08\x00\xffd\x01\x01\xa2\x01b\x1eR\xffV\x00\x10T\xf2\xfe\x01w\x07\x01\x00\x02\x08\x00\xffd\x01\x01\xa2\x01b\x1eR\xffV\x00\x0bHz\xf0\x01w\x07\x01\x00\x01\x08\x01\xff\x01\x01b\x1eR\xffV\x00\x10T\xf2\xfe\x01w\x07\x01\x00\x02\x08\x01\xff\x01\x01b\x1eR\xffV\x00\x0bHz\xf0\x01w\x07\x01\x00\x01\x08\x02\xff\x01\x01b\x1eR\xffV\x00\x00\x00\x00\x00\x01w\x07\x01\x00\x02\x08\x02\xff\x01\x01b\x1eR\xffV\x00\x00\x00\x00\x00\x01w\x07\x01\x00\x10\x07\x00\xff\x01\x01b\x1bR\xffU\xff\xff\xf3\xfa\x01w\x07\x81\x81\xc7\x82\x05\xff\x01rb\x01e\x0b?\xeej\x01\x01\x83\x02X\xaf(\x9aa\x13R\x98L\xf8R\x95#~\xf2fp\xcb=6~!\x8bH\xd9Rx\x9f\xc4\xa5\x88\x86\x04\x01+24\x90\xce\xd3\xd9m4\x1c\x9e\x9c\xcfw\x01\x01\x01c[\x12\x00v\x07\x00\x07\r\xf8\xb2\xdbb\x00b\x00rc\x02\x01q\x01c;\x15\x00\x00\x1b\x1b\x1b\x1b\x1a\x01\x1b\xe1',
            meter_id='1 EMH 00 4921570',
            channels=[ChannelValue(channel_name='129-129:199.130.3*255', value='EMH', unit=None),
                      ChannelValue(channel_name='1-0:1.8.0*255', value=27400268.6, unit='Wh'),
                      ChannelValue(channel_name='1-0:2.8.0*255', value=18929944.0, unit='Wh'),
                      ChannelValue(channel_name='1-0:1.8.1*255', value=27400268.6, unit='Wh'),
                      ChannelValue(channel_name='1-0:2.8.1*255', value=18929944.0, unit='Wh'),
                      ChannelValue(channel_name='1-0:1.8.2*255', value=0, unit='Wh'),
                      ChannelValue(channel_name='1-0:2.8.2*255', value=0, unit='Wh'),
                      ChannelValue(channel_name='1-0:16.7.0*255', value=-307.8, unit='W'),
                      ChannelValue(channel_name='129-129:199.130.5*255',
                                   value='58af289a611352984cf85295237ef26670cb3d367e218b48d952789fc4a5888604012b323490ced3d96d341c9e9ccf77',
                                   unit=None)])
        super().__init__(test_data)


class TestSmlReader(unittest.TestCase):
    @mock.patch('serial.serial_for_url', autospec=True)
    def test_init(self, serial_for_url_mock):
        # Create shared serial instance with unmocked import
        shared_serial_instance = serial_for_url("loop://", baudrate=9600, timeout=5)
        serial_for_url_mock.return_value = shared_serial_instance
        simulator = SmlMeterSimulator()
        simulator.start()
        reader = SmlReader("loop://", meter_id="1EMH004921570")
        sample = reader.retrieve()
        simulator.stop()
        self.assertFalse(shared_serial_instance.is_open)
        self.assertEqual(sample.meter_id, simulator.get_meter_id())
        self.assertEqual(sample.channels, simulator.get_channels())

    def test_init_fail(self):
        reader = SmlReader("loop://", meter_id="1EMH004921570")
        sample = reader.retrieve()
        self.assertIsNone(sample)

    @mock.patch('serial.tools.list_ports.grep', autospec=True)
    @mock.patch('serial.serial_for_url', autospec=True)
    def test_detect(self, serial_for_url_mock, list_ports_mock):
        # Create serial instances with unmocked import
        unconnected_serial_instance = serial_for_url("loop://", baudrate=9600, timeout=5)
        shared_serial_instance = serial_for_url("loop://", baudrate=9600, timeout=5)
        # Mock serial_for_url to return an unconnected instance and one with the simulator
        serial_for_url_mock.side_effect = [shared_serial_instance, unconnected_serial_instance, shared_serial_instance]
        # Create a Simulator. The simulator makes the first call to serial_for_url() and receives the shared instance
        simulator = SmlMeterSimulator()
        simulator.start()
        # Mock available serial ports
        list_ports_mock.return_value = [ListPortInfo("/dev/ttyUSB0"), ListPortInfo("/dev/ttyUSB1")]
        # Start device detection. This triggers the remaining two calls to serial_for_url()
        devices = SmlReader("unused://").detect()
        simulator.stop()
        self.assertFalse(shared_serial_instance.is_open)
        self.assertEqual(len(devices), 1)
        self.assertIn(Device(simulator.get_meter_id(), "/dev/ttyUSB1", "SML", simulator.get_channels()),
                      devices)


if __name__ == '__main__':
    unittest.main()
