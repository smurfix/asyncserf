
+++++++
 Usage
+++++++

.. module:: asyncserf

.. currentmodule:: asyncserf

Using :mod:`asyncserf` is reasonably simple: You open a long-lived connection
and send requests to it.

Let's consider a basic example::

    import anyio
    from asyncserf import serf_client, UTF8Codec

    async def main():
        async with serf_client(codec = UTF8Codec()) as client:
            await client.event("Hello", payload="I am an example")
            
            async with client.stream('*') as stream:
                async for resp in stream:
                    if resp.event == 'query':
                        await resp.respond('For %s, with %s' % (resp.name, resp.payload))
                    else:
                        print("I got me a %s" % (resp,))

    if __name__ == "__main__":
        anyio.run(main)

This sample is slightly asocial because it indiscriminately responds to all
queries (and requests all other events even if it doesn't do anything with
them), but it's immediately obvious what this code is doing.

.. autofunction: asyncserf.serf_client

.. autoclass: asyncserf.client.Serf

---
Multiple concurrent requests
---

AsyncSerf subscribes to "Structured Concurrency" paradigm, i.e. each
requests runs in a separate task; there are no callbacks.

The `asyncserf.Serf` class has a :meth:`Serf.spawn` helper method so that
you can start your handler tasks within AsyncSerf's task group – they will
get cancelled along with the rest of the connection's tasks if there is an
unrecoverable error.

.. automethod:: asyncserf.Serf.spawn

Thus, let's extend our example with a keepalive transmitter::

    async def keepalive(client):
        while True:
            await anyio.sleep(60)
            await client.event("keepalive", payload="My example")

    async def main():
        async with serf_client(codec = UTF8Codec()) as client:
            await client.event("Hello", payload="I am an example")
            await client.spawn(keepalive)
            
            ## async with … – continue as above

Any complex system should include code to shut itself down cleanly, so
let's add that too::

            keeper = await client.spawn(keepalive)
            async with client.stream('*') as stream:
                async for resp in stream:
                    if resp.event == 'query':
                        await resp.respond('For %s, with %s' % (resp.name, resp.payload))
                    elif resp.event == 'user' and resp.name == 'shutdown':
                        break
                    elif keeper is not None and resp.event == 'user' and resp.name == 'quiet':
                        keeper.cancel()
                        keeper = None
                    else:
                        print("I got me a %s" % (resp,))
            client.cancel()

though in a real, complex system you probably want to open multiple,
more selective event streams.

.. automethod:: asyncserf.Serf.cancel

---------------------
Supported RPC methods
---------------------

AsyncSerf aims to support all methods exported by Serf's RPF interface.

Streaming
+++++++++

You've already seen an example for receiving an event stream:

.. automethod:: asyncserf.Serf.stream

A query is also implemented as a stream because there may be any number of
replies::

    NS=10**9

    async def ask_query(self, client):
        acks = 0
        reps = 0
        async with client.query("foo", payload="baz", request_ack=True,
                timeout=5*NS) as q:
            async for r in q:
                if not hasattr(r,'type'):
                    break
                if r.type == "ack":
                    acks += 1
                elif r.type == "response":
                    reps += 1
                    # process `r.payload`
                    pass
                else:
                    assert False, r
        # at this point the query is finished
        pass

The ``done`` type (which you'll find in Serf's RPC documentation) is
internally translated to a ``StopAsyncIteration`` exception, so you don't
have to handle it yourself.


.. automethod:: asyncserf.Serf.query

You can also receive a logging stream. Remember that Serf sends a bunch of
old log entries which may deadlock the RPC socket until you read them all.

.. automethod:: asyncserf.Serf.monitor

Requests
++++++++

AsyncSerf contains methods for all remaining RPC methods that Serf offers.

See Serf's `RPC documentation <https://www.serf.io/docs/agent/rpc.html>`
for details, esp. regarding the values in replies.

.. automethod:: asyncserf.Serf.event

.. automethod:: asyncserf.Serf.respond

.. automethod:: asyncserf.Serf.members

.. automethod:: asyncserf.Serf.tags

.. automethod:: asyncserf.Serf.join

.. automethod:: asyncserf.Serf.force_leave

.. automethod:: asyncserf.Serf.stats

Codecs
++++++

Serf's RPC protocol can transport user-specific payloads, which must be
binary strings. As these are inconvenient and rarely what you need,
AsyncSerf transparently encodes and decodes them with a user-supplied codec.

The codec needs to have ``encode`` and ``decode`` methods which return /
accept :class:`bytes`. The default is to do nothing: bytes are
transported unchanged, anything else will trigger an exception.

.. automodule:: asyncserf.codec
    :members:


Helper classes
++++++++++++++

.. autoclass:: asyncserf.stream.SerfStream

.. autoclass:: asyncserf.stream.SerfQuery

.. autoclass:: asyncserf.stream.SerfEvent
    :members:

.. autoclass:: asyncserf.util.ValueEvent

