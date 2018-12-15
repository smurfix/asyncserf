#
# async serf client
# (c) 2018 Matthias Urlichs

import anyio
from .connection import SerfConnection
from async_generator import asynccontextmanager

@asynccontextmanager
async def serf_client(**kw):
    async with anyio.create_task_group() as tg:
        client = AioSerf(tg, **kw)
        async with client._connected():
            yield client

class AioSerf(object):
    def __init__(self, tg, host='localhost', port=7373, rpc_auth=None):
        self.tg = tg
        self.host = host
        self.port = port
        self.rpc_auth = rpc_auth

    @asynccontextmanager
    async def _connected(self):
        self.connection = SerfConnection(self.tg, host=self.host, port=self.port)
        try:
            async with self.connection._connected():
                await self.connection.handshake()
                if self.rpc_auth:
                    await self.connection.auth(self.rpc_auth)
                yield self
        finally:
            self.connection = None

    def stream(self, event_types='*'):
        if isinstance(event_types, list):
            event_types = ','.join(event_types)
        return self.connection.stream(
            'stream', {'Type': event_types})

    def event(self, name, payload=None, coalesce=True):
        """
        Send an event to the cluster. Can take an optional payload as well,
        which will be sent in the form that it's provided.
        """
        return self.connection.call(
            'event',
            {'Name': name, 'Payload': payload, 'Coalesce': coalesce},
            expect_body=False)

    def members(self, name=None, status=None, tags=None):
        """
        Lists members of a Serf cluster, optionally filtered by one or more
        filters:

        `name` is a string, supporting regex matching on node names.
        `status` is a string, supporting regex matching on node status.
        `tags` is a dict of tag names and values, supporting regex matching
        on values.
        """
        filters = {}

        if name is not None:
            filters['Name'] = name

        if status is not None:
            filters['Status'] = status

        if tags is not None:
            filters['Tags'] = tags

        if len(filters) == 0:
            return self.connection.call('members')
        else:
            return self.connection.call('members-filtered', filters)

    def force_leave(self, name):
        """
        Force a node to leave the cluster.
        """
        return self.connection.call(
            'force-leave',
            {"Node": name}, expect_body=False)

    def join(self, location):
        """
        Join another cluster by provided a list of ip:port locations.
        """
        if not isinstance(location, (list, tuple)):
            location = [location]
        return self.connection.call(
            'join',
            {"Existing": location, "Replay": False}, expect_body=2)

    def stats(self):
        """
        Obtain operator debugging information about the running Serf agent.
        """
        return self.connection.call('stats')

