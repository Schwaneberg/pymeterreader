"""
Commmon code for all readers
"""
from time import time
from string import digits, ascii_letters, punctuation
legal_characters = digits + ascii_letters + punctuation


class Sample:
    """
    Data storage object to represent a readout
    """

    def __init__(self):
        self.time = time()
        self.meter_id = None
        self.channels = []


def strip(string: str) -> str:
    """
    Strip irrelevant characters from identifiaction
    :rtype: object
    :param string: original string
    :return: stripped string
    """
    return ''.join([char for char in string if char in legal_characters]).strip().upper()
