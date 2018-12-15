class SerfError(Exception):
    pass


class SerfConnectionError(SerfError):
    def __init__(self, host, port):
        self.host = host
        self.port = port
    def __str__(self):
        return "Error connecting to %s:%s" % (self.host, self.port)


class SerfClosedError(SerfError):
    pass
