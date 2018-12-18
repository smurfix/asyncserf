#!/usr/bin/python3

# run "serf query example FooBar" to test this

import anyio
from aioserf import serf_client, UTF8Codec

import logging


async def main():
    async with serf_client(codec=UTF8Codec()) as client:
        await client.event("Hello", payload="I am an example")

        async with client.stream('*') as stream:
            async for resp in stream:
                print(resp)
                if resp.event == 'query' and resp.name == "example":
                    await resp.respond('For %s, with %s' % (resp.name, resp.payload))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    anyio.run(main)
