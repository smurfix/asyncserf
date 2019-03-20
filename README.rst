trio-serf
=========

trio-serf is an async Python interface to Serf, the decentralised solution
for service discovery and orchestration.

It uses `trio <https://github.com/python-trio/trio>` as its underlying
async framework. Previous versions used the `anyio
<https://github.com/agronholm/anyio>` wrapper, thus worked with ``asyncio``,
``trio``, and ``curio``, but this has been discontinued because of issues
with error handling.

.. image:: https://badge.fury.io/py/trio-serf.svg
    :alt: PyPI latest version badge
    :target: https://pypi.python.org/pypi/trio-serf
.. image:: https://coveralls.io/repos/smurfix/trio-serf/badge.png?branch=master
    :alt: Code coverage badge
    :target: https://coveralls.io/r/smurfix/trio-serf?branch=master

Installation
------------

trio-serf requires a running Serf agent. See `Serf's agent documentation
<http://www.serfdom.io/docs/agent/basics.html>`_ for instructions.

To install trio-serf, run the following command:

.. code-block:: bash

    $ pip install trio-serf

or alternatively (you really should be using pip though):

.. code-block:: bash

    $ easy_install trio-serf

or from source:

.. code-block:: bash

    $ python setup.py install

Getting Started
---------------

These examples require a running async loop.
`Trio <https://github.com/python-trio/trio>` is recommended, though
``asyncio`` works too.

.. code-block:: python

    from trio_serf import serf_client

    async with serf_client() as client:
        await client.event('foo', 'bar')

Stream usage:

.. code-block:: python

    from trio_serf import serf_client

    async with serf_client() as client:
        async with client.stream('*') as stream:
            async for resp in stream:
                print(resp)

Development
------------

You can run the tests using the following commands:

.. code-block:: bash

    $ serf agent --tag foo=bar & # start serf agent
    $ python3 -mpytest tests

