# utility code

import attr
import outcome

import anyio
from anyio.exceptions import CancelledError


@attr.s
class ValueEvent:
    """A waitable value useful for inter-task synchronization,
    inspired by :class:`threading.Event`.

    An event object manages an internal value, which is initially
    unset, and tasks can wait for it to become True.

    """

    event = attr.ib(factory=anyio.create_event, init=False)
    value = attr.ib(default=None, init=False)

    async def set(self, value):
        """Set the result to return this value, and wake any waiting task.
        """
        self.value = outcome.Value(value)
        await self.event.set()

    async def set_error(self, exc):
        """Set the result to raise this exceptio, and wake any waiting task.
        """
        self.value = outcome.Error(exc)
        await self.event.set()

    def is_set(self):
        return self.value is not None

    def cancel(self):
        return self.set_error(CancelledError())

    async def get(self):
        """Block until the value is set.

        If it's already True, then this method is still a checkpoint, but
        otherwise returns immediately.

        """
        await self.event.wait()
        return self.value.unwrap()

