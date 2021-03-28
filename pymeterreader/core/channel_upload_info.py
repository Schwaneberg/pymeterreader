import typing as tp
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass()
class ChannelUploadInfo:
    """
    Channel Upload info structure
    :param uuid: uuid of db entry to feed
    :param interval: interval between readings in seconds
    :param factor: multiply to original values, e.g. to conver kWh to Wh
    :param last_upload: time of last upload to middleware
    :param last_value: last value in middleware
    """
    uuid: str
    interval: timedelta
    factor: float
    last_upload: datetime
    last_value: tp.Union[int, float]
