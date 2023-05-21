import typing as tp
import unittest
from unittest import mock

from pymeterreader.core import ChannelDescription, ChannelUploadInfo
from pymeterreader.device_lib.common import Sample, ChannelValue
from pymeterreader.gateway import VolkszaehlerGateway
from pymeterreader.meter_reader import map_configuration

EXAMPLE_CONF = {'devices': {
    'electric meter': {'channels': {'1.8.0': {'uuid': 'c07ef180-e4c6-11e9-95a6-434024b862ef', 'interval': '5m'}},
                       'tty': '/dev/ttyUSB0', 'id': '1 EMH00 12345678', 'protocol': 'sml', 'baudrate': 9600},
    'heat meter': {'channels': {6.8: {'uuid': 'c07ef180-e4c6-11e9-95a6-434024b862ef', 'interval': '12h'}},
                   'id': 888777666, 'protocol': 'plain'}, 'climate basement': {
        'channels': {'humidity': {'uuid': 'ca5a59ee-5de5-4a20-a24a-fdb5f64e5db0', 'interval': '1h'},
                     'temperature': {'uuid': '397eda02-7909-4af8-b1a6-3d6c8535229a', 'interval': '1h'},
                     'pressure': {'uuid': '250ca04a-02ee-4a1b-98dd-3423b21008b7', 'interval': '1h'}}, 'id': 118,
        'protocol': 'BME280'}},
                'middleware': {'type': 'volkszaehler', 'middleware_url': 'http://localhost/middleware.php'}}

SAMPLE_BME = Sample()
SAMPLE_BME.meter_id = '0x76'
SAMPLE_BME.channels = [ChannelValue('TEMPERATURE', 20.0, 'C'), ChannelValue('HUMIDITY', 50.0, '%'),
                       ChannelValue('PRESSURE', 1000.0, 'hPa')]

SAMPLE_SML = Sample()
SAMPLE_SML.meter_id = '1 EMH00 12345678'
SAMPLE_SML.channels = [ChannelValue('1.8.0*255', 10000, 'kWh')]

SAMPLE_PLAIN = Sample()
SAMPLE_PLAIN.meter_id = '888777666'
SAMPLE_PLAIN.channels = [ChannelValue('6.8', 20000, 'kWh')]


class MockedGateway(VolkszaehlerGateway):
    def post(self, channel, value, sample_timestamp, poll_timestamp):
        return True

    def get_upload_info(self, channel_info: ChannelUploadInfo) -> tp.Optional[ChannelUploadInfo]:
        return None

    def get_channels(self) -> tp.List[ChannelDescription]:
        return []


class MockedReader():
    def __init__(self, sample):
        self.sample = sample
        self.meter_id = None

    def poll(self):
        return self.sample


class TestMeterReader(unittest.TestCase):
    #pylint: disable=unused-argument
    @mock.patch("pymeterreader.meter_reader.VolkszaehlerGateway", return_value=MockedGateway('http://192.168.1.1/',
                                                                                             True))
    @mock.patch("pymeterreader.meter_reader.SmlReader", return_value=MockedReader(SAMPLE_SML))
    @mock.patch("pymeterreader.meter_reader.PlainReader", return_value=MockedReader(SAMPLE_PLAIN))
    @mock.patch("pymeterreader.meter_reader.Bme280Reader", return_value=MockedReader(SAMPLE_BME))
    def test_meter_reader(self, mock_bme, mock_plain, mock_sml, mock_gw):
        meter_reader_nodes = map_configuration(EXAMPLE_CONF)
        self.assertEqual(3, len(meter_reader_nodes))


if __name__ == '__main__':
    unittest.main()
