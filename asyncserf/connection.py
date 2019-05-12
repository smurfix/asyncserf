import math
import resource
import socket
from logging import getLogger
import errno

import msgpack
import outcome
import anyio
from async_generator import asynccontextmanager

from .exceptions import SerfClosedError, SerfConnectionError, SerfError
from .result import SerfResult
from .util import ValueEvent

logger = getLogger(__name__)

_conn_id = 0


class SerfTimeout(TimeoutError):
    pass


class _StreamReply:
    """
    This class represents a multi-message reply.

    Actually, it also represents the query itself, which is not started
    until you enter the stream's context.

    This is an internal class. See :meth:`Serf.stream` for details.
    """

    # pylint: disable=protected-access,too-many-instance-attributes,too-many-arguments

    send_stop = True
    head = None

    def __init__(self, conn, command, params, seq, expect_body):
        self._conn = conn
        self._command = command
        self._params = params
        self.seq = seq
        self._q = anyio.create_queue(10000)
        self.expect_body = -expect_body

    async def set(self, value):
        await self._q.put(outcome.Value(value))

    async def set_error(self, err):
        await self._q.put(outcome.Error(err))

    async def get(self):
        res = await self._q.get()
        return res.unwrap()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._q is None:
            raise StopAsyncIteration
        res = await self._q.get()
        if res is None:
            raise StopAsyncIteration
        return res.unwrap()

    async def __aenter__(self):
        reply = await self._conn._call(self._command, self._params, _reply=self)
        res = await reply.get()
        if res is not None:
            self.head = res.head
        return self

    async def __aexit__(self, *exc):
        hdl = self._conn._handlers
        if self.send_stop:
            async with anyio.open_cancel_scope(shield=True):
                try:
                    await self._conn.call(
                        "stop", params={b"Stop": self.seq}, expect_body=False
                    )
                except anyio.exceptions.ClosedResourceError:
                    pass
                if hdl is not None:
                    # TODO remember this for a while?
                    await self._conn.tg.spawn(self._cleanup, hdl)

    async def _cleanup(self, hdl, *, result=None):
        if result is not None:
            await result.set()
        await anyio.sleep(2)
        del hdl[self.seq]

    async def cancel(self):
        await self._q.put(None)
        self._q = None


