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
    devices.extend(SmlReader.detect())
    devices.extend(PlainReader.detect())
    devices.extend(Bme280Reader.detect())
    return devices
