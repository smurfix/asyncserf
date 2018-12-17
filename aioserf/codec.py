# Collection of basic codecs for the messages' payload

import msgpack

__all__ = ['UTF8Codec', 'MsgPackCodec']

class UTF8Codec:
    def encode(self, data):
        return data.encode("utf-8")
    def decode(self, data):
        return data.decode("utf-8")

class MsgPackCodec:
    def __init__(self, use_bin_type=True, use_list=False):
        self.use_bin_type = use_bin_type
        self.use_list = use_list
    def encode(self, data):
        return msgpack.packb(data, use_bin_type=self.use_bin_type)
    def decode(self, data):
        return msgpack.unpackb(data, raw=False, use_list=self.use_list)


