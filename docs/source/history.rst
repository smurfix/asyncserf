Release history
===============

.. currentmodule:: asyncserf

.. towncrier release notes start

AsyncSerf 0.11
--------------

- Actor supports packer/unpacker
- Removed stupidity inherited from DistKV's mock serf

AsyncSerf 0.10
--------------

- Actor fixes
- add Actor hook to speed up syncs during testing

AsyncSerf 0.9
-------------

- allow Actor enable/disable
- new Actor accessors

AsyncSerf 0.8
-------------

- add taskgroup and spawn method to Actor
- add mutability flag to NodeList

AsyncSerf 0.7
-------------

- add Actor

AsyncSerf 0.6
-------------

- use our own cancel error for ValueEvent ("Future")

AsyncSerf 0.5
-------------

- Use anyio
- rename to AsyncSerf

AsyncSerf 0.2.0
---------------

Features
~~~~~~~~

- :mod:`asyncserf` now supports 100% of Serf's RPC interface.
- Documentation (using sphinx)!

