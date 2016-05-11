#!/usr/bin/env python3
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
from uuid import UUID
from re import compile as re_compile

from . import Const
from .compat import (PY3, string_types, int_types, arg_checker, ensure_ascii, ensure_unicode, urlparse, number_types,
                     Sequence, Mapping)


VALIDATION_LID_LEN = 64
VALIDATION_MIME_LEN = 64
VALIDATION_META_FMT = {'n3', 'xml', 'turtle'}
VALIDATION_META_LANGUAGE = 2
VALIDATION_META_LABEL = 64
VALIDATION_META_COMMENT = 256
VALIDATION_META_TAG_MIN = 3
VALIDATION_META_TAG_MAX = 16
VALIDATION_META_VALUE_UNIT = 128
VALIDATION_META_VALUE_UNIT_MIN_URLBITS = 3
VALIDATION_META_SEARCH_TEXT = 128
VALIDATION_MAX_ENCODED_LENGTH = int(round(1024 * 64 * 0.98))  # (64k is current hard AMQP message limit)
VALIDATION_FOC_TYPES = frozenset((Const.R_FEED, Const.R_CONTROL))
VALIDATION_SEARCH_TYPES = frozenset(('full', 'reduced', 'located'))
# http://www.w3.org/TR/xmlschema-2/#built-in-datatypes
VALIDATION_META_VALUE_TYPES = frozenset(("string", "boolean", "decimal", "float", "double", "duration", "dateTime",
                                         "time", "date", "gYearMonth", "gYear", "gMonthDay", "gDay", "gMonth",
                                         "hexBinary", "base64Binary", "anyURI", "QName", "NOTATION",
                                         "normalizedString", "token", "language", "NMTOKEN", "NMTOKENS", "Name",
                                         "NCName", "ID", "IDREF", "IDREFS", "ENTITY", "ENTITIES", "integer",
                                         "nonPositiveInteger", "negativeInteger", "long", "int", "short", "byte",
                                         "nonNegativeInteger", "unsignedLong", "unsignedInt", "unsignedShort",
                                         "unsignedByte", "positiveInteger"))

_PATTERN_ASCII = re_compile(r'^(?%s)\S+$' % 'a' if PY3 else '')
_PATTERN_LEAD_TRAIL_WHITESPACE = re_compile(r'^(?u)\s.*|.*\s$')
_PATTERN_WHITESPACE = re_compile(r'^(?u).*\s.*$')
_PATTERN_LANGUAGE = re_compile(r'^(?%si)[a-z]{2}$' % 'a' if PY3 else '')
_PATTERN_WORD = re_compile(r'^(?u)\w+$')
# For e.g. splitting search text into individual words. Do not pick words surrounded by non-whitespace characters
_PATTERN_WORDS = re_compile(r'(?u)(?<!\S)\w+(?!\S)')
# for validating fqdn/ip and path of a url (cannot contain whitespace, minimum length)
_PATTERN_URL_PART = re_compile(r'^(?u)\S{3}\S*$')

_LOCATION_SEARCH_ARGS = frozenset(('lat', 'long', 'radius'))


