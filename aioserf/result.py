import msgpack

class SerfResult(object):
    """
    Bounded result object for responses from a Serf agent.
    """

    def __init__(self, head=None, body=None):
        self.head, self.body = head, body

    def __iter__(self):
        yield self.head
        yield self.body

    def __repr__(self):
        return "%(class)s<head=%(h)s,body=%(b)s>" \
            % {'class': self.__class__.__name__,
               'h': self.head,
               'b': self.body}

    async def reply(self, client, params=None):
        """for queries"""
        await client.connection.call(b"respond", {
            b'ID':self.body[b'ID'],
            b'Payload':msgpack.packb(params),
            })
