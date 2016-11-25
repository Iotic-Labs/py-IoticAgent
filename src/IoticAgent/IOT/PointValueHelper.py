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
"""Shareable object helper classes
"""

from __future__ import unicode_literals

from collections import namedtuple
import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.compat import Sequence, Lock, valid_identifier

from .Exceptions import IOTUnknown
from .Point import Point, PointDataObject
from .RemotePoint import RemotePoint
from .utils import private_names_for


class Value(object):
    """Represent data and metadata for a single value. NOT thread safe."""

    __slots__ = tuple(private_names_for('Value', ('__label', '__type', '__unit', '__description', '__unset',
                                                  '__value')))

    def __init__(self, label, type_, unit=None, description=None):
        self.__label = label
        self.__type = type_
        self.__unit = unit
        self.__description = description
        self.__unset = True
        self.__value = None

    @property
    def unset(self):
        """Whether this value instances has had data assigned to it"""
        return self.__unset

    @property
    def label(self):
        """Label for this value"""
        return self.__label

    @property
    def type_(self):
        """Value type, e.g. one of IoticAgent.Datatypes"""
        return self.__type

    @property
    def unit(self):
        """Value unit, e.g. one of IoticAgent.Units"""
        return self.__unit

    @property
    def description(self):
        """Human-readable description of this value"""
        return self.__description

    @property
    def value(self):
        """Data for this value. Returns None if it hasn't been set. To distinguish between None and
        and unset, check the `unset` property."""
        return self.__value

    @value.setter
    def value(self, value):
        self.__unset = False
        self.__value = value

    @value.deleter
    def value(self):
        self.__unset = True
        self.__value = None

    def copy(self):
        return Value(self.__label, self.__type, self.__unit, self.__description)


class _ValueFilter(namedtuple('nt__ValueFilter', 'by_type by_unit')):
    """Used by PointDataObject to present a subset of values."""

    def __new__(cls, by_type, by_unit):
        return super(_ValueFilter, cls).__new__(cls,
                                                {name: frozenset(values) for name, values in by_type.items()},
                                                {name: frozenset(values) for name, values in by_unit.items()})

    def filter_by(self, types=(), units=()):
        """Return list of value labels, filtered by either or both type and unit. An empty
        sequence for either argument will match as long as the other argument matches any values."""
        if not (isinstance(types, Sequence) and isinstance(units, Sequence)):
            raise TypeError('types/units must be a sequence')
        empty = frozenset()

        if types:
            type_names = set()
            for type_ in types:
                type_names |= self.by_type.get(type_, empty)
            if not units:
                return type_names

        if units:
            unit_names = set()
            for unit in units:
                unit_names |= self.by_unit.get(unit, empty)
            if not types:
                return unit_names

        return (type_names & unit_names) if (types and units) else empty


class PointDataObjectHandler(object):
    """Caches metadata for a point and produces skeletal represenation of a point's values, optionally populating it
    with data from a share/ask/tell. Threadsafe."""

    class _RefreshException(Exception):
        """Raised by __refresh() to indicate metadata unsuitable for template usage."""
        pass

    __slots__ = tuple(private_names_for('PointDataObjectHandler', ('__remote', '__point', '__last_parse_ok', '__client',
                                                                   '__lock', '__value_templates', '__filter')))

    def __init__(self, point, client):
        """point - instance of Point, RemoteFeed or RemoteControl or a valid GUID
           client - instance of IOT.Client
        """
        # remote => use describe, non-remote => use point value listing
        if isinstance(point, Point):
            self.__remote = False
            self.__point = point
        elif isinstance(point, RemotePoint):
            self.__point = point.guid
            self.__remote = True
        else:
            self.__point = Validation.guid_check_convert(point)
            self.__remote = True

        self.__lock = Lock()
        self.__client = client
        # flag to prevent repeated fetching of value metadata
        self.__last_parse_ok = True
        self.__value_templates = None
        self.__filter = None

    def get_template(self, data=None):  # noqa (complexity)
        """Get new template which represents the values of this point in a
        [PointDataObject](./Point.m.html#IoticAgent.IOT.Point.PointDataObject). If data is set (to a dictionary), use
        this to populate the created template."""
        with self.__lock:
            if self.__value_templates is None and self.__last_parse_ok:
                try:
                    self.__refresh()
                except self._RefreshException:
                    # Point has no (useable) values - don't try to refetch again
                    self.__last_parse_ok = False
                    raise
            if self.__value_templates is None:
                raise ValueError('Point has no values')
            if data is None:
                template = PointDataObject(self.__value_templates, self.__filter)
            else:
                while True:
                    try:
                        template = PointDataObject._from_dict(self.__value_templates, self.__filter, data)
                    except:
                        # parsing has failed for first time since refresh so try again
                        if self.__last_parse_ok:
                            logger.warning('Failed to parse data from for point %s, refreshing', self.__point)
                            self.__last_parse_ok = False
                            try:
                                self.__refresh()
                            except self._RefreshException:
                                break
                        else:
                            raise
                    else:
                        self.__last_parse_ok = True
                        break
            return template

    def __refresh(self):
        """Update local knowledge of values (to be used to create new skeletal instances). MUST be called within
        lock."""
        raw_values = self.__get_values()
        if not raw_values:
            raise self._RefreshException('Point has no values')

        # individual templates
        templates = []
        # lookup tables by type and unit of value
        by_type = {}
        by_unit = {}

        for raw_value in raw_values:
            label = raw_value['label']
            if not valid_identifier(label) or label.startswith('__'):
                raise self._RefreshException('Value "%s" unsuitable for object wrapper' % label)
            value = Value(label, raw_value['type'], raw_value['unit'], raw_value['comment'])
            templates.append(value)
            try:
                by_type[value.type_].add(label)
            except KeyError:
                by_type[value.type_] = {label}
            if value.unit:
                try:
                    by_unit[value.unit].add(label)
                except KeyError:
                    by_unit[value.unit] = {label}

        self.__value_templates = templates
        self.__filter = _ValueFilter(by_type, by_unit)

    def __get_values(self):
        """Retrieve value information either via describe or point value listing. MUST be called within lock."""
        values = []

        if self.__remote:
            description = self.__client.describe(self.__point)
            if description is not None:
                if description['type'] != 'Point':
                    raise IOTUnknown('%s is not a Point' % self.__point)
                values = description['meta']['values']
        else:
            limit = 100
            offset = 0
            while True:
                new = self.__point.list(limit=limit, offset=offset)
                values += new
                if len(new) < limit:
                    break
                offset += limit

        return values
