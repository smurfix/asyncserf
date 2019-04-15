# simple result class


class SerfResult:
    """
    Result object for responses from a Serf agent.
    """

    def __init__(self, head=None, body=None):
        self.head, self.body = head, body

    def __iter__(self):
        """
        Iterator.

        Used for assignment, i.e.::

            head, body = result
        """
        yield self.head
        yield self.body

    def __repr__(self):
        return "%(class)s<head=%(h)s,body=%(b)s>" % {
            "class": self.__class__.__name__,
            "h": self.head,
            "b": self.body,
        }
