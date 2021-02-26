import typing as tp
from threading import Thread, Event
from time import sleep

from pymeterreader.core.meter_reader_node import MeterReaderNode


class MeterReaderTask(Thread):
    class Timer(Thread):
        """
        Precise event timer
        """
        def __init__(self, interval: tp.Union[int, float], event: Event):
            Thread.__init__(self)
            self.__interval = interval
            self.__event = event
            self.daemon = True
            self.__stop_event = Event()

        def run(self):
            while not self.__stop_event.is_set():
                sleep(self.__interval)
                self.__event.set()

        def stop(self):
            self.__stop_event.set()

    def __init__(self, meter_reader_node: MeterReaderNode):
        """
        Worker thread will call "poll and push" as often
        as required.
        :param meter_reader_node:
        """
        Thread.__init__(self)
        self.__meter_reader_mode = meter_reader_node
        self.__timer = Event()
        self.stop_event = Event()
        self.__timer_thread = self.Timer(self.__meter_reader_mode.poll_interval,
                                         self.__timer)
        self.daemon = True
        self.__timer_thread.start()
        super().start()

    def __block(self):
        self.__timer.wait()
        self.__timer.clear()
        return True

    def stop(self):
        """
        Call to stop the thread
        """
        self.stop_event.set()
        self.__timer.set()

    def run(self):
        """
        Start the worker thread.
        """
        self.__block()  # initial sample polled during initialization
        while not self.stop_event.is_set():
            self.__meter_reader_mode.poll_and_push()
            self.__block()
