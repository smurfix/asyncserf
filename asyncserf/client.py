#
# async serf client
# (c) 2018 Matthias Urlichs

import anyio

try:
    from contextlib import asynccontextmanager
except ImportError:
    from async_generator import asynccontextmanager

from .codec import NoopCodec
from .connection import SerfConnection
from .stream import SerfQuery, SerfStream
from .util import ValueEvent


@asynccontextmanager
async def serf_client(**kw):
    """
    Async context manager for connecting to Serf.

    Arguments: see :class:`asyncserf`, except for the task group ``tg``
    which ``serf_client`` creates and manages for you.

    This is an async context manager.
    """
    async with anyio.create_task_group() as tg:
        client = Serf(tg, **kw)
        async with client._connected():  # noqa:E501 pylint:disable=not-async-context-manager,protected-access
            yield client
            await tg.cancel_scope.cancel()


class Serf:
    """
    The main adapter.

    Args:
      ``tg``: the task group to use.
      ``host``: the host to connect to. Defaults to "localhost".
      ``port``: the TCP port to connect to. Defaults to 7373 (serf).
      ``rpc_auth``: authorizatioon information.
      ``codec``: Codec for the payload. Defaults to no-op,
                 i.e. the payload must consist of bytes.

    Do not instantiate this object directly; insread, use::

        async with serf_client(**args) as client:
            pass  # work with 'client'
    """

    _conn = None

    def __init__(
        self, tg, host="localhost", port=7373, rpc_auth=None, codec=None
    ):  # pylint: disable=too-many-arguments
        self.tg = tg
        self.host = host
        self.port = port
        self.rpc_auth = rpc_auth
        if codec is None:
            codec = NoopCodec()
        self.codec = codec

    @asynccontextmanager
    async def _connected(self):
        """
        Helper to manage the underlying connection.

        This is an async context manager.
        """
        self._conn = SerfConnection(self.tg, host=self.host, port=self.port)
        try:
            # pylint: disable=protected-access
            async with self._conn._connected():  # pylint: disable=not-async-context-manager
                await self._conn.handshake()
                if self.rpc_auth:
                    await self._conn.auth(self.rpc_auth)
                yield self
        finally:
            try:
                if self._conn is not None:
                    await self._conn.call("leave")
            finally:
                self._conn = None

    async def spawn(self, proc, *args, **kw):
        """
        Run a task within this object's task group.

        Returns:
          a cancel scope you can use to stop the task.
        """

        async def _run(proc, args, kw, result):
            """
            Helper for starting a task.

            This accepts a :class:`ValueEvent`, to pass the task's cancel scope
            back to the caller.
            """
            async with anyio.open_cancel_scope() as scope:
                if result is not None:
                    await result.set(scope)
                await proc(*args, **kw)

        res = ValueEvent()
        await self.tg.spawn(_run, proc, args, kw, res)
        return await res.get()

    async def cancel(self):
        """
        Cancel our internal task group. This should cleanly shut down
        everything.
        """
        await self.tg.cancel_scope.cancel()

    def stream(self, event_types="*"):
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
            event_types = ",".join(event_types)
        res = self._conn.stream("stream", {"Type": event_types})
        return SerfStream(self, res)

    def query(
        self, name, payload=None, *, nodes=None, tags=None, request_ack=False, timeout=0
    ):
        """
        Send a query.

        Args:
          ``name``: The query name. Mandatory.
          ``payload``: Your payload. Will be passed through this client's
                       codec.
          ``nodes``: The list of nodes to pass this query to. Default: no
                     restriction
          ``tags``: A dict of tags used to filter nodes. Values are regexps
                    which a node's corresponding tag value must match.
          ``request_ack``: A flag whether the query result shall include
                           messages that a Serf node matches the request.
                           The default is ``False``.
          ``timeout``: Time (in seconds) after which the query will be
                       concluded.
        Returns:
          a :class:`asyncserf.stream.SerfQuery` object.

        Note that the query will not be started until you enter its
        context. You should then iterate over the results::

            async with client.query("example") as stream:
                async for response in stream:
                    if response.type == "ack":
                        print("Response arrived at %s" % (response.from,))
                    elif response.type == "response":
                        print("Node %s answered %s" %
                                (response.from,
                                 repr(response.payload)))

        """
        params = {"Name": name, "RequestAck": request_ack}
        if payload is not None:
            params["Payload"] = self.codec.encode(payload)
        if nodes:
            params["FilterNodes"] = list(nodes)
        if tags:
            params["FilterTags"] = dict(tags)
        if timeout:
            params["Timeout"] = int(timeout * 10 ** 9)

        res = self._conn.stream("query", params)
        return SerfQuery(self, res)

    def monitor(self, log_level="info"):
        """
        Ask the server to stream (some of) its log entries to you.

        :Args:
          ``log_level``: The debug level.
                         Possible values are "trace", "debug", "info", "warn",
                         and "err". The default is "info".
        """
        res = self._conn.stream("monitor", {"LogLevel": log_level})
        return SerfStream(self, res)

    def respond(self, seq, payload):
        """
        Respond to a query.

        You should probably call this via :class:`asyncserf.stream.SerfEvent`.
        """
        if seq is None:
            raise RuntimeError("You cannot respond to this message.")
        if payload is not None:
            payload = self.codec.encode(payload)
        return self._conn.call(
            "respond", {"ID": seq, "Payload": payload}, expect_body=False
        )

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
            "event",
            {"Name": name, "Payload": payload, "Coalesce": coalesce},
            expect_body=False,
        )

    def members(self, name=None, status=None, tags=None):
        """
        Lists members of a Serf cluster, optionally filtered by one or more
        filters:

        Args:
          ``name``: a string with a regex that matches on node names.
          ``status``: a string with a regex matching on node status.
          ``tags``: a dict of tags used to filter nodes. Values are regexps
                    which a node's corresponding tag value must match.

        All arguments must match for a node to be returned.
        """
        filters = {}

        if name is not None:
            filters["Name"] = name

        if status is not None:
            filters["Status"] = status

        if tags is not None:
            filters["Tags"] = tags

        if len(filters) == 0:
            return self._conn.call("members")
        else:
            return self._conn.call("members-filtered", filters)

    def tags(self, **tags):
        """Set this node's tags.

        Keyword arguments are used to name tags to be set or deleted.

        You can delete a tag by passing ``None`` as its value.

        Tags that are not mentioned are not changed.
        """
        deleted = []
        for k, v in list(tags.items()):
            if v is None:
                del tags[k]
                deleted.append(k)
        tags = {"Tags": tags}
        if deleted:
            tags["DeleteTags"] = deleted
        return self._conn.call("tags", tags)

    def leave(self):
        """
        Terminate the Serf instance you're connected to.

        This will ultimately shut down the connection, probably with an
        error.
        """
        return self._conn.call("leave", expect_body=False)

    def force_leave(self, name):
        """
        Force a node to leave the cluster.

        Args:
          ``name``: the name of the node that should leave.
        """
        return self._conn.call("force-leave", {"Node": name}, expect_body=False)

    def install_key(self, key):
        """
        Install a new encryption key onto the cluster's keyring.

        Args:
          ``key``: the new 16-byte key, base64-encoded.
        """
        return self._conn.call("install-key", {"Key": key}, expect_body=True)

    def use_key(self, key):
        """
        Change the cluster's primary encryption key.

        Args:
          ``key``: an existing 16-byte key, base64-encoded.
        """
        return self._conn.call("use-key", {"Key": key}, expect_body=True)

    def remove_key(self, key):
        """
        Remove an encryption key from the cluster.

        Args:
          ``key``: the obsolete 16-byte key, base64-encoded.
        """
        return self._conn.call("remove-key", {"Key": key}, expect_body=True)

    def list_keys(self):
        """
        Return a list of all encryption keys.

        """
        return self._conn.call("list-keys", expect_body=True)

    def join(self, location, replay=False):
        """
        Ask Serf to join a cluster, by providing a list of possible
        ip:port locations.

        Args:
          ``location``: A list of addresses.
          ``replay``: a flag indicating whether to replay old user events
                      to new nodes; defaults to ``False``.

        """
        if not isinstance(location, (list, tuple)):
            location = [location]
        return self._conn.call(
            "join", {"Existing": location, "Replay": replay}, expect_body=2
        )

    def get_coordinate(self, node):
        """
        Return the network coordinate of a given node.

        Args:
          ``node``: The node to request

        """
        return self._conn.call(" get-coordinate", {"Node": node}, expect_body=True)

    def stats(self):
        """
        Obtain operator debugging information about the running Serf agent.
        """
        return self._conn.call("stats")
