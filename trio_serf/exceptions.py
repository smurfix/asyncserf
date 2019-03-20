class SerfError(Exception):
    """
    Generic class for errors returned by Serf.
    """

    pass


class SerfConnectionError(SerfError):
    """
    Exception raised when there's no Serf there.
    """

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port

    def __str__(self):
        return "Error connecting to %s:%s" % (self.host, self.port)


class SerfClosedError(SerfError):
    """
    Exception raised when Serf has closed the connection.
    """

    pass
