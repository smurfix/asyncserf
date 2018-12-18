+++++++++++
 Rationale
+++++++++++

`Serf <http://serf.io/>` is a very good implementation of a truly
distributed gossip protocol. Python is a nice programming language
which supports coroutines. It recently acquired support for `Structured Concurrency
<https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/>`.

This module serves as the interface between coroutines and Serf.

