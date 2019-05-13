# Collection of basic codecs for the messages' payload

import msgpack

__all__ = ["UTF8Codec", "MsgPackCodec", "NoopCodec"]


class NoopCodec:
    """A codec that does nothing.

    Your payload needs to consist of bytes.
    """

    @staticmethod
    def encode(data):
        assert isinstance(data, bytes)
        return data

    @staticmethod
    def decode(data):
        return data


class UTF8Codec:
    """A codec that translates to UTF-8 strings.

    Your payload needs to be a single string.

    This codec will *not* stringify other data types for you.
    """

    @staticmethod
    def encode(data):
        return data.encode("utf-8")

    @staticmethod
    def decode(data):
        return data.decode("utf-8")


class MsgPackCodec:
    """A codec that encodes to "msgpack"-encoded bytestring.

    Your payload must consist of whatever "msgpack" accepts.

    Args:
      ``use_bin_type``: Bytestrings are encoded as byte arrays.
                        Defaults to ``True``. If ``False``,
                        bytes are transmitted as string types and input
                        strings are not UTF8-decoded. Use this if your
                        network contains clients which use
                        non-UTF8-encoded strings (this violates the
                        MsgPack specification).
      ``use_list``: if ``True``, lists and tuples are returned as lists
                    (i.e. modifyable). Defaults to ``False``, which uses
                    immutable tuples (this is faster).
    """

    def __init__(self, use_bin_type=True, use_list=False):
        self.use_bin_type = use_bin_type
        self.use_list = use_list

    def encode(self, data):
        return msgpack.packb(data, use_bin_type=self.use_bin_type)

    def decode(self, data):
        return msgpack.unpackb(data, raw=not self.use_bin_type, use_list=self.use_list)
        # raw=False would try to decode input bytes, which is not what you
        # want when the input is a bytestring. So we only use that if
        # bytestring input has been marked as such.
