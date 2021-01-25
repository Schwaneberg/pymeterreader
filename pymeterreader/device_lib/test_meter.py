import typing as tp
from abc import abstractmethod
from dataclasses import dataclass
from threading import Thread
from time import sleep

import serial

from pymeterreader.device_lib.common import ChannelValue


@dataclass(frozen=True)
class TestData:
    meter_id: str
    channels: tp.List[ChannelValue]


@dataclass(frozen=True)
class SerialTestData(TestData):
    binary: bytes


class MeterSimulator(Thread):
    """
    Simulate Meter that sends a measurement
    """

    def __init__(self, sleep_interval: float) -> None:
        self.__continue = True
        self.sleep_interval = sleep_interval
        # Open the shared serial instance using the mocked serial.serial_for_url function
        self.tty = serial.serial_for_url("loop://")
        super().__init__()

    def run(self) -> None:
        # Store whether we need to write a response. This needs to be cached to
        write_pending = False
        # Try to write continuously
        while self.__continue:
            try:
                # Wait for the wakeup sequence if we have not already received a wakeup sequence but failed sending it.
                if not write_pending:
                    write_pending = self.wait_for_wakeup()
                if write_pending:
                    # Write bytes
                    self.tty.write(self.get_sample_bytes())
                    # Reset Write pending status
                    write_pending = False
            # Keep trying even when the serial port has not been opened or has already been closed by the reader
            except serial.PortNotOpenError:
                pass
            # Send next measurement after sleep interval. Time drift depends on this functions runtime
            sleep(self.sleep_interval)

    def stop(self) -> None:
        self.__continue = False

    def wait_for_wakeup(self) -> bool:
        """
        This method blocks until the wakeup sequence is received or an error occurs.
        The wakeup procedure was correctly executed if True is returned.
        The default implementation returns immediately.
        """
        return True

    @abstractmethod
    def get_sample_bytes(self) -> bytes:
        raise NotImplementedError("This is just an abstract class.")

    @abstractmethod
    def get_meter_id(self) -> str:
        raise NotImplementedError("This is just an abstract class.")

    @abstractmethod
    def get_channels(self) -> tp.List[ChannelValue]:
        raise NotImplementedError("This is just an abstract class.")


class StaticMeterSimulator(MeterSimulator):
    def __init__(self, test_data: SerialTestData, sleep_interval: float = 0.5) -> None:
        super().__init__(sleep_interval)
        self.__test_data = test_data

    def get_sample_bytes(self) -> bytes:
        return self.__test_data.binary

    def get_meter_id(self) -> str:
        return self.__test_data.meter_id

    def get_channels(self) -> tp.List[ChannelValue]:
        return self.__test_data.channels
