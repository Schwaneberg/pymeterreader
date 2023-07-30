"""
Implementing a MQTT client
"""
import json
import sys
from datetime import datetime
import logging
from typing import Optional, List, Union, Tuple, Dict
import paho.mqtt.client as mqtt
from paho.mqtt.publish import single

from pymeterreader.core.channel_description import ChannelDescription
from pymeterreader.core.channel_upload_info import ChannelUploadInfo
from pymeterreader.gateway.basegateway import BaseGateway

logger = logging.getLogger(__name__)
if sys.version_info.minor >= 8:
    from typing import Literal
    t_protocol = Literal["3.1", "3.1.1", "5.0"]
    t_transport = Literal["tcp", "websocket"]
else:
    t_protocol = str
    t_transport = None


class MQTTGateway(BaseGateway):
    """
    This Gateway acts an an MQTT client
    """
    def __init__(self, middleware_url: str, user: Optional[str] = None, password: Optional[str] = None,
                 certfile: Optional[str] = None, keyfile: Optional[str] = None, insecure: Optional[bool] = False,
                 ciphers: Optional[str] = None, ca_ceerts: Optional[str] = None, protocol_version: t_protocol = "3.1.1",
                 transport: t_transport = "tcp", port: int = 1883, **kwargs):
        """
        :param middleware_url: IP or host name of the MQTT router
        :param user: user name for the MQTT client connection
        :param password: optional password for authentication
        :param ca_ceerts: a string path to the Certificate Authority certificate files that are to be treated as trusted
        :param certfile: path to the certificate file
        :param keyfile: Optional key file path
        :param insecure: Disable certificate validation
        :param protocol_version: MQTT version 3.1, 3.1.1 or 5.0 (default "3.1.1")
        :param transport: Transport via "websockets" or "tcp" (default "tcp")
        :param port: MQTT Broker port (default 1883)
        """
        # pylint: disable=too-many-arguments,too-many-arguments
        super().__init__(**kwargs)
        if protocol_version == "3.1.1":
            self.protocol = mqtt.MQTTv311
        elif protocol_version == "3.1":
            self.protocol = mqtt.MQTTv311
        elif protocol_version == "5.0":
            self.protocol = mqtt.MQTTv5
        else:
            raise NotImplementedError(f"MQTT protocol version {protocol_version} is not supported")
        self.url = middleware_url
        self.auth = {'username': user, 'password': password}
        self.tls = {'ca_certs': ca_ceerts, 'certfile': certfile,
                    'keyfile': keyfile, 'tls_version': None,
                    'ciphers': ciphers, 'insecure': insecure} if ca_ceerts or certfile or keyfile else None
        self.certfile = certfile
        self.keyfile = keyfile
        self.transport = transport
        self.port = port
        self.post_timestamps: Dict[str, Tuple[datetime, Union[int, float]]] = {}

    def post(self, channel: ChannelUploadInfo, value: Union[int, float], sample_timestamp: datetime,
             poll_timestamp: datetime) -> bool:
        try:
            payload = json.dumps({
                "state": channel.factor * value,
                "dev_cla": channel.device_class,
                "unit_of_meas": channel.unit_of_measurement
            })
            logger.debug(f"MQTT Payload: {payload}")
            single(channel.uuid, payload=payload, qos=0, retain=True, hostname=self.url,
                   port=self.port, client_id="", keepalive=60, auth=self.auth, tls=self.tls,
                   protocol=self.protocol, transport=self.transport)
            self.post_timestamps[channel.uuid] = sample_timestamp, value
        except Exception as err:
            logger.error(err)
            return False
        return True

    def get_upload_info(self, channel_info: ChannelUploadInfo) -> Optional[ChannelUploadInfo]:
        timestamp, value = self.post_timestamps.get(channel_info.uuid, (None, None))
        if timestamp is not None and value is not None:
            return ChannelUploadInfo(channel_info.uuid, channel_info.interval, channel_info.factor, timestamp, value)
        return None

    def get_channels(self) -> List[ChannelDescription]:
        return []
