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

"""Mime type (and shorthand) checking functions. Used for point data requests."""

from __future__ import unicode_literals

from re import compile as re_compile

from .compat import unicode_type, PY3


__all__ = ('valid_mimetype', 'expand_idx_mimetype')


# Universal mime type restrictions
__MAX_LEN = 64


# The shorthand pattern begins with "idx/" and is followed by a positive integer without trailing zeroes. The maximum
# type length (__MAX_LEN) still applies.
__IDX_PREFIX = 'idx/'
__IDX_PATTERN = re_compile(r'^(?%si)%s(\S{1,%d})$' % (('a' if PY3 else ''), __IDX_PREFIX,
                                                      __MAX_LEN - len(__IDX_PREFIX)))


# Valid idx mappings. Indexes as strings to make lookup quicker (when matching __IDX_PATTERN). An entry for
# application/octet-stream is not included since payloads are in bytes and thus said type would provide no additional
# information. Clients should either expose this mapping to the user or convert to the normal long representation such
# that no additional application logic is required.
__IDX_MAPPING = {
    '1': 'application/ubjson',
    '2': 'text/plain; charset=utf8'
}


def valid_mimetype(type_, allow_none=True):
    """Checks for validity of given type, optionally allowing for a None value. Note: Unknown idx/NUMBER notation, where
       NUMBER is not a known shorthand mapping, will be rejected, i.e. type_ is valid if it
       1)  is an ASCII-only string between 1 & 64 characters long
       2a) does not begin with "idx/" OR
       2b) begins with "idx/" and is followed by a known shorthand index (integer)
    """
    if isinstance(type_, unicode_type):
        match = __IDX_PATTERN.match(type_)
        if match:
            return match.group(1) in __IDX_MAPPING
        else:
            return __is_ascii(type_, 1, __MAX_LEN)
    else:
        return type_ is None and allow_none


# Assumes string passed
def __is_ascii(obj, min_len=None, max_len=None):
    try:
        obj = obj.encode('ascii')
    except UnicodeEncodeError:
        return False
    else:
        return (True if max_len is None else len(obj) <= max_len) and (True if min_len is None else len(obj) >= min_len)


def expand_idx_mimetype(type_):
    """Returns long equivalent of type_, if available, otherwise type_ itself. Does not raise exceptions"""
    if isinstance(type_, unicode_type):
        match = __IDX_PATTERN.match(type_)
        return __IDX_MAPPING.get(match.group(1), type_) if match else type_
    else:
        return type_
