#
# async serf client
# (c) 2018 Matthias Urlichs

import anyio
from .connection import SerfConnection
from .stream import SerfStream, SerfQuery
from .codec import MsgPackCodec
from async_generator import asynccontextmanager

@asynccontextmanager
async def serf_client(**kw):
    async with anyio.create_task_group() as tg:
        client = AioSerf(tg, **kw)
        async with client._connected():
            yield client

class AioSerf(object):
    def __init__(self, tg, host='localhost', port=7373, rpc_auth=None,
            codec=None):
        self.tg = tg
        self.host = host
        self.port = port
        self.rpc_auth = rpc_auth
        if codec is None:
            codec = MsgPackCodec()
        self.codec = codec

    @asynccontextmanager
    async def _connected(self):
        self._conn = SerfConnection(self.tg, host=self.host, port=self.port)
        try:
            async with self._conn._connected():
                await self._conn.handshake()
                if self.rpc_auth:
                    await self._conn.auth(self.rpc_auth)
                yield self
        finally:
            if self._conn is not None:
                await self._conn.call("leave")
            self._conn = None

    def stream(self, event_types='*'):
        """
        Open an event stream.

        Possible event types:

        * ``*`` -- all events
        * ``user`` -- all user events
        * ``user:TYPE`` -- all user events of type TYPE
        * ``query`` -- all queries
        * ``query:TYPE`` -- all queries of type TYPE
        * ``member-join``
        * ``member-leave``

        This method returns a SerfStream object which affords an async
        context manager plus async iterator, which will give you SerfEvent
        objects, which you can use to return a reply (if triggered by a
        "query" event).

        Replies have a "respond" method which you may use to send
        responses to queries.

        Example Usage::

            >>> async with client.stream("user") as stream:
            >>>     async for event in stream:
            >>>         msg = await dispatch(event.type)(event.payload)
            >>>         await event.respond(msg)

        though you might want to process messages in a task group::

            >>> async def in_tg(event):
            >>>     msg = await dispatch(event.type)(event.payload)
            >>>     await event.respond(msg)
            >>> async with anyio.create_task_group() as tg:
            >>>     async with client.stream("query") as stream:
            >>>         async for event in stream:
            >>>             await tg.spawn(in_tg, event)

        """
        if isinstance(event_types, list):
            event_types = ','.join(event_types)
        res = self._conn.stream('stream', {'Type': event_types})
        return SerfStream(self, res)

    def query(self, name, payload=None, *, nodes=None, tags=None,
            request_ack=False, timeout=0):
        """
        Send a query, expect a stream of replies.
        """
        params = {'Name': name, 'RequestAck': request_ack}
        if payload is not None:
            params['Payload'] = self.codec.encode(payload)
        if nodes:
            params['FilterNodes'] = list(nodes)
        if tags:
            params['FilterTags'] = dict(tags)
        if timeout:
            params['Timeout'] = timeout

        res = self._conn.stream('query', params)
        return SerfQuery(self, res)

    def monitor(self, log_level='DEBUG'):
        res = self._conn.stream('monitor', {'LogLevel': log_level})
        return SerfStream(self, res)

    def respond(self, seq, payload):
        if seq is None:
            raise RuntimeError("You cannot respond to this message.")
        if payload is not None:
            payload = self.codec.encode(payload)
        return self._conn.call("respond", {'ID': seq, 'Payload': payload}, expect_body=False)


    def event(self, name, payload=None, coalesce=True):
        """
        Send an event to the cluster. Can take an optional payload as well,
        which will be sent in the form that it's provided.
        """
        if payload is not None:
            payload = self.codec.encode(payload)
        return self._conn.call(
            'event',
            {'Name': name, 'Payload': payload, 'Coalesce': coalesce},
            expect_body=False)

    def members(self, name=None, status=None, tags=None):
        """
        Lists members of a Serf cluster, optionally filtered by one or more
        filters:

        `name` is a string, supporting regex matching on node names.
        `status` is a string, supporting regex matching on node status.
        `tags` is a dict of tag names and values, supporting regex matching
        on values.
        """
        filters = {}

        if name is not None:
            filters['Name'] = name

        if status is not None:
            filters['Status'] = status

        if tags is not None:
            filters['Tags'] = tags

        if len(filters) == 0:
            return self._conn.call('members')
        else:
            return self._conn.call('members-filtered', filters)

    def tags(self, **tags):
        """Set this node's tags.

        Delete tags by setting its value to None.
        """
        deleted = []
        for k,v in list(tags.items()):
            if v is None:
                del tags[k]
                deleted.append(k)
        tags = {'Tags': tags}
        if deleted:
            tags['DeleteTags'] = deleted
        return self._conn.call('tags', tags)

    def force_leave(self, name):
        """
        Force a node to leave the cluster.
        """
        return self._conn.call(
            'force-leave',
            {"Node": name}, expect_body=False)

    def join(self, location):
        """
        Join another cluster by provided a list of ip:port locations.
        """
        if not isinstance(location, (list, tuple)):
            location = [location]
        return self._conn.call(
            'join',
            {"Existing": location, "Replay": False}, expect_body=2)

    def stats(self):
        """
        Obtain operator debugging information about the running Serf agent.
        """
        return self._conn.call('stats')

