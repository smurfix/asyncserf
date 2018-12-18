#
# async serf client
# (c) 2018 Matthias Urlichs

import anyio
from .connection import SerfConnection
from .stream import SerfStream, SerfQuery
from .codec import NoopCodec
from .util import ValueEvent
from async_generator import asynccontextmanager

@asynccontextmanager
async def serf_client(**kw):

    async with anyio.create_task_group() as tg:
        client = AioSerf(tg, **kw)
        async with client._connected():
            yield client

class AioSerf(object):
    """
    The main adapter.

    Args:
      ``tg``: the task group to use. Typically passed in by
              :func:`serf_client`.

    """
    def __init__(self, tg, host='localhost', port=7373, rpc_auth=None,
            codec=None):
        self.tg = tg
        self.host = host
        self.port = port
        self.rpc_auth = rpc_auth
        if codec is None:
            codec = NoopCodec()
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

    async def _spawn(self, val, proc, args, kw):
        async with anyio.open_cancel_scope() as scope:
            await val.set(scope)
            await proc(*args, **kw)

    async def spawn(self, proc, *args, **kw):
        """
        Run a task within this object's task group.

        Returns:
          a cancel scope you can use to stop the task.
        """
        val = ValueEvent()
        await self.tg.spawn(self._spawn, val, proc, args, kw)
        return await val.get()

    async def cancel(self):
        """
        Cancel our internal task group. This should cleanly shut down
        everything.
        """
        await self.tg.cancel_scope.cancel()

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
            params['Timeout'] = int(timeout * 10**9)

        res = self._conn.stream('query', params)
        return SerfQuery(self, res)

    def monitor(self, log_level='info'):
        """
        Ask the server to stream (some of) its log entries to you.

        :Args:
          ``log_level``: The debug level.
                         Possible values are "trace", "debug", "info", "warn",
                         and "err". The default is "info".
        """
        res = self._conn.stream('monitor', {'LogLevel': log_level})
        return SerfStream(self, res)

    def respond(self, seq, payload):
        """
        Respond to a query.

        You should probably call this via :class:`aioserf.stream.SerfEvent`.
        """
        if seq is None:
            raise RuntimeError("You cannot respond to this message.")
        if payload is not None:
            payload = self.codec.encode(payload)
        return self._conn.call("respond", {'ID': seq, 'Payload': payload}, expect_body=False)


    def event(self, name, payload=None, coalesce=True):
        """
        Send a user-specified event to the cluster. Can take an optional
        payload, which will be sent as translated by the client's codec.

        Args:
          ``name``: The name of the user event.
          ``payload``: The payload, as acceptable to the codec's ``encode`` method.
          ``coalesce``: A flag specifying whether multiple events with
                        the same name should be replaced by 
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

        Args:
          ``name``: a string with a regex that matches on node names.
          ``status``: a string with a regex matching on node status.
          ``tags``: a dict of tag names to regex values.

        All arguments must match for a node to be returned.
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

        Tags that are not mentioned are not changed. You can
        delete a tag by passing ``None`` as its value.

        All keyword arguments are used as tags to be set or deleted.
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

    def leave(name):
        """
        Terminate this Serf instance.

        This will ultmately shut down the connection, probably with an
        error.
        """
        return self._conn.call('leave', expect_body=False)

    def force_leave(self, name):
        """
        Force a node to leave the cluster.

        Args:
          ``name``: the name of the node that should leave.
        """
        return self._conn.call(
            'force-leave',
            {"Node": name}, expect_body=False)

    def install_key(self, key):
        """
        Install a new encryption key onto the cluster's keyring.

        Args:
          ``key``: the new 16-byte key, base64-encoded.
        """
        return self._conn.call(
            'install-key',
            {"Key": key}, expect_body=True)

    def use_key(self, key):
        """
        Change the cluster's primary encryption key.

        Args:
          ``key``: an existing 16-byte key, base64-encoded.
        """
        return self._conn.call(
            'use-key',
            {"Key": key}, expect_body=True)

    def remove_key(self, key):
        """
        Remove an encryption key from the cluster.

        Args:
          ``key``: the obsolete 16-byte key, base64-encoded.
        """
        return self._conn.call(
            'remove-key',
            {"Key": key}, expect_body=True)

    def list_keys(self):
        """
        Return a list of all encryption keys.

        """
        return self._conn.call('list-keys', expect_body=True)

    def join(self, location, replay=False):
        """
        Ask Serf to join a cluster, by providing a list of ip:port locations.

        Args:
          ``location``: A list of addresses.
          ``replay``: a flag indicating whether to replay old user events
                      to new nodes; defaults to ``False``.

        """
        if not isinstance(location, (list, tuple)):
            location = [location]
        return self._conn.call(
            'join',
            {"Existing": location, "Replay": replay}, expect_body=2)

    def get_coordinate(self, node):
        """
        Return the network coordinate of a given node.

        Args:
          ``node``: The node to request

        """
        return self._conn.call(
            ' get-coordinate',
            {"Node": node}, expect_body=True)

    def stats(self):
        """
        Obtain operator debugging information about the running Serf agent.
        """
        return self._conn.call('stats')

