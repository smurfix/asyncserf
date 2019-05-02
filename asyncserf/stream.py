# Streaming frontend

import logging

logger = logging.getLogger(__name__)


class SerfStream:
    """
    An object of this class is returned by :meth:`asyncserf.Serf.stream`.
    It represents the message stream that's returned by a query which
    returns more than one reply.

    All you should do with this object is iterate over it with an async
    context::

        async with client.stream(...) as stream:
            assert isinstance(stream, SerfStream)
            async for reply in stream:
                assert isinstance(reply, SerfEvent)
                pass

    Note that the actual query is not started until you enter the context.
    """

    _it = None
    _ctx = None

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
            res._set(r.body, self.client.codec)  # pylint: disable=protected-access
            return res

    @property
    def head(self):
        return self._ctx.head

    @property
    def body(self):
        return self._ctx.body

    def cancel(self):
        """Tell the server to cancel the query, if possible."""
        if self._it is not None:
            self._it.cancel()


class SerfQuery(SerfStream):
    """
    An object of this class is returned by :meth:`asyncserf.Serf.query`.

    All you should do with this object is iterate over it with an async
    context::

        async with client.query(...) as query:
            assert isinstance(query, SerfQuery)
            async for reply in query:
                assert isinstance(reply, SerfEvent)
                pass

    This is a derivative class of :class:`SerfStream`.

    Cancelling a ``SerfQuery`` has no effect – the query only terminates
    when its timeout expires.

    """

    def __init__(self, client, stream):
        super().__init__(client, stream)
        self.stream.send_stop = False

    async def __anext__(self):
        """
        Auto-close the iterator when Serf says a query is done.
        """
        res = await super().__anext__()
        if res.type == "done":
            try:
                # pylint: disable=protected-access
                del self.client._conn._handlers[self.stream.seq]
            except AttributeError:
                # either the connection or the handlers is `None`, thus
                # the connectionis closed, which we don't care about.
                # No, we don't catch KeyError here. That should not happen.
                pass
            raise StopAsyncIteration
        return res


class SerfEvent:
    """
    Encapsulates one event returned by a :class:`SerfStream` or :class:`SerfQuery`.

    The event's data are represented by (lower-cased) attributes of this object.

    The payload (if any) will have been decoded by the client's codec.
    Non-decodable payloads trigger a fatal error. To avoid that, use the
    :class:`asyncserf.codec.NoopCodec` codec and decode manually.
    """

    id = None
    payload = None

    def __init__(self, client):
        self.client = client

    async def respond(self, payload=None):
        """
        This method only works for "query" requests, as returned by
        iterating over a :class:`SerfStream`.

        Args:
          ``payload``: the payload, as accepted by the client codec's encoder.
        """
        if self.id is None:
            raise RuntimeError("This is not in reply to a query")
        await self.client.respond(self.id, payload)

    def _set(self, body, codec):
        logger.debug("Set %s with %s", self, body)
        for k, v in body.items():
            k = k.decode("UTF-8")
            if v is not None:
                if k == "Payload":
                    v = codec.decode(v)
                elif isinstance(v, bytes):
                    v = v.decode("utf-8")
            setattr(self, k.lower(), v)
        logger.debug("Set result %s", self)

    def __repr__(self):
        return "<%s: %s>" % (
            self.__class__.__name__,
            ",".join(
                "%s:%s" % (str(k), repr(v))
                for k, v in vars(self).items()
                if not k.startswith("_")
            ),
        )
