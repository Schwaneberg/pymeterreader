"""
Detect and present meters.
"""
from pymeterreader.device_lib import SmlReader, PlainReader, Bme280Reader


def detect():
    """
    Calls all detectors and returns a list of available devices.
    """
    devices = []
    SmlReader.detect(devices)
    PlainReader.detect(devices)
    Bme280Reader.detect(devices)
    return devices
