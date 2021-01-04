class ChannelInfo:
    def __init__(self, uuid, interval, factor, last_upload, last_value):
        """
        Channel info structure
        :param uuid: uuid of db entry to feed
        :param interval: interval between readings in seconds
        :param factor: multiply to original values, e.g. to conver kWh to Wh
        :param last_upload: time of last upload to middleware
        :param last_value: last value in middleware
        """
        # pylint: disable=too-many-arguments
        self.uuid = uuid
        self.interval = interval
        self.factor = factor
        self.last_upload = last_upload
        self.last_value = last_value
