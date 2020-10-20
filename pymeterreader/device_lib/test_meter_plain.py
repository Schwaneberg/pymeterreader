import unittest
from unittest import mock
from pymeterreader.device_lib.meter_plain import PlainReader

START_SEQ = b'\x1b\x1b\x1b\x1b\x01\x01\x01\x01'
TEST_FRAME = b'\x026.8(0006047*kWh)6.26(00428.35*m3)9.21(99999999)\r\n'
# 9.21: meter id
# 6.8: count


class MockSerial:
    def __init__(self, chars, lines):
        self.chars = chars
        self.lines = lines
        self.close_called = 0
        self.written = b''

    def read(self):
        if self.chars:
            return self.chars.pop(0)
        else:
            return b'\x1b'

    def write(self, data):
        self.written += data

    def readline(self):
        return self.lines.pop(0)

    def flush(self):
        pass

    def close(self):
        self.close_called +=1


def bytes_to_bytearray(data):
    return [data[i:i+1] for i in range(len(data))]


class TestSmlMeters(unittest.TestCase):
    @mock.patch('pymeterreader.device_lib.meter_sml.os.listdir', autospec=True)
    @mock.patch('pymeterreader.device_lib.meter_plain.serial', autospec=True)
    def test_init(self, mock_serial, mock_listdir):
        mserial = MockSerial(b'', [b'\x00', TEST_FRAME])
        mock_serial.Serial.return_value = mserial
        mock_listdir.return_value = ['ttyUSB0']
        sml_meter = PlainReader('99999999')
        sample = sml_meter.poll()
        self.assertEqual(6047, sample.channels[0]['value'])
        self.assertEqual('6.8', sample.channels[0]['objName'])
        self.assertEqual('kWh', sample.channels[0]['unit'])
        self.assertIsNotNone(sml_meter.tty_path)
        self.assertEqual(1, mserial.close_called)
        self.assertEqual(40 * b'\00' + b"/?!\x0D\x0A", mserial.written)

    @mock.patch('pymeterreader.device_lib.meter_sml.os.listdir', autospec=True)
    @mock.patch('pymeterreader.device_lib.meter_plain.serial', autospec=True)
    def test_init_fail(self, mock_serial, mock_listdir):
        mserial = MockSerial(b'', [b'\x00', b'foobar'])
        mock_serial.Serial.return_value = mserial
        mock_listdir.return_value = ['ttyUSB0']
        sml_meter = PlainReader('99999999')
        sample = sml_meter.poll()
        self.assertIsNone(sample)
        self.assertIsNone(sml_meter.tty_path)
        self.assertEqual(1, mserial.close_called)
        self.assertEqual(40 * b'\00' + b"/?!\x0D\x0A", mserial.written)


if __name__ == '__main__':
    unittest.main()