class SerfConnection:
    """
    Manages RPC communication to and from a Serf agent.

    This is an internal class; see :class:`asyncserf.Serf` for methods
    you're supposed to call. ;-)
    """

    # pylint: disable=too-many-instance-attributes

    # Read from the RPC socket in blocks of this many bytes.
    # (Typically 4k)
    _socket_recv_size = resource.getpagesize()
    _conn_id = 0

    def __init__(self, tg, host="localhost", port=7373):
        type(self)._conn_id += 1
        self._conn_id = type(self)._conn_id
        self.tg = tg
        self.host = host
        self.port = port
        self._socket = None
        self._seq = 0
        self._handlers = {}
        self._send_lock = anyio.create_lock()

    # handler protocol: incoming messages are passed in using `.set`.
    # If .expect_body is True then the reader will add a body to the
    # request. If it's -1 then the first reply is the body-less OK (we
    # hope) and only subsequent replies will have a body.

    def __repr__(self):
        return "<%(class)s counter=%(c)s host=%(h)s port=%(p)s>" % {
            "class": self.__class__.__name__,
            "c": self._seq,
            "h": self.host,
            "p": self.port,
        }

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
        # pylint: disable=protected-access ## owch

        class SingleReply(ValueEvent):
            # pylint: disable=protected-access,no-self-argument
            """
            A helper class, used to process a single reply.
            """

            def __init__(slf, seq, expect_body):
                super().__init__()
                slf.seq = seq
                slf.expect_body = expect_body

            async def set(slf, val):  # pylint: disable=arguments-differ
                if self._handlers is not None:
                    del self._handlers[slf.seq]
                await super().set(val)

            async def set_error(slf, err):  # pylint: disable=arguments-differ
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

        async with self._send_lock:  # pylint: disable=not-async-context-manager  ## owch
            if self._socket is None:
                raise anyio.exceptions.ClosedResourceError()
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
            logger.warning("Reader terminated:%s", msg)
            return
        try:
            seq = msg.head[b"Seq"]
        except KeyError:
            raise RuntimeError("Reader got out of sync: " + str(msg))
        try:
            hdl = self._handlers[seq]
        except KeyError:
            logger.warning("Spurious message %s: %s", seq, msg)
            return

        if (
            msg.body is None
            and hdl.expect_body > 0
            and (hdl.expect_body > 1 or not msg.head[b"Error"])
        ):
            return True
        # Do this here because stream replies might arrive immediately
        # i.e. before the queue listener gets around to us
        if hdl.expect_body < 0:
            hdl.expect_body = -hdl.expect_body
        if msg.head[b"Error"]:
            await hdl.set_error(SerfError(msg))
            await anyio.sleep(0.01)
        else:
            await hdl.set(msg)
        return False

    async def _reader(self, *, result: ValueEvent = None):
        """Main loop for reading

        TODO: add a timeout for receiving message bodies.
        """
        unpacker = msgpack.Unpacker(object_hook=self._decode_addr_key)
        cur_msg = None

        async with anyio.open_cancel_scope(shield=True) as s:
            if result is not None:
                await result.set(s)

            try:
                while self._socket is not None:
                    if cur_msg is not None:
                        logger.debug("%d:wait for body", self._conn_id)
                    try:
                        async with anyio.fail_after(5 if cur_msg else math.inf):
                            buf = await self._socket.receive_some(
                                self._socket_recv_size
                            )
                    except TimeoutError:
                        seq = cur_msg.head.get(b"Seq", None)
                        hdl = self._handlers.get(seq, None)
                        if hdl is not None:
                            await hdl.set_error(SerfTimeout(cur_msg))
                        else:
                            raise SerfTimeout(cur_msg) from None
                    except anyio.exceptions.ClosedResourceError:
                        return  # closed by us
                    except OSError as err:
                        if err.errno == errno.EBADF:
                            return
                        raise
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
        return await self.call("handshake", {"Version": 1}, expect_body=False)

    async def auth(self, auth_key):
        """
        Performs the initial authentication on connect
        """
        return await self.call("auth", {"AuthKey": auth_key}, expect_body=False)

    @asynccontextmanager
    async def _connected(self):
        """
        This async context manager handles the actual TCP connection to
        the Serf process.
        """
        reader = None
        try:
            async with await anyio.connect_tcp(self.host, self.port) as sock:
                self._socket = sock
                reader = await self.tg.spawn(self._reader)
                yield self
        except socket.error as e:
            raise SerfConnectionError(self.host, self.port) from e
        finally:
            sock, self._socket = self._socket, None
            if sock is not None:
                await sock.close()
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

    @staticmethod
    def _decode_addr_key(obj_dict):
        """
        Callback function to handle the decoding of the 'Addr' field.

        Serf msgpack 'Addr' as an IPv6 address, and the data needs to be
        unpacked using socket.inet_ntop().

        :param obj_dict: A dictionary containing the msgpack map.
        :return: A dictionary with the correct 'Addr' format.
        """
        key = b"Addr"
        ip_addr = obj_dict.get(key, None)
        if ip_addr is not None:
            if len(ip_addr) == 4:  # IPv4
                ip_addr = socket.inet_ntop(socket.AF_INET, obj_dict[key])
            else:
                ip_addr = socket.inet_ntop(socket.AF_INET6, obj_dict[key])

                # Check if the address is an IPv4 mapped IPv6 address:
                # ie. ::ffff:xxx.xxx.xxx.xxx
                if ip_addr.startswith("::ffff:"):
                    ip_addr = ip_addr[7:]

            # The msgpack codec is set to raw,
            # thus everything needs to be bytes
            obj_dict[key] = ip_addr.encode("utf-8")

        return obj_dict
