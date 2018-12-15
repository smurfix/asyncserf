aioserf
=======

AioSerf is an async Python interface to Serf, the decentralised solution
for service discovery and orchestration.

It uses `anyio <https://github.com/agronholm/anyio>`, thus should work with
``asyncio``, ``trio``, and ``curio``. Hopefully.

.. image:: https://secure.travis-ci.org/smurfix/aioserf.png?branch=master
    :alt: Travis-CI badge
    :target: http://travis-ci.org/smurfix/aioserf
.. image:: https://gemnasium.com/smurfix/aioserf.png
    :alt: Gemnasium badge
    :target: https://gemnasium.com/smurfix/aioserf
.. image:: https://badge.fury.io/py/aioserf.svg
    :alt: PyPI latest version badge
    :target: https://pypi.python.org/pypi/aioserf
.. image:: https://coveralls.io/repos/smurfix/aioserf/badge.png?branch=master
    :alt: Code coverage badge
    :target: https://coveralls.io/r/smurfix/aioserf?branch=master

Installation
------------

aioserf requires a running Serf agent. See `Serf's agent documentation
<http://www.serfdom.io/docs/agent/basics.html>`_ for instructions.

To install aioserf, run the following command:

.. code-block:: bash

    $ pip install aioserf

or alternatively (you really should be using pip though):

.. code-block:: bash

    $ easy_install aioserf

or from source:

.. code-block:: bash

    $ python setup.py install

Getting Started
---------------

.. code-block:: python

    from aioserf import serf_client

    async with serf_client() as client:
        await client.event('foo', 'bar')

Stream usage:

.. code-block:: python

    from aioserf import serf_client

    async with serf_client() as client:
        async for response in client.stream('*'):
            print(response)

Development
------------

aioserf requires a running Serf agent. See `Serf's agent documentation
<http://www.serfdom.io/docs/agent/basics.html>`_ for instructions.

You can run the tests using the following commands:

.. code-block:: bash

    $ serf agent --tag foo=bar & # start serf agent
    $ python3 -mpytest tests

