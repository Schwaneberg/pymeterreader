from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelDescription:
    """
    Data storage object to describe a channel
    """
    uuid: str
    title: str
    type: str = ""
    description: str = ""
