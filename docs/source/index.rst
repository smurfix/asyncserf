=========================================================
AsyncSerf: an async Python front-end for Hashicorp's Serf
=========================================================

AsyncSerf is an asynchronous interface to `Serf <http://serf.io/>`.

Key features:

* async; uses `AnyIO <https://github.com/agronholm/anyio/>`,
  thus is compatible with ``asyncio``, ``trio`` and ``curio``.

* properly multiplexed; issue multiple commands in parallel

* listen for, and respond to, queries / user events

* transparently encodes/decodes your payloads, if desired

* should support 100% of Serf's RPC command set

* includes adequate tests and example code

* License: MIT

Inherited from `Trio <https://github.com/python-trio/trio>`_:

* Real-time chat: https://gitter.im/python-trio/general

* Contributor guide: https://trio.readthedocs.io/en/latest/contributing.html

* Code of conduct: Contributors are requested to follow our `code of
  conduct <https://trio.readthedocs.io/en/latest/code-of-conduct.html>`_
  in all project spaces.

.. toctree::
   :maxdepth: 2

   rationale.rst
   usage.rst
   actor.rst
   history.rst

====================
 Indices and tables
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :ref:`glossary`
