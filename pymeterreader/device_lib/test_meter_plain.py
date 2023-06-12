import unittest
from unittest import mock

from serial import serial_for_url, PortNotOpenError
from serial.tools.list_ports_common import ListPortInfo

from pymeterreader.device_lib import PlainReader
from pymeterreader.device_lib.common import ChannelValue, Device
from pymeterreader.device_lib.test_meter import StaticMeterSimulator, SerialTestData


class PlainMeterSimulator(StaticMeterSimulator):
    """
    Simulate a Plain Meter that requires a wakeup before sending a sample.
    This implementation is not compatible with a loop:// interface since
    it depends on having different send/receiver buffers.
    """

    def __init__(self) -> None:
        start_sequence = b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01'
        test_frame = b'\x026.8(0006047*kWh)6.26(00428.35*m3)9.21(99999999)\r\n'
        test_data = SerialTestData(
            binary=start_sequence + test_frame,
            meter_id='99999999',
            channels=[ChannelValue(channel_name='6.8', value=6047.0, unit='kWh'),
                      ChannelValue(channel_name='6.26', value=428.35, unit='m3')])
        super().__init__(test_data)

    def wait_for_wakeup(self) -> bool:
        wakeup_counter = 0
        wakeup_sequence = b"\x00"
        # Loop until we have received the wakeup sequence
        while wakeup_counter < 40:
            try:
                if self.tty.read(1) == wakeup_sequence:
                    wakeup_counter += 1
                else:
                    # Reset counter if the sequence is interrupted
                    wakeup_counter = 0
            # Keep trying even when the serial port has not been opened or has already been closed by the reader
            except PortNotOpenError:
                pass
        # Read start sequence
        start_sequence = b"/?!\x0D\x0A"
        # Block until start sequence length has been read
        sequence = self.tty.read(len(start_sequence))
        # Return whether the start_sequence has been received
        return sequence == start_sequence


class SimplePlainMeterSimulator(StaticMeterSimulator):
    """
    Simulate a Plain Meter that continuously clears the receive buffer before sending a sample
    Thus it is compatible with a loop:// interface.
    """

    def __init__(self) -> None:
        start_sequence = b"/?!\x0D\x0A"
        test_frame = b'\x026.8(0006047*kWh)6.26(00428.35*m3)9.21(99999999)\r\n'
        test_data = SerialTestData(
            binary=start_sequence + test_frame,
            meter_id='99999999',
            channels=[ChannelValue(channel_name='6.8', value=6047.0, unit='kWh'),
                      ChannelValue(channel_name='6.26', value=428.35, unit='m3')])
        super().__init__(test_data)


class TestPlainReader(unittest.TestCase):
    @mock.patch('serial.serial_for_url', autospec=True)
    def test_init(self, serial_for_url_mock):
        # Create shared serial instance with unmocked import
        shared_serial_instance = serial_for_url("loop://", baudrate=9600, timeout=5)
        serial_for_url_mock.return_value = shared_serial_instance
        simulator = SimplePlainMeterSimulator()
        simulator.start()
        reader = PlainReader("loop://")
        sample = reader.retrieve()
        simulator.stop()
        self.assertEqual(sample.meter_id, simulator.get_meter_id())
        self.assertEqual(sample.channels, simulator.get_channels())

    def test_init_fail(self):
        reader = PlainReader("loop://")
        sample = reader.retrieve()
        self.assertIsNone(sample)

    @mock.patch('serial.tools.list_ports.grep', autospec=True)
    @mock.patch('serial.serial_for_url', autospec=True)
    def test_detect(self, serial_for_url_mock, list_ports_mock):
        # Create serial instances with unmocked import
        unconnected_serial_instance = serial_for_url("loop://", baudrate=2400, timeout=5)
        shared_serial_instance = serial_for_url("loop://", baudrate=2400, timeout=5)
        # Mock serial_for_url to return an unconnected instance and one with the simulator
        serial_for_url_mock.side_effect = [shared_serial_instance, unconnected_serial_instance, shared_serial_instance]
        # Create a Simulator. The simulator makes the first call to serial_for_url() and receives the shared instance
        simulator = SimplePlainMeterSimulator()
        simulator.start()
        # Mock available serial ports
        list_ports_mock.return_value = [ListPortInfo("/dev/ttyUSB0"), ListPortInfo("/dev/ttyUSB1")]
        # Start device detection. This triggers the remaining two calls to serial_for_url()
        devices = PlainReader("unused://").detect()
        simulator.stop()
        self.assertFalse(shared_serial_instance.is_open)
        self.assertEqual(len(devices), 1)
        self.assertIn(Device(simulator.get_meter_id(), "/dev/ttyUSB1", "PLAIN", simulator.get_channels()),
                      devices)


if __name__ == '__main__':
    unittest.main()
