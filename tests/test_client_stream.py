import pytest
import anyio

from asyncserf import UTF8Codec, serf_client

# pylint: disable=not-async-context-manager,protected-access


class TestSerfStream:
    async def send_data(self):
        async with serf_client() as serf:
            assert (await serf.event("foo", "bar")).head == {b"Error": b"", b"Seq": 1}
            assert (await serf.event("bill", "gates")).head == {
                b"Error": b"",
                b"Seq": 2,
            }

    @pytest.mark.anyio
    async def test_stream(self):
        async with serf_client(codec=UTF8Codec()) as serf:
            async with serf.stream("user") as response:
                await self.send_data()
                assert response.head == {b"Error": b"", b"Seq": 1}
                expected_data = sorted([["bill", "gates"], ["foo", "bar"]])
                all_responses = []
                async for resp in response:
                    all_responses.append(resp)
                    if len(all_responses) == 2:
                        break

            sorted_responses = sorted(
                [[res.name, res.payload] for res in all_responses]
            )
            for i, res in enumerate(sorted_responses):
                expected = expected_data[i]
                assert res[0] == expected[0]
                assert res[1] == expected[1]


class TestSerfQuery:
    async def answer_query(self, serf, ev):
        async with serf.stream("query:foo") as s:
            await ev.set()
            async for r in s:
                assert r.payload == "baz"
                await r.respond("bar")

    async def ask_query(self, serf, ev):
        acks = 0
        reps = 0
        async with serf.query("foo", payload="baz", request_ack=True, timeout=1) as q:
            async for r in q:
                if not hasattr(r, "type"):
                    break
                if r.type == "ack":
                    acks += 1
                elif r.type == "response":
                    reps += 1
                    assert r.payload == "bar"
                else:
                    assert False, r
        assert reps > 0
        assert acks > 0
        await ev.set()

    @pytest.mark.anyio
    async def test_query(self):
        async with anyio.create_task_group() as tg:
            async with serf_client(codec=UTF8Codec()) as serf1:
                async with serf_client(codec=UTF8Codec()) as serf2:
                    ev1 = anyio.create_event()
                    ev2 = anyio.create_event()
                    await tg.spawn(self.answer_query, serf2, ev1)
                    await ev1.wait()
                    await tg.spawn(self.ask_query, serf1, ev2)
                    await ev2.wait()


class TestSerfMonitor:
    @pytest.mark.anyio
    async def test_sending_a_simple_event(self):
        async with serf_client() as serf:
            assert (await serf.event("foo", "bar")).head == {b"Error": b"", b"Seq": 1}
            assert (await serf.event("bill", "gates")).head == {
                b"Error": b"",
                b"Seq": 2,
            }

    @pytest.mark.anyio
    async def test_monitor(self):
        n = 0
        async with serf_client() as serf:
            async with serf.monitor() as response:
                async for resp in response:
                    print(resp)
                    n += 1
                    if n >= 3:
                        break
