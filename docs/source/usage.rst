
+++++++
 Usage
+++++++

.. module:: trio_serf

.. currentmodule:: trio_serf

Using :mod:`trio_serf` is reasonably simple: You open a long-lived connection
and send requests to it.

Let's consider a basic example::

    import trio
    from trio_serf import serf_client, UTF8Codec

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
        trio.run(main)

This sample is slightly asocial because it indiscriminately responds to all
queries (and requests all other events even if it doesn't do anythign with
them), but it's immediately obvious what this code is doing.

.. autofunction: trio_serf.serf_client

.. autoclass: trio_serf.Serf

---
Multiple concurrent requests
---

Async code as you know it heavily leans towards throwing requests over your
interface's wall and then using callbacks to process any replies. Trio-Serf
doesn't support that. Instead, you start a new task and do your work there.
The `trio_serf.Serf` class has a :meth:`Serf.spawn` 
helper method so that you can start your task within Trio-Serf's task group.

.. automethod:: trio_serf.Serf.spawn

Thus, let's extend our example with a keepalive transmitter::

    async def keepalive(client):
        while True:
            await trio.sleep(60)
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

.. automethod:: trio_serf.Serf.cancel

---------------------
Supported RPC methods
---------------------

Trio-Serf aims to support all methods exported by Serf's RPF interface.

Streaming
+++++++++

You've already seen an example for receiving an event stream:

.. automethod:: trio_serf.Serf.stream

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


.. automethod:: trio_serf.Serf.query

You can also receive a logging stream. Remember that Serf sends a bunch of
old log entries which may deadlock the RPC socket until you read them all.

.. automethod:: trio_serf.Serf.monitor

Requests
++++++++

Trio-Serf contains methods for all remaining RPC methods that Serf offers.

See Serf's `RPC documentation <https://www.serf.io/docs/agent/rpc.html>`
for details, esp. regarding the values in replies.

.. automethod:: trio_serf.Serf.event

.. automethod:: trio_serf.Serf.respond

.. automethod:: trio_serf.Serf.members

.. automethod:: trio_serf.Serf.tags

.. automethod:: trio_serf.Serf.join

.. automethod:: trio_serf.Serf.force_leave

.. automethod:: trio_serf.Serf.stats

Codecs
++++++

Serf's RPC protocol can transport user-specific payloads, which must be
binary strings. As these are inconvenient and rarely what you need,
Trio-Serf transparently encodes and decodes them with a user-supplied codec.

The codec needs to have ``encode`` and ``decode`` methods which return /
accept :class:`bytes`. The default is to do nothing.

.. automodule:: trio_serf.codec
    :members:


Helper classes
++++++++++++++

.. autoclass:: trio_serf.stream.SerfStream

.. autoclass:: trio_serf.stream.SerfQuery

.. autoclass:: trio_serf.stream.SerfEvent
    :members:

.. autoclass:: trio_serf.util.ValueEvent

