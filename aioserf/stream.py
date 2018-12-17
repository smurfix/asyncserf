# Streaming frontend

class SerfStream:
    """
    Represents the data stream from a call to ``client.stream()``.
    """
    _it = None

    def __init__(self, client, stream):
        self.client = client
        self.stream = stream

    async def __aenter__(self):
        self._ctx = await self.stream.__aenter__()
        return self

    async def __aexit__(self, *tb):
        await self._ctx.__aexit__(*tb)
        self._ctx = None

    def __aiter__(self):
        self._it = self._ctx.__aiter__()
        return self

    async def __anext__(self):
        try:
            r = await self._it.__anext__()
        except StopAsyncIteration:
            self._it = None
            raise
        else:
            res = SerfEvent(self.client)
            for k,v in r.body.items():
                k = k.decode('UTF-8')
                if v is not None:
                    if k == "Payload":
                        v = self.client.codec.decode(v)
                    elif isinstance(v, bytes):
                        v = v.decode("utf-8")
                setattr(res, k.lower(), v)
            return res

    @property
    def head(self):
        return self._ctx.head
    @property
    def body(self):
        return self._ctx.body

    def cancel(self):
        if self._it is not None:
            return self._it.cancel()


class SerfQuery(SerfStream):
    def __init__(self, client, stream):
        super().__init__(client, stream)
        self.stream.send_stop = False

    async def __anext__(self):
        res = await super().__anext__()
        if res.type == "done":
            try:
                del self.client._conn._handlers[self.stream.seq]
            except AttributeError:
                pass
            raise StopAsyncIteration
        return res


class SerfEvent:
    """
    Encapsulates one event on a SerfStream.
    """
    id = None
    payload = None

    def __init__(self, client):
        self.client = client

    async def respond(self, payload):
        await self.client.respond(self.id, payload)
        if payload is not None:
            payload = self.client.codec.encode(payload)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, ",".join("%s:%s" %(str(k),repr(v)) for k,v in vars(self).items() if not k.startswith('_')))

