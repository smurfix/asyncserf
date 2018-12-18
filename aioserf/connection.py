import socket
import msgpack
import resource
from async_generator import asynccontextmanager
import anyio
from anyio.exceptions import ClosedResourceError
import outcome

from .result import SerfResult
from .util import ValueEvent
from .exceptions import SerfError, SerfConnectionError, SerfClosedError

from logging import getLogger
logger = getLogger(__name__)

_conn_id = 0


class _StreamReply:
    """
    This class represents a multi-message reply.

    Actually, it also represents the query itself, which is not started
    until you enter the stream's context.

    This is an internal class. See :meth:`AioSerf.stream` for details.
    """
    _running = False
    send_stop = True

    def __init__(self, conn, command, params, seq, expect_body):
        self._conn = conn
        self._command = command
        self._params = params
        self.seq = seq
        self.q = anyio.create_queue(10000)
        self.expect_body = -expect_body

    async def set(self, value):
        await self.q.put(outcome.Value(value))

    async def set_error(self, err):
        await self.q.put(outcome.Error(err))

    async def get(self):
        res = await self.q.get()
        if res is not None:
            res = res.unwrap()
        return res

    def __aiter__(self):
        if not self._running:
            pass  # raise RuntimeError("You need to wrap this in an 'async with'")
        return self

    async def __anext__(self):
        if not self._running:
            raise StopAsyncIteration
        res = await self.q.get()
        if res is None:
            raise StopAsyncIteration
        return res.unwrap()

    async def __aenter__(self):
        reply = await self._conn._call(self._command, self._params, _reply=self)
        res = await reply.get()
        if res is not None:
            self.head = res.head
            self._running = True
        return self

    async def __aexit__(self, *exc):
        self._running = False
        hdl = self._conn._handlers
        if self.send_stop:
            async with anyio.open_cancel_scope(shield=True):
                await self._conn.call("stop", params={b'Stop': self.seq}, expect_body=False)
                if hdl is not None:
                    # TODO remember this for a while?
                    del hdl[self.seq]

    async def cancel(self):
        await self.q.put(None)


