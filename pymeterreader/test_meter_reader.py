import unittest
from unittest import mock
from pymeterreader.meter_reader import map_configuration
from pymeterreader.gateway import BaseGateway
from pymeterreader.device_lib.common import Sample

EXAMPLE_CONF = {'devices': {
    'electric meter': {'channels': {'1.8.0': {'uuid': 'c07ef180-e4c6-11e9-95a6-434024b862ef', 'interval': '5m'}},
                       'tty': '/dev/ttyUSB\\d+', 'id': '1 EMH00 12345678', 'protocol': 'sml', 'baudrate': 9600},
    'heat meter': {'channels': {6.8: {'uuid': 'c07ef180-e4c6-11e9-95a6-434024b862ef', 'interval': '12h'}},
                   'id': 888777666, 'protocol': 'plain'}, 'climate basement': {
        'channels': {'humidity': {'uuid': 'ca5a59ee-5de5-4a20-a24a-fdb5f64e5db0', 'interval': '1h'},
                     'temperature': {'uuid': '397eda02-7909-4af8-b1a6-3d6c8535229a', 'interval': '1h'},
                     'pressure': {'uuid': '250ca04a-02ee-4a1b-98dd-3423b21008b7', 'interval': '1h'}}, 'id': 118,
        'protocol': 'BME280'}},
                'middleware': {'type': 'volkszaehler', 'middleware_url': 'http://localhost/middleware.php'}}

SAMPLE_BME = Sample()
SAMPLE_BME.meter_id = '0x76'
SAMPLE_BME.channels = [{'objName': 'TEMPERATURE', 'value': 20.0, 'unit': 'C'},
            {'objName': 'HUMIDITY', 'value': 50.0, 'unit': '%'},
            {'objName': 'PRESSURE', 'value': 1000.0, 'unit': 'hPa'}]

SAMPLE_SML = Sample()
SAMPLE_SML.meter_id = '1 EMH00 12345678'
SAMPLE_SML.channels = [{'objName': '1.8.0*255', 'value': 10000, 'unit': 'kWh'}]

SAMPLE_PLAIN = Sample()
SAMPLE_PLAIN.meter_id = 888777666
SAMPLE_PLAIN.channels = [{'objName': '6.8', 'value': 20000, 'unit': 'kWh'}]


class MockedGateway(BaseGateway):
    def post(self, uuid: str, value, timestamp):
        return True

    def get(self, uuid):
        return None


class MockedReader():
    def __init__(self, sample):
        self.sample = sample
        self.meter_id = None

    def poll(self):
        return self.sample


class TestMeterReader(unittest.TestCase):
    @mock.patch("pymeterreader.meter_reader.VolkszaehlerGateway", return_value=MockedGateway('http://192.168.1.1/', True))
    @mock.patch("pymeterreader.meter_reader.SmlReader", return_value=MockedReader(SAMPLE_SML))
    @mock.patch("pymeterreader.meter_reader.PlainReader",  return_value=MockedReader(SAMPLE_PLAIN))
    @mock.patch("pymeterreader.meter_reader.Bme280Reader",  return_value=MockedReader(SAMPLE_BME))
    def test_meter_reader(self, mock_bme, mock_plain, mock_sml, mock_gw):
        meter_reader_nodes = map_configuration(EXAMPLE_CONF)
        self.assertEqual(3, len(meter_reader_nodes))


if __name__ == '__main__':
    unittest.main()
