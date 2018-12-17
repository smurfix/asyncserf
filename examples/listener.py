#!/usr/bin/python3

import anyio
from aioserf import serf_client, UTF8Codec

import logging

async def main():
    async with serf_client(codec = UTF8Codec()) as client:
        async with client.stream('*') as stream:
            async for resp in stream:
                if resp.event == 'query':
                    await resp.respond('For %s, with %s' % (resp.name, resp.payload))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    anyio.run(main)