class SerfConnection(object):
    """
    Manages RPC communication to and from a Serf agent.

    This is an internal class; see :class:`aioserf.AioSerf` for methods
    you're supposed to call. ;-)
    """

    # Read from the RPC socket in blocks of this many bytes.
    # (Typically 4k)
    _socket_recv_size = resource.getpagesize()
    _conn_id = 0

    def __init__(self, tg, host='localhost', port=7373):
        global _conn_id
        _conn_id += 1
        self._conn_id = _conn_id
        self.tg = tg
        self.host = host
        self.port = port
        self._socket = None
        self._seq = 0
        self._handlers = {}

    # handler protocol: incoming messages are passed in using `.set`.
    # If .expect_body is True then the reader will add a body to the
    # request. If it's -1 then the first reply is the body-less OK (we
    # hope) and only subsequent replies will have a body.

    def __repr__(self):
        return "<%(class)s counter=%(c)s host=%(h)s port=%(p)s>" \
            % {'class': self.__class__.__name__,
               'c': self._seq,
               'h': self.host,
               'p': self.port}

    def stream(self, command, params=None, expect_body=True):
        """
        Sends the provided command to Serf for evaluation, with
        any parameters as the message body. Expect a streamed reply.

        Returns a ``_StreamReply`` object which affords an async context
        manager plus async iterator, which will return replies.
        """
        return _StreamReply(self, command, params, self._counter, expect_body)

    async def _call(self, command, params=None, expect_body=True, *, _reply=None):
        """
        Sends the provided command to Serf for evaluation, with
        any parameters as the message body.

        Returns the reply object. If the connection is being torn down and
        no reply is explected, return ``None``.
        """

        class SingleReply(ValueEvent):
            """
            A helper class, used to process a single reply.
            """

            def __init__(slf, seq, expect_body):
                super().__init__()
                slf.seq = seq
                slf.expect_body = expect_body

            async def set(slf, val):
                if self._handlers is not None:
                    del self._handlers[slf.seq]
                await super().set(val)

            async def set_error(slf, err):
                if self._handlers is not None:
                    del self._handlers[slf.seq]
                await super().set_error(err)

        if self._socket is None:
            return

        if _reply is None:
            seq = self._counter
            _reply = SingleReply(seq, expect_body)
        else:
            seq = _reply.seq
        if self._handlers is not None:
            self._handlers[seq] = _reply
        else:
            _reply = None

        if params:
            logger.debug("%d:Send %s:%s =%s", self._conn_id, seq, command, repr(params))
        else:
            logger.debug("%d:Send %s:%s", self._conn_id, seq, command)
        msg = msgpack.packb({"Seq": seq, "Command": command})
        if params is not None:
            msg += msgpack.packb(params)

        await self._socket.send_all(msg)

        return _reply

    async def call(self, command, params=None, expect_body=True):
        """
        Fire a single-reply command, wait for the reply (and return it).
        """

        res = await self._call(command, params, expect_body=expect_body)
        if res is None:
            return res
        return await res.get()

    async def _handle_msg(self, msg):
        """Handle an incoming message.

        Return True if the message is incomplete, i.e. the reader should
        wait for a body, attach it to the message, and then call this
        method again.
        """
        if self._handlers is None:
            logger.warn("Message without handlers:%s", msg)
            return
        try:
            seq = msg.head[b'Seq']
        except KeyError:
            raise RuntimeError("Reader got out of sync: " + str(msg))
        try:
            hdl = self._handlers[seq]
        except KeyError:
            logger.warn("Spurious message %s: %s", seq, msg)
            return

        if msg.body is None and hdl.expect_body > 0 and (hdl.expect_body > 1
                                                         or not msg.head[b'Error']):
            return True
        # Do this here because stream replies might arrive immediately
        # i.e. before the queue listener gets around to us
        if hdl.expect_body < 0:
            hdl.expect_body = -hdl.expect_body
        if msg.head[b'Error']:
            await hdl.set_error(SerfError(msg))
            await anyio.sleep(0.01)
        else:
            await hdl.set(msg)
        return False

    async def _reader(self, scope):
        """Main loop for reading

        TODO: add a timeout for receiving message bodies.
        """
        unpacker = msgpack.Unpacker(object_hook=self._decode_addr_key)
        cur_msg = None

        async with anyio.open_cancel_scope(shield=True) as s:
            await scope.set(s)

            try:
                while self._socket is not None:
                    if cur_msg is not None:
                        logger.debug("%d:wait for body", self._conn_id)
                    try:
                        buf = await self._socket.receive_some(self._socket_recv_size)
                    except ClosedResourceError:
                        return  # closed by us
                    if len(buf) == 0:  # Connection was closed.
                        raise SerfClosedError("Connection closed by peer")
                    unpacker.feed(buf)

                    for msg in unpacker:
                        if cur_msg is not None:
                            logger.debug("%d  Body=%s", self._conn_id, msg)
                            cur_msg.body = msg
                            await self._handle_msg(cur_msg)
                            cur_msg = None
                        else:
                            logger.debug("%d:Recv =%s", self._conn_id, msg)
                            msg = SerfResult(msg)
                            if await self._handle_msg(msg):
                                cur_msg = msg
            finally:
                hdl, self._handlers = self._handlers, None
                async with anyio.open_cancel_scope(shield=True):
                    for m in hdl.values():
                        await m.cancel()

    async def handshake(self):
        """
        Sets up the connection with the Serf agent and does the
        initial handshake.
        """
        return await self.call('handshake', {"Version": 1}, expect_body=False)

    async def auth(self, auth_key):
        """
        Performs the initial authentication on connect
        """
        return await self.call('auth', {"AuthKey": auth_key}, expect_body=False)

    @asynccontextmanager
    async def _connected(self):
        """
        This async context manager handles the actual TCP connection to
        the Serf process.
        """
        reader = ValueEvent()
        try:
            async with await anyio.connect_tcp(self.host, self.port) as sock:
                self._socket = sock
                await self.tg.spawn(self._reader, reader)
                reader = await reader.get()
                yield self
        except socket.error as e:
            raise SerfConnectionError(self.host, self.port) from e
        finally:
            if self._socket is not None:
                await self._socket.close()
                self._socket = None
            if reader is not None:
                await reader.cancel()
                reader = None

    @property
    def _counter(self):
        """
        Returns the current value of our message sequence counter and increments it.
        """
        current = self._seq
        self._seq += 1
        return current

    def _decode_addr_key(self, obj_dict):
        """
        Callback function to handle the decoding of the 'Addr' field.

        Serf msgpack 'Addr' as an IPv6 address, and the data needs to be
        unpacked using socket.inet_ntop().

        :param obj_dict: A dictionary containing the msgpack map.
        :return: A dictionary with the correct 'Addr' format.
        """
        key = b'Addr'
        ip_addr = obj_dict.get(key, None)
        if ip_addr is not None:
            if len(ip_addr) == 4:  # IPv4
                ip_addr = socket.inet_ntop(socket.AF_INET, obj_dict[key])
            else:
                ip_addr = socket.inet_ntop(socket.AF_INET6, obj_dict[key])

                # Check if the address is an IPv4 mapped IPv6 address:
                # ie. ::ffff:xxx.xxx.xxx.xxx
                if ip_addr.startswith('::ffff:'):
                    ip_addr = ip_addr[7:]

            # The msgpack codec is set to raw,
            # thus everything needs to be bytes
            obj_dict[key] = ip_addr.encode('utf-8')

        return obj_dict
