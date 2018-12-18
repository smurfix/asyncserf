
+++++++
 Usage
+++++++

.. module:: aioserf

.. currentmodule:: aioserf

Using :mod:`aioserf` is reasonably simple: You open a long-lived connection
and send requests to it.

Let's consider a basic example::

    import anyio
    from aioserf import serf_client, UTF8Codec

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
queries (and requests all other events even if it doesn't do anythign with
them), but it's immediately obvious what this code is doing.

.. autofunction: aioserf.serf_client

.. autoclass: aioserf.AioSerf

---
Multiple concurrent requests
---

Async code as you know it heavily leans towards throwing requests over your
interface's wall and then using callbacks to process any replies. AioSerf
doesn't support that. Instead, you start a new task and do your work there.
The `aioserf.AioSerf` class has a :meth:`AioSerf.spawn` 
helper method so that you can start your task within AioSerf's task group.

.. automethod:: aioserf.AioSerf.spawn

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
                        await keeper.cancel()
                        keeper = None
                    else:
                        print("I got me a %s" % (resp,))
            await client.cancel()

though in a real, complex system you probably want to open multiple,
more selective event streams.

.. automethod:: aioserf.AioSerf.cancel

---------------------
Supported RPC methods
---------------------

AioSerf aims to support all methods exported by Serf's RPF interface.

Streaming
+++++++++

You've already seen an example for receiving an event stream:

.. automethod:: aioserf.AioSerf.stream

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


.. automethod:: aioserf.AioSerf.query

You can also receive a logging stream. Remember that Serf sends a bunch of
old log entries which may deadlock the RPC socket until you read them all.

.. automethod:: aioserf.AioSerf.monitor

Requests
++++++++

AioSerf contains methods for all remaining RPC methods that Serf offers.

See Serf's `RPC documentation <https://www.serf.io/docs/agent/rpc.html>`
for details, esp. regarding the values in replies.

.. automethod:: aioserf.AioSerf.event

.. automethod:: aioserf.AioSerf.respond

.. automethod:: aioserf.AioSerf.members

.. automethod:: aioserf.AioSerf.tags

.. automethod:: aioserf.AioSerf.join

.. automethod:: aioserf.AioSerf.force_leave

.. automethod:: aioserf.AioSerf.stats

Codecs
++++++

Serf's RPC protocol can transport user-specific payloads, which must be
binary strings. As these are inconvenient and rarely what you need,
AioSerf transparently encodes and decodes them with a user-supplied codec.

The codec needs to have ``encode`` and ``decode`` methods which return /
accept :class:`bytes`. The default is to do nothing.

.. automodule:: aioserf.codec
    :members:


Helper classes
++++++++++++++

.. autoclass:: aioserf.stream.SerfStream

.. autoclass:: aioserf.stream.SerfQuery

.. autoclass:: aioserf.stream.SerfEvent
    :members:

.. autoclass:: aioserf.util.ValueEvent

