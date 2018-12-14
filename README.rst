aioserf
==========

The Python interface to Serf, the decentralised solution for
service discovery and orchestration.

.. image:: https://secure.travis-ci.org/KushalP/aioserf-py.png?branch=master
    :alt: Travis-CI badge
    :target: http://travis-ci.org/KushalP/aioserf-py
.. image:: https://gemnasium.com/KushalP/aioserf-py.png
    :alt: Gemnasium badge
    :target: https://gemnasium.com/KushalP/aioserf-py
.. image:: https://badge.fury.io/py/aioserf.svg
    :alt: PyPI latest version badge
    :target: https://pypi.python.org/pypi/aioserf
.. image:: https://coveralls.io/repos/KushalP/aioserf-py/badge.png?branch=master
    :alt: Code coverage badge
    :target: https://coveralls.io/r/KushalP/aioserf-py?branch=master

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

    from contextlib import closing
    from aioserf.client import AioSerf

    with closing(AioSerf()) as client:
        client.event('foo', 'bar')

Stream usage:

.. code-block:: python

    from contextlib import closing
    from aioserf.client import AioSerf

    with closing(AioSerf(timeout=None)) as client:
        for response in client.stream('*').body:
            print(response)

Development
------------

aioserf requires a running Serf agent. See `Serf's agent documentation
<http://www.serfdom.io/docs/agent/basics.html>`_ for instructions.

You can run the tests using the following commands:

.. code-block:: bash

    $ serf agent --tag foo=bar  # start serf agent
    $ python setup.py test
