import mock
import pytest
import re

from contextlib import closing
from aioserf import serf_client


class TestAioSerfStream(object):
    """
    Common commands for the library
    """
    @pytest.mark.anyio
    async def test_sending_a_simple_event(self):
        async with serf_client() as serf:
            assert (await serf.event('foo', 'bar')).head == {b'Error': b'', b'Seq': 1}
            assert (await serf.event('bill', 'gates')).head == {b'Error': b'', b'Seq': 2}

    @pytest.mark.anyio
    async def test_stream(self):
        async with serf_client() as serf:
            async with serf.stream() as response:
                assert response.head == {b'Error': b'', b'Seq': 1}
                expected_data = sorted([
                    [b'bill', b'gates'],
                    [b'foo', b'bar'],
                ])
                all_responses = []
                async for resp in response:
                    all_responses.append(resp)
                    if len(all_responses) == 2:
                        break

            sorted_responses = sorted([
                [
                    res.body[b'Name'],
                    res.body[b'Payload'],
                ] for res in all_responses
            ])
            for i, res in enumerate(sorted_responses):
                expected = expected_data[i]
                assert res[0] == expected[0]
                assert res[1] == expected[1]
