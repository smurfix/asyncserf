try:
    from contextlib import asynccontextmanager, AsyncExitStack
except ImportError:
    from async_generator import asynccontextmanager
    from async_exit_stack import AsyncExitStack
import trio
import anyio
import mock
import attr
import time
from functools import partial

import asyncserf.client
from asyncserf.util import ValueEvent
from asyncserf.stream import SerfEvent

import logging

logger = logging.getLogger(__name__)

otm = time.time


@asynccontextmanager
async def stdtest(n=1, **kw):  # pylint: disable=unused-argument
    clock = trio.hazmat.current_clock()
    clock.autojump_threshold = 0.01

    @attr.s
    class S:
        tg = attr.ib()
        serfs = attr.ib(factory=set)
        splits = attr.ib(factory=set)
        s = []  # servers
        c = []  # clients

        async def ready(self, i=None):
            if i is not None:
                await self.s[i].is_ready
                return self.s[i]
            for s in self.s:
                if s is not None:
                    await s.is_ready
            return self.s

        def __iter__(self):
            return iter(self.s)

        @asynccontextmanager
        async def client(self, i: int = 0, **kv):  # pylint: disable=unused-argument
            """Get a client for the i'th server."""
            async with asyncserf.client.serf_client() as c:
                yield c

        def split(self, s):
            assert s not in self.splits
            logger.debug("Split: add %d", s)
            self.splits.add(s)

        def join(self, s):
            logger.debug("Split: join %d", s)
            self.splits.remove(s)

    def tm():
        try:
            return trio.current_time()
        except RuntimeError:
            return otm()

    async with anyio.create_task_group() as tg:
        st = S(tg)
        async with AsyncExitStack() as ex:
            ex.enter_context(mock.patch("time.time", new=tm))
            logging._startTime = tm()  # pylint:disable=protected-access

            ex.enter_context(
                mock.patch("asyncserf.client.serf_client", new=partial(mock_serf_client, st))
            )

            try:
                yield st
            finally:
                logger.info("Runtime: %s", clock.current_time())
                await tg.cancel_scope.cancel()
        logger.info("End")
        pass  # unwinding ex:AsyncExitStack


@asynccontextmanager
async def mock_serf_client(master, **cfg):
    async with anyio.create_task_group() as tg:
        ms = MockSerf(tg, master, **cfg)
        master.serfs.add(ms)
        try:
            yield ms
        finally:
            master.serfs.remove(ms)
        pass  # terminating mock_serf_client nursery


class MockSerf:
    def __init__(self, tg, master, **cfg):
        self.cfg = cfg
        self.tg = tg
        self.streams = {}
        self._master = master

    def __hash__(self):
        return id(self)

    async def spawn(self, fn, *args, **kw):
        async def run(evt=None, task_status=trio.TASK_STATUS_IGNORED):
            with trio.CancelScope() as sc:
                task_status.started(sc)
                if evt is not None:
                    await evt.set(sc)
                await fn(*args, **kw)

        evt = ValueEvent()
        await self.tg.spawn(run, evt)
        return await evt.get()

    def stream(self, typ):
        if "," in typ:
            raise RuntimeError("not supported")
        if not typ.startswith("user:"):
            raise RuntimeError("not supported")
        typ = typ[5:]
        s = MockSerfStream(self, typ)
        return s

    async def event(self, typ, payload, coalesce=True):
        # logger.debug("SERF>%s> %r", typ, payload)

        assert not coalesce
        for s in list(self._master.serfs):
            for x in self._master.splits:
                if (s.cfg.get("i", 0) < x) != (self.cfg.get("i", 0) < x):
                    break
            else:
                sl = s.streams.get(typ, None)
                if sl is not None:
                    for si in sl:
                        await si.qw.send(payload)


class MockSerfStream:
    def __init__(self, serf, typ):
        self.serf = serf
        self.typ = typ
        self.qr = None
        self.qw = None

    async def __aenter__(self):
        logger.debug("SERF:MON START:%s", self.typ)
        assert self.qw is None
        self.qw, self.qr = anyio.create_memory_object_stream(100)
        self.serf.streams.setdefault(self.typ, []).append(self)
        return self

    async def __aexit__(self, *tb):
        self.serf.streams[self.typ].remove(self)
        logger.debug("SERF:MON END:%s", self.typ)
        await self.qw.aclose()

    def __aiter__(self):
        return self

    async def __anext__(self):
        res = await self.qr.receive()
        # logger.debug("SERF<%s< %r", self.typ, res)
        evt = SerfEvent(self)
        evt.payload = res
        return evt
