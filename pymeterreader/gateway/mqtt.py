"""
Implementing a MQTT client
"""
from datetime import datetime
import logging
from typing import Optional, Literal, Union, List
import ssl
import paho.mqtt.client as mqtt

from pymeterreader.core import ChannelUploadInfo, ChannelDescription
from pymeterreader.gateway import BaseGateway

logger = logging.getLogger(__name__)


class MQTTGateway(BaseGateway):
    """
    This Gateway acts an an MQTT client
    """
    def __init__(self, middleware_url: str,
                 user: Optional[str] = None, password: Optional[str] = None,
                 certfile: Optional[str] = None, keyfile: Optional[str] = None,
                 protocol_version: Literal["3.1", "3.1.1", "5.0"] = "3.1.1",
                 transport: Literal["tcp", "websocket"] = "tcp"):
        if protocol_version == "3.1.1":
            protocol = mqtt.MQTTv311
        elif protocol_version == "3.1":
            protocol = mqtt.MQTTv311
        elif protocol_version == "5.0":
            protocol = mqtt.MQTTv5
        else:
            raise NotImplementedError(f"MQTT protocol version {protocol_version} is not supported")

        self.client = mqtt.Client(client_id="PyMeterReader",
                                  transport=transport,
                                  protocol=protocol)
        if user is not None and password is not None:
            self.client.username_pw_set(user, password)
        self.client.tls_set(certfile=certfile,
                            keyfile=keyfile,
                            cert_reqs=ssl.CERT_REQUIRED)

    def post(self, channel: ChannelUploadInfo, value: Union[int, float], sample_timestamp: datetime,
             poll_timestamp: datetime) -> bool:
        ...

    def get_upload_info(self, channel_info: ChannelUploadInfo) -> Optional[ChannelUploadInfo]:
        ...

    def get_channels(self) -> List[ChannelDescription]:
        return []

    def mqtt_on_message(self, client, userdata, message):
        logger.info(f"MQTT Message: '{message}' on topic '{message.topic}' with QoS '{message.qos}'")
