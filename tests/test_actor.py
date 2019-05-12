import pytest
import trio
import time

from .mock_serf import stdtest
from asyncserf.actor import (
    Actor,
    GoodNodeEvent,
    TagEvent,
    UntagEvent,
    RecoverEvent,
    PingEvent,
    RawPingEvent,
)

import logging

logging.basicConfig(level=logging.INFO)

N = 20


@pytest.mark.trio
async def test_10_all(autojump_clock):
    """
    This test starts multiple servers at the same time and checks that all
    of them get their turn.
    """
    N = 5
    tagged = False

    async with stdtest(n=N, tocks=1000) as st:
        msgs = {}

        async def s1(i, *, task_status=trio.TASK_STATUS_IGNORED):
            nonlocal tagged
            async with st.client(i) as c:
                async with Actor(c, "test10", "c_" + str(i), cfg={"nodes": N}) as k:
                    task_status.started()
                    await k.set_value(i * 31)
                    c = 0
                    t = time.time()
                    async for m in k:
                        if not isinstance(m, RawPingEvent):
                            k.logger.debug("*** MSG %d %r", i, m)
                        ot, t = t, time.time()
                        if ot != t:
                            assert tagged <= 1
                        msgs.setdefault(i, []).append(m)
                        if isinstance(m, GoodNodeEvent):
                            pass
                        elif isinstance(m, TagEvent):
                            # assert not tagged  # may collide, so checked above
                            tagged += 1
                            c += 1
                        elif isinstance(m, UntagEvent):
                            assert tagged
                            tagged -= 1
                            if c > 2:
                                break
                assert tagged <= 1
                k.logger.debug("N2 %r", k._values)
                for x in range(1, 6):
                    assert k._values["c_" + str(x)] == x * 31

        async with trio.open_nursery() as tg:
            for i in range(1, 6):
                await tg.start(s1, i)


@pytest.mark.trio
async def test_11_some(autojump_clock):
    """
    This test starts multiple servers at the same time and checks that
    some of them are skipped.
    """
    N = 15

    async with stdtest(n=N, tocks=1000) as st:
        msgs = {}

        c = 0
        h = [0] * (N + 1)

        async def s1(i, *, task_status=trio.TASK_STATUS_IGNORED):
            nonlocal c
            async with st.client(i) as cl:
                async with Actor(cl, "test11", "c_" + str(i), cfg={"nodes": 3}) as k:
                    task_status.started()
                    await k.set_value(i * 31)
                    async for m in k:
                        msgs.setdefault(i, []).append(m)
                        if isinstance(m, GoodNodeEvent):
                            pass
                        elif isinstance(m, TagEvent):
                            c += 1
                            h[i] += 1
                        elif isinstance(m, (PingEvent, UntagEvent)):
                            if c > 10:
                                assert sum((x > 0) for x in h) < 6
                                return
                for i in range(1, 6):
                    assert k._values["c_" + str(i)] == i * 31

        async with trio.open_nursery() as tg:
            for i in range(1, 6):
                await tg.start(s1, i)

            await trio.sleep(100)
        pass  # server end


@pytest.mark.trio
@pytest.mark.parametrize("tocky", [-10, -2, -1, 0, 1, 2, 10])
async def test_12_split1(autojump_clock, tocky):
    """
    This test starts multiple servers at the same time.
    """
    n_ping = 0
    N = 10

    n_recover = [0] * N

    async with stdtest(n=N) as st:

        async def s1(i, *, task_status=trio.TASK_STATUS_IGNORED):
            nonlocal n_ping
            async with st.client(i) as c:
                async with Actor(c, "test12", "c_" + str(i), cfg={"nodes": 3}) as k:
                    task_status.started()
                    await k.set_value(i * 31)
                    c = 0
                    async for m in k:
                        if isinstance(m, TagEvent):
                            n_ping += 1
                        elif isinstance(m, RecoverEvent):
                            n_recover[i] += 1

        async with trio.open_nursery() as tg:
            for i in range(N):
                await tg.start(s1, i)

            await trio.sleep(60)
            print(n_ping, n_recover)
            st.split(N // 2)
            await trio.sleep(60)
            print(n_ping, n_recover)
            st.join(N // 2)
            await trio.sleep(60)
            print(n_ping, n_recover)

            tg.cancel_scope.cancel()
            pass  # server end
