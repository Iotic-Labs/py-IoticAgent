# Copyright (c) 2016 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-IoticAgent/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import unicode_literals

from warnings import warn
from functools import partial
from abc import ABCMeta, abstractmethod
from io import BytesIO
from zlib import (compressobj as _zlib_compressobj, decompressobj as _zlib_decompressobj, DEFLATED as _zlib_DEFLATED,
                  Z_FINISH as _zlib_Z_FINISH)

from .Const import COMP_NONE, COMP_ZLIB, COMP_LZ4F


def __dummy(*args, **kwargs):  # pylint: disable=unused-argument
    raise NotImplementedError('(de)compression type unavailable')


try:
    from lz4framed import compress as _lz4f_compress, Decompressor as _lz4f_Decompressor
except ImportError:
    _lz4f_compress = _lz4f_Decompressor = __dummy
    warn('Unable to import lz4framed - COMP_LZ4F will not be available.', ImportWarning)
    LZ4F_AVAILABLE = False
else:
    LZ4F_AVAILABLE = True

# Default maximum length to allow when decompressing before raising OversizeException
DEFAULT_MAX_SIZE = 1024 * 1024


class OversizeException(Exception):
    """Raised when the decompressed result exceeds the associated size restriction"""

    def __init__(self, max_length):  # pylint: disable=useless-super-delegation
        super(OversizeException, self).__init__(max_length)

    @property
    def size(self):
        return self.args[0]  # pylint: disable=unsubscriptable-object


class Compressor(object):
    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def method():
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def compress(data):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def decompress(data, max_size=DEFAULT_MAX_SIZE):
        raise NotImplementedError


class Noop(Compressor):

    @staticmethod
    def method():
        return COMP_NONE

    @staticmethod
    def compress(data):
        return data

    @staticmethod
    def decompress(data, max_size=DEFAULT_MAX_SIZE):  # pylint: disable=unused-argument
        return data


# Not all versions support explicit keyword config
try:
    # some support one but not both
    _zlib_decompressobj(wbits=15)
    _zlib_compressobj(method=_zlib_DEFLATED, wbits=15)
except TypeError:
    warn('zlib module in use does not support setting of method & wbits', ImportWarning)
else:
    _zlib_compressobj = partial(_zlib_compressobj, method=_zlib_DEFLATED, wbits=15)  # pylint: disable=invalid-name
    _zlib_decompressobj = partial(_zlib_decompressobj, wbits=15)  # pylint: disable=invalid-name


class Zlib(Compressor):

    @staticmethod
    def method():
        return COMP_ZLIB

    @staticmethod
    def compress(data):
        out = BytesIO()
        # using obj so can specify params (via functools.partial)
        compressor = _zlib_compressobj()
        out.write(compressor.compress(data))
        out.write(compressor.flush(_zlib_Z_FINISH))
        return out.getvalue()

    @staticmethod
    def decompress(data, max_size=DEFAULT_MAX_SIZE):
        out = BytesIO()
        decompressor = _zlib_decompressobj()
        out.write(decompressor.decompress(data, max_size + 1024))
        if out.tell() > max_size:
            raise OversizeException(max_size)
        out.write(decompressor.flush())
        return out.getvalue()


class Lz4f(Compressor):
    """NOTE: Check LZ4F_AVAILABLE to make sure required module was loaded."""

    @staticmethod
    def method():
        return COMP_LZ4F

    @staticmethod
    def compress(data):
        return _lz4f_compress(data, checksum=True)

    @staticmethod
    def decompress(data, max_size=DEFAULT_MAX_SIZE):
        out = BytesIO()
        for chunk in _lz4f_Decompressor(BytesIO(data)):
            out.write(chunk)
            if out.tell() > max_size:
                raise OversizeException(max_size)
        return out.getvalue()


# pylint: disable=superfluous-parens
COMPRESSORS = {c.method(): c for c in ((Noop, Zlib, Lz4f) if LZ4F_AVAILABLE else (Noop, Zlib))}
