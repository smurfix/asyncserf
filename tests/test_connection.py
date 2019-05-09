import socket

import pytest
import anyio
from async_generator import asynccontextmanager

from asyncserf import connection

# pylint: disable=not-async-context-manager,protected-access


def extract_addr(rpc, ip_address, address_family=socket.AF_INET6):
    packed_ip_format = socket.inet_pton(address_family, ip_address)
    r = rpc._decode_addr_key({b"Addr": packed_ip_format})
    return r[b"Addr"].decode("utf-8")


@asynccontextmanager
async def rpc_connect(**kw):
    async with anyio.create_task_group() as tg:
        conn = connection.SerfConnection(tg, **kw)
        async with conn._connected():
            yield conn


class TestSerfConnection:
    """
    Tests for the Serf RPC communication object.
    """

    @pytest.mark.anyio
    async def test_has_a_default_host_port_and_timeout(self):
        async with rpc_connect() as rpc:
            assert rpc.host == "localhost"
            assert rpc.port == 7373

    @pytest.mark.anyio
    async def test_allows_passing_host_port_and_timeout(self):
        async with anyio.create_task_group() as tg:
            rpc = connection.SerfConnection(tg, host="foo", port=455)
            assert rpc.host == "foo"
            assert rpc.port == 455

    @pytest.mark.anyio
    async def test_representation(self):
        async with rpc_connect() as rpc:
            assert str(rpc) == "<SerfConnection counter=0 host=localhost port=7373>"

    @pytest.mark.anyio
    async def test_connection_to_bad_socket_throws_exception(self):
        with pytest.raises(connection.SerfConnectionError) as exceptionInfo:
            async with rpc_connect(port=40000):
                pass
        assert isinstance(exceptionInfo.value.__cause__, OSError)

    @pytest.mark.anyio
    async def test_handshake_to_serf_agent(self):
        async with rpc_connect() as rpc:
            assert (await rpc.handshake()).head == {b"Seq": 0, b"Error": b""}

    @pytest.mark.anyio
    async def test_call_throws_exception_if_socket_none(self):
        async with rpc_connect() as rpc:
            with pytest.raises(connection.SerfError) as exceptionInfo:
                await rpc.call("members")
            assert "handshake" in str(exceptionInfo).lower()

    @pytest.mark.anyio
    async def test_handshake_and_call_increments_counter(self):
        async with rpc_connect() as rpc:
            assert "counter=0" in str(rpc)
            await rpc.handshake()
            assert "counter=1" in str(rpc)
            await rpc.call(
                "event",
                {"Name": "foo", "Payload": "test payload", "Coalesce": True},
                expect_body=False,
            )
            assert "counter=2" in str(rpc)

    @pytest.mark.anyio
    async def test_msgpack_object_stream_decode(self):
        async with rpc_connect() as rpc:
            await rpc.handshake()
            result = await rpc.call("members")
            assert result.head == {b"Error": b"", b"Seq": 1}
            assert b"Members" in result.body.keys()

    @pytest.mark.anyio
    async def test_small_socket_recv_size(self):
        async with rpc_connect() as rpc:
            # Read a paltry 7 bytes at a time, intended to stress the buffered
            # socket reading and msgpack message handling logic.
            await rpc.handshake()
            rpc._socket_recv_size = 7
            result = await rpc.call("members")
            assert result.head == {b"Error": b"", b"Seq": 1}
            assert b"Members" in result.body.keys()

    @pytest.mark.anyio
    async def test_rpc_timeout(self):
        async with rpc_connect() as rpc:
            # Avoid delaying the test too much.
            rpc.timeout = 0.1
            await rpc.handshake()
            # Incorrectly set expect_body to True for an event RPC,
            # which will wait around for a body it'll never get,
            # which should cause a SerfTimeout exception.
            with pytest.raises(connection.SerfTimeout):
                await rpc.call(
                    "event",
                    {"Name": "foo", "Payload": "test payload", "Coalesce": True},
                    expect_body=True,
                )

    @pytest.mark.anyio
    async def test_connection_closed(self):
        async with rpc_connect() as rpc:
            await rpc.handshake()

            await rpc._socket.close()

            with pytest.raises(OSError):
                await rpc.handshake()

    @pytest.mark.anyio
    async def test_decode_addr_key_ipv6(self):
        async with rpc_connect() as rpc:
            ip_address = "2001:a:b:c:1:2:3:4"
            assert extract_addr(rpc, ip_address) == ip_address

    @pytest.mark.anyio
    async def test_decode_addr_key_ipv4_mapped_ipv6(self):
        async with rpc_connect() as rpc:
            assert extract_addr(rpc, "::ffff:192.168.0.1") == "192.168.0.1"

    @pytest.mark.anyio
    async def test_decode_addr_key_ipv4(self):
        async with rpc_connect() as rpc:
            ip_address = "192.168.0.1"
            assert extract_addr(rpc, ip_address, socket.AF_INET) == ip_address

    @pytest.mark.anyio
    async def test_close(self):
        async with rpc_connect() as rpc:
            assert rpc._socket is not None
        assert rpc._socket is None