class Validation(object):

    @staticmethod
    def check_convert_string(obj, name=None,
                             no_leading_trailing_whitespace=True,
                             no_whitespace=False,
                             no_newline=True,
                             whole_word=False,
                             min_len=1,
                             max_len=0):
        """Ensures the provided object can be interpreted as a unicode string, optionally with
           additional restrictions imposed. By default this means a non-zero length string
           which does not begin or end in whitespace."""
        if not name:
            name = 'Argument'
        obj = ensure_unicode(obj, name=name)
        if no_whitespace:
            if _PATTERN_WHITESPACE.match(obj):
                raise ValueError('%s cannot contain whitespace' % name)
        elif no_leading_trailing_whitespace and _PATTERN_LEAD_TRAIL_WHITESPACE.match(obj):
            raise ValueError('%s contains leading/trailing whitespace' % name)
        if (min_len and len(obj) < min_len) or (max_len and len(obj) > max_len):
            raise ValueError('%s too short/long (%d/%d)' % (name, min_len, max_len))
        if whole_word:
            if not _PATTERN_WORD.match(obj):
                raise ValueError('%s can only contain alphanumeric (unicode) characters, numbers and the underscore'
                                 % name)
        # whole words cannot contain newline so additional check not required
        elif no_newline and '\n' in obj:
            raise ValueError('%s cannot contain line breaks' % name)
        return obj

    @classmethod
    def lid_check_convert(cls, lid):
        return cls.check_convert_string(lid, 'lid', max_len=VALIDATION_LID_LEN)

    @classmethod
    def pid_check_convert(cls, lid):
        return cls.check_convert_string(lid, 'pid', max_len=VALIDATION_LID_LEN)

    @staticmethod
    def guid_check_convert(guid, allow_none=False):
        """Take a GUID in the form of hex string "32" or "8-4-4-4-12".
        Returns hex string "32" or raises ValueError: badly formed hexadecimal UUID string
        """
        if isinstance(guid, string_types):
            return ensure_unicode(UUID(guid).hex)
        elif guid is None and allow_none:
            return None
        else:
            raise ValueError('guid must be a string')

    @staticmethod
    def limit_offset_check(limit, offset):
        if not (isinstance(limit, int_types) and limit >= 0 and
                isinstance(offset, int_types) and offset >= 0):
            raise ValueError("limit/offset invalid")

    @staticmethod
    def metafmt_check_convert(fmt):
        fmt = ensure_unicode(fmt, name='fmt')
        if fmt not in VALIDATION_META_FMT:
            raise ValueError("metadata fmt must be one of of %s" % VALIDATION_META_FMT)
        return fmt

    @classmethod
    def tags_check_convert(cls, tags):
        """Accept one tag as string or multiple tags in list of strings.
        Returns list (with tags in unicode form) or raises ValueError
        """
        # single string check comes first since string is also a Sequence
        if isinstance(tags, string_types):
            return [cls.__tag_check_convert(tags)]
        elif isinstance(tags, Sequence):
            if not len(tags):
                raise ValueError("Tag list is empty")
            return [cls.__tag_check_convert(tag) for tag in tags]
        else:
            raise ValueError("tags must be a single string or list of sequence of strings")

    @classmethod
    def __tag_check_convert(cls, tag):
        return cls.check_convert_string(tag, 'tags', no_whitespace=True, whole_word=True,
                                        min_len=VALIDATION_META_TAG_MIN, max_len=VALIDATION_META_TAG_MAX)

    @staticmethod
    def bool_check_convert(bname, barg):  # pylint: disable=unused-argument
        """Currently does no checking - passthrough for now in case people change their minds"""
        return bool(barg)

    @classmethod
    def lang_check_convert(cls, lang, allow_none=False, default=None):
        if lang is None:
            if allow_none:
                return None
            else:
                lang = default
        lang = ensure_unicode(lang, name='lang')
        if not _PATTERN_LANGUAGE.match(lang):
            raise ValueError('Language should only contain a-z characters')
        return lang

    @classmethod
    def mime_check_convert(cls, mime, allow_none=False):
        if mime is None and allow_none:
            return None
        else:
            mime = ensure_ascii(mime, name='mime')
            if 1 < len(mime) < VALIDATION_MIME_LEN:
                return mime
            else:
                raise ValueError('mime too long (%d)' % VALIDATION_MIME_LEN)

    @staticmethod
    def foc_check(foc):
        if foc not in VALIDATION_FOC_TYPES:
            raise ValueError("Resource type invalid expected one of %s" % VALIDATION_FOC_TYPES)

    @classmethod
    def label_check_convert(cls, label, allow_none=False):
        if label is None and allow_none:
            return None
        else:
            return cls.check_convert_string(label, 'label', max_len=VALIDATION_META_LABEL)

    @classmethod
    def comment_check_convert(cls, comment, allow_none=False):
        if comment is None and allow_none:
            return None
        else:
            return cls.check_convert_string(comment, 'comment', max_len=VALIDATION_META_COMMENT, no_newline=False)

    description_check_convert = comment_check_convert

    @staticmethod
    def value_type_check_convert(vtype):
        vtype = ensure_unicode(vtype, name='vtype')
        if vtype not in VALIDATION_META_VALUE_TYPES:
            raise ValueError("value type not a valid xsd primitive (or derived) type name")
        return vtype

    @classmethod
    def value_unit_check_convert(cls, unit):
        if unit is None:
            return None
        unit = ensure_unicode(unit, name='unit')
        if len(unit) > VALIDATION_META_VALUE_UNIT:
            raise ValueError('unit too long (%d)' % VALIDATION_META_VALUE_UNIT)
        if cls.__valid_url(unit):
            return unit
        else:
            raise ValueError('unit does not resemble valid http(s) url')

    @classmethod
    def __valid_url(cls, url):
        """Expects input to already be a valid string"""
        bits = urlparse(url)
        return ((bits.scheme == "http" or bits.scheme == "https") and
                _PATTERN_URL_PART.match(bits.netloc) and
                _PATTERN_URL_PART.match(bits.path))

    @staticmethod
    def location_check(lat, lon):
        """For use by Core client wrappers"""
        if not (isinstance(lat, number_types) and -90 <= lat <= 90):
            raise ValueError("Latitude: '{latitude}' invalid".format(latitude=lat))

        if not (isinstance(lon, number_types) and -180 <= lon <= 180):
            raise ValueError("Longitude: '{longitude}' invalid".format(longitude=lon))

    @classmethod
    def search_location_check(cls, location):
        """Core.Client.request_search location parameter should be a dictionary that contains lat, lon and radius floats
        """
        if not (isinstance(location, Mapping) and set(location.keys()) == _LOCATION_SEARCH_ARGS):
            raise ValueError('Search location should be mapping with keys: %s' % _LOCATION_SEARCH_ARGS)

        cls.location_check(location['lat'], location['long'])
        radius = location['radius']
        if not (isinstance(radius, number_types) and 0 < radius <= 20038):  # half circumference
            raise ValueError("Radius: '{radius}' is invalid".format(radius=radius))

    @classmethod
    def search_check_convert(cls, text, lang, location, unit, default_lang):
        arg_count = 0
        payload = {}
        if text is not None:
            payload['text'] = cls.__search_text_check_convert(text)
            arg_count += 1
        else:
            raise ValueError('text parameter required for search')

        payload['lang'] = cls.lang_check_convert(lang, default=default_lang)

        if location is not None:
            cls.search_location_check(location)
            payload.update(location)
            arg_count += 1

        if unit is not None:
            payload['unit'] = cls.value_unit_check_convert(unit)
            arg_count += 1

        # NOTE: This check is for future use once text is optional - currently this will not trigger
        if not arg_count:
            raise ValueError('At least one of text, location and unit must be specified')

        return payload

    @staticmethod
    def search_type_check_convert(type_):
        type_ = ensure_ascii(type_, name='type_')
        if type_ not in VALIDATION_SEARCH_TYPES:
            raise ValueError('Search type must be one of: %s' % VALIDATION_SEARCH_TYPES)
        return type_

    @classmethod
    def __search_text_check_convert(cls, text):
        """Converts and keeps only words in text deemed to be valid"""
        text = cls.check_convert_string(text, name='text', no_leading_trailing_whitespace=False)
        if len(text) > VALIDATION_META_SEARCH_TEXT:
            raise ValueError("Search text can contain at most %d characters" % VALIDATION_META_SEARCH_TEXT)
        text = ' '.join(_PATTERN_WORDS.findall(text))
        if not text:
            raise ValueError('Search text must contain at least one non-whitespace term (word)')
        return text

    @staticmethod
    def callable_check(func, arg_count=1, arg_value=None, allow_none=False):
        """Check whether func is callable, with the given number of positional arguments. Returns True if check
           succeeded, False otherwise."""
        if func is None:
            if not allow_none:
                raise ValueError('callable cannot be None')
        elif not arg_checker(func, *[arg_value for _ in range(arg_count)]):
            raise ValueError('callable %s invalid (for %d arguments)' % (func, arg_count))
