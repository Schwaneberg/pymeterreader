"""
Detect and present meters.
"""
import typing as tp
from pymeterreader.device_lib import SmlReader, PlainReader, Bme280Reader, Device


def detect() -> tp.List[Device]:
    """
    Calls all detectors and returns a list of available devices.
    """
    devices = []
    SmlReader.detect(devices)
    PlainReader.detect(devices)
    Bme280Reader.detect(devices)
    return devices
