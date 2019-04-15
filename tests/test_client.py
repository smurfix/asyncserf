import re

import pytest

from asyncserf import SerfError, serf_client


# pylint: disable=not-async-context-manager,protected-access


class TestSerfCommands:
    """
    Common commands for the library
    """

    #    @pytest.mark.anyio
    #    async def test_rpc_auth(self):
    #        with mock.patch('asyncserf.client.SerfConnection') as mock_serf_connection_class:
    #            mock_serf_connection = mock.MagicMock()
    #            mock_serf_connection_class.return_value = mock_serf_connection
    #            async with serf_client(rpc_auth='secret') as serf:
    #                assert serf._conn is not None
    #            mock_serf_connection.auth.assert_called_once_with('secret')

    @pytest.mark.anyio
    async def test_has_a_default_host_and_port(self):
        async with serf_client() as serf:
            assert serf.host == "localhost"
            assert serf.port == 7373

    @pytest.mark.anyio
    async def test_initialises_a_serf_connection_on_creation(self):
        async with serf_client() as serf:
            assert serf._conn is not None

    @pytest.mark.anyio
    async def test_sending_a_simple_event(self):
        async with serf_client() as serf:
            assert (await serf.event("foo", "bar")).head == {b"Error": b"", b"Seq": 1}

    @pytest.mark.anyio
    async def test_sending_a_non_coalescing_event(self):
        async with serf_client() as serf:
            assert (await serf.event("foo", "bar")).head == {b"Error": b"", b"Seq": 1}

    @pytest.mark.anyio
    async def test_event_payload_is_optional(self):
        async with serf_client() as serf:
            assert (await serf.event("foo")).head == {b"Error": b"", b"Seq": 1}
            assert (await serf.event("bar", coalesce=False)).head == {
                b"Error": b"",
                b"Seq": 2,
            }

    @pytest.mark.anyio
    async def test_force_leaving_of_a_node(self):
        async with serf_client() as serf:
            assert (await serf.force_leave("bad-node-name")).head == {
                b"Error": b"",
                b"Seq": 1,
            }

    @pytest.mark.anyio
    async def test_joining_a_non_existent_node(self):
        async with serf_client() as serf:
            address = "127.0.0.1:23000"
            with pytest.raises(SerfError) as e:
                await serf.join([address])
            assert "dial tcp" in str(e.value)
            with pytest.raises(SerfError) as e:
                await serf.join([address])
            assert "dial tcp" in str(e.value)

    @pytest.mark.anyio
    async def test_joining_an_existing_node_fails(self):
        async with serf_client() as serf:
            with pytest.raises(SerfError) as e:
                await serf.join(["127.0.0.1:7373"])
            join = e.value.args[0]
            assert join.head[b"Seq"] == 1
            assert (
                b"EOF" in join.head[b"Error"]
                or b"connection reset by peer" in join.head[b"Error"]
            )
            assert join.body == {b"Num": 0}

    @pytest.mark.anyio
    async def test_providing_a_single_value_should_put_it_inside_a_list(self):
        async with serf_client() as serf:
            with pytest.raises(SerfError) as e:
                await serf.join("127.0.0.1:7373")
            join = e.value.args[0]
            assert join.head[b"Seq"] == 1
            assert (
                b"EOF" in join.head[b"Error"]
                or b"connection reset by peer" in join.head[b"Error"]
            )
            assert join.body == {b"Num": 0}

    @pytest.mark.anyio
    async def test_member_list_is_not_empty(self):
        async with serf_client() as serf:
            members = await serf.members()
            assert len(members.body[b"Members"]) > 0

    @pytest.mark.anyio
    async def test_member_filtering_name(self):
        async with serf_client() as serf:
            # Get current node name.
            members = await serf.members()
            name = members.body[b"Members"][0][b"Name"]

            members = await serf.members(name=name)
            assert len(members.body[b"Members"]) == 1

    @pytest.mark.anyio
    async def test_member_filtering_name_no_matches(self):
        async with serf_client() as serf:
            members = await serf.members(name="no_node_has_this_name")
            assert len(members.body[b"Members"]) == 0

    @pytest.mark.anyio
    async def test_member_filtering_status_alive(self):
        async with serf_client() as serf:
            members = await serf.members(status="alive")
            assert len(members.body[b"Members"]) > 0

    @pytest.mark.anyio
    async def test_member_filtering_status_no_matches(self):
        async with serf_client() as serf:
            members = await serf.members(status="invalid_status")
            assert len(members.body[b"Members"]) == 0

    @pytest.mark.anyio
    async def test_member_filtering_tags(self):
        async with serf_client() as serf:
            members = await serf.members(tags={"foo": "bar"})
            assert len(members.body[b"Members"]) == 1

    @pytest.mark.anyio
    async def test_member_filtering_tags_regex(self):
        async with serf_client() as serf:
            members = await serf.members(tags={"foo": "ba[rz]"})
            assert len(members.body[b"Members"]) == 1

    @pytest.mark.anyio
    async def test_member_check_addr(self):
        async with serf_client() as serf:
            # regression test for issue 20
            members = await serf.members()
            ip_addr = members.body[b"Members"][0][b"Addr"]

            assert (
                re.match(rb"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_addr)
                or b":" in ip_addr
            )

    @pytest.mark.anyio
    async def test_stats_is_well_formed(self):
        async with serf_client() as serf:
            stats = await serf.stats()
            for key in [b"agent", b"runtime", b"serf", b"tags"]:
                assert key in stats.body
                assert isinstance(stats.body[key], dict)

    @pytest.mark.anyio
    async def test_close(self):
        async with serf_client() as serf:
            assert serf._conn is not None
        assert serf._conn is None
