#!/usr/bin/python3

# This code tests how many requests per second you can send to your Serf
# instance. It also verifies that Serf can handle sequence numbers
# in excess of 2^32. (2^64 fails because MsgPack cannot encode integers
# that large than that. 2^63 works, but your code won't get that far.)

import anyio
from aioserf import serf_client
import sys

import logging


async def foo(client):
    while True:
        await client._conn.call("stop", {"Stop": 123}, expect_body=False)


async def main():
    async with serf_client() as client:
        client._conn._seq = 2**63
        for i in range(10):
            await client.spawn(foo, client)
            while True:
                await anyio.sleep(1)
                print(client._conn._seq - 2**63, end=" \r")
                sys.stdout.flush()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    anyio.run(main)
