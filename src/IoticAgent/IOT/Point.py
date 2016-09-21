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
"""Wrapper object for Iotic Points.
Points are come in two types:

`Feed`s where they output data from a Thing

`Control`s where they are a way of sending data to a Thing
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.Const import R_FEED, R_CONTROL
from IoticAgent.Core.compat import Sequence, Mapping, raise_from, string_types, ensure_unicode

from .utils import private_names_for, foc_to_str

try:
    from .PointMeta import PointMeta
except ImportError:
    PointMeta = None


_POINT_TYPES = frozenset((R_FEED, R_CONTROL))


class Point(object):
    """Point class.  A Point represents either a feed or control.

    `Feeds` are advertised when a Thing has data to share.  They are for out-going data which will get shared with any
    remote Things that have followed them.  Feeds are one-to-many.

    `Controls` are where a Thing invites others to send it data.  Controls can be used to activate some hardware,
    reset counters, change reporting intervals - pretty much anything you want to change the state of a Thing.
    Controls are many-to-one
    """
    def __init__(self, client, foc, lid, pid, guid):
        self.__client = client
        Validation.foc_check(foc)
        self.__foc = foc
        self.__lid = Validation.lid_check_convert(lid)
        self.__pid = Validation.pid_check_convert(pid)
        self.__guid = Validation.guid_check_convert(guid)

    def __hash__(self):
        # Why not just hash guid? Because Point is used before knowing guid in some cases
        # Why not hash without guid? Because in two separate containers one could have identicial points
        # (if not taking guid into account)
        return hash(self.__lid) ^ hash(self.__pid) ^ hash(self.__foc) ^ hash(self.__guid)

    def __eq__(self, other):
        return (isinstance(other, Point) and
                self.__guid == other.__guid and
                self.__foc == other.__foc and
                self.__lid == other.__lid and
                self.__pid == other.__pid)

    def __str__(self):
        return '%s (%s: %s, %s)' % (self.__guid, foc_to_str(self.__foc), self.__lid, self.__pid)

    @property
    def guid(self):
        """The Globally Unique ID of this Point in hex form (undashed).
        """
        return self.__guid

    @property
    def lid(self):
        """The local id of the Thing that advertises this Point.  This is unique to you on this container.
        """
        return self.__lid

    @property
    def pid(self):
        """Point id - the local id of this Point.  This is unique to you on this container.
        Think of it as a nickname for the Point
        """
        return self.__pid

    @property
    def foc(self):
        """Whether this Point is a feed or control.  String of either `"feed"` or `"control"`
        """
        return foc_to_str(self.__foc)

    def rename(self, new_pid):
        """Rename the Point.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `new_pid` (required) (string) the new local identifier of your Point
        """
        logger.info("rename(new_pid=\"%s\") [lid=%s, pid=%s]", new_pid, self.__lid, self.__pid)
        evt = self.__client._request_point_rename(self.__foc, self.__lid, self.__pid, new_pid)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)
        self.__pid = new_pid

    def list(self, limit=50, offset=0):
        """List `all` the values on this Point.

        Returns QAPI list function payload

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `limit` (optional) (integer) Return this many value details

        `offset` (optional) (integer) Return value details starting at this offset
        """
        logger.info("list(limit=%s, offset=%s) [lid=%s,pid=%s]", limit, offset, self.__lid, self.__pid)
        evt = self.__client._request_point_value_list(self.__lid, self.__pid, self.__foc, limit=limit, offset=offset)
        evt.wait(self.__client.sync_timeout)

        self.__client._except_if_failed(evt)
        return evt.payload['values']

    def list_followers(self):
        """list followers for this Point This includes remote follows and remote attaches

        Returns QAPI list function payload

            #!python
            {
                "<Subscription GUID 1>": "<GUID of follower1>",
                "<Subscription GUID 2>": "<GUID of follower2>"
            }

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

         `limit` (optional) (integer) Return this many value details

        `offset` (optional) (integer) Return value details starting at this offset
        """
        evt = self.__client._request_point_list_detailed(self.__foc, self.__lid, self.__pid)
        evt.wait(self.__client.sync_timeout)

        self.__client._except_if_failed(evt)
        return evt.payload['subs']

    def get_template(self):
        """Get new [PointDataObject](./PointValueHelper.m.html#IoticAgent.IOT.PointValueHelper.PointDataObject) instance
        to use for sharing data."""
        return self.__client._get_point_data_handler_for(self).get_template()

    def share(self, data, mime=None):
        """Share some data from this Point

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `data` (mandatory) (as applicable) The data you want to share

        `mime` (optional) (string) The mime type of the data you're sharing.  There are some
        Iotic Labs-defined default values:

        `"idx/1"` - Corresponds to "application/ubjson" - the recommended way to send mixed data.
        Share a python dictionary as the data and the agent will to the encoding and decoding for you.

            #!python
            data = {}
            data["timestamp"] = datetime.datetime.now().isoformat()
            data["temperature"] = self._convert_to_celsius(ADC.read(1))
            # ...etc...
            my_feed.share(data)

        `"idx/2"` Corresponds to "text/plain" - the recommended way to send "byte" data.
        Share a utf8 string as data and the agent will pass it on, unchanged.

            #!python
            my_feed.share("string data".encode('utf8'), mime="idx/2")

        `"text/xml"` or any other valid mime type.  To show the recipients that
         you're sending something more than just bytes

            #!python
            my_feed.share("<xml>...</xml>".encode('utf8'), mime="text/xml")
        """
        logger.info("share() [lid=\"%s\",pid=\"%s\"]", self.__lid, self.__pid)
        if self.__foc != R_FEED:
            raise TypeError('Only feeds can share (this is a %s)' % self.foc)
        if mime is None and isinstance(data, PointDataObject):
            data = data.to_dict()
        evt = self.__client._request_point_share(self.__lid, self.__pid, data, mime)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def share_async(self, data, mime=None):
        logger.info("share_async() [lid=\"%s\",pid=\"%s\"]", self.__lid, self.__pid)
        if mime is None and isinstance(data, PointDataObject):
            data = data.to_dict()
        return self.__client._request_point_share(self.__lid, self.__pid, data, mime)

    def get_meta(self):
        """Get the metadata object for this Point

        Returns a [PointMeta](PointMeta.m.html#IoticAgent.IOT.PointMeta.PointMeta) object - OR -

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        Raises `RuntimeError` if RDFLib is not installed or not available
        """
        if PointMeta is None:
            raise RuntimeError("PointMeta not available")
        rdf = self.get_meta_rdf(fmt='n3')
        return PointMeta(self, rdf, self.__client.default_lang, fmt='n3')

    def get_meta_rdf(self, fmt='n3'):
        """Get the metadata for this Point in rdf fmt

        Advanced users who want to manipulate the RDF for this Point directly without the
        [PointMeta](PointMeta.m.html#IoticAgent.IOT.PointMeta.PointMeta) helper object

        Returns the RDF in the format you specify. - OR -

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `fmt` (optional) (string) The format of RDF you want returned.
        Valid formats are: "xml", "n3", "turtle"
        """
        evt = self.__client._request_point_meta_get(self.__foc, self.__lid, self.__pid, fmt=fmt)
        evt.wait(self.__client.sync_timeout)

        self.__client._except_if_failed(evt)
        return evt.payload['meta']

    def set_meta_rdf(self, rdf, fmt='n3'):
        """Set the metadata for this Point in rdf fmt
        """
        evt = self.__client._request_point_meta_set(self.__foc, self.__lid, self.__pid, rdf, fmt=fmt)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def create_tag(self, tags, lang=None):
        """Create tags for a Point in the language you specify. Tags can only contain alphanumeric (unicode) characters
        and the underscore. Tags will be stored lower-cased.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        tags (mandatory) (list) - the list of tags you want to add to your Point, e.g.
        ["garden", "soil"]

        `lang` (optional) (string) Default `None`.  The two-character ISO 639-1 language code to use for your label.
        None means use the default language for your agent.
        See [Config](./Config.m.html#IoticAgent.IOT.Config.Config.__init__)
        """
        if isinstance(tags, str):
            tags = [tags]

        evt = self.__client._request_point_tag_create(self.__foc, self.__lid, self.__pid, tags, lang, delete=False)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def delete_tag(self, tags, lang=None):
        """Delete tags for a Point in the language you specify. Case will be ignored and any tags matching lower-cased
        will be deleted.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `tags` (mandatory) (list) - the list of tags you want to delete from your Point, e.g.
        ["garden", "soil"]

        `lang` (optional) (string) The two-character ISO 639-1 language code to use for your label.
        None means use the default language for your agent.
        See [Config](./Config.m.html#IoticAgent.IOT.Config.Config.__init__)
        """
        if isinstance(tags, str):
            tags = [tags]

        evt = self.__client._request_point_tag_delete(self.__foc, self.__lid, self.__pid, tags, lang)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def list_tag(self, limit=50, offset=0):
        """List `all` the tags for this Point

        Returns tag dictionary of lists of tags keyed by language. As below

            #!python
            {
                "en": [
                    "mytag1",
                    "mytag2"
                ],
                "de": [
                    "ein_name",
                    "nochein_name"
                ]
            }

        - OR...

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `limit` (optional) (integer) Return at most this many tags

        `offset` (optional) (integer) Return tags starting at this offset
        """
        evt = self.__client._request_point_tag_list(self.__foc, self.__lid, self.__pid, limit=limit, offset=offset)
        evt.wait(self.__client.sync_timeout)

        self.__client._except_if_failed(evt)
        return evt.payload['tags']

    def create_value(self, label, vtype, lang=None, description=None, unit=None):
        """Create a value on this Point.  Values are descriptions in semantic metadata of the individual data items
        you are sharing (or expecting to receive, if this Point is a control).  This will help others to search for
        your feed or control. If a value with the given label (and language) already exists, its fields are updated
        with the provided ones (or unset, if None).

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `label` (mandatory) (string) the label for this value e.g. "Temperature".  The label must be unique for this
        Point.  E.g. You can't have two data values called "Volts" but you can have "volts1" and "volts2".

        `lang` (optional) (string) The two-character ISO 639-1 language code to use for your label.
        None means use the default language for your agent.
        See [Config](./Config.m.html#IoticAgent.IOT.Config.Config.__init__)

        `vtype` (mandatory) (xsd:datatype) the datatype of the data you are describing, e.g. dateTime
        We recommend you use a Iotic Labs-defined constant from
        [Datatypes](../Datatypes.m.html#IoticAgent.Datatypes.Datatypes) such as:
        [DECIMAL](../Datatypes.m.html#IoticAgent.Datatypes.DECIMAL)

        `description` (optional) (string) The longer descriptive text for this value.

        `unit` (optional) (ontology url) The url of the ontological description of the unit of your value
        We recommend you use a constant from  [Units](../Units.m.html#IoticAgent.Units.Units), such as:
        [CELSIUS](../Units.m.html#IoticAgent.Units.Units.CELSIUS)

            #!python
            # example with no units as time is unit-less
            my_feed.value_create("timestamp",
                                 Datatypes.DATETIME,
                                 "en",
                                 "time of reading")

            # example with a unit from the Units class
            my_feed.value_create("temperature",
                                 Datatypes.DECIMAL,
                                 "en",
                                 "Fish-tank temperature in celsius",
                                 Units.CELSIUS)
        """
        evt = self.__client._request_point_value_create(self.__lid, self.__pid, self.__foc, label, vtype, lang,
                                                        description, unit)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def delete_value(self, label, lang=None):
        """Delete the labelled value on this Point

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `label` (mandatory) (string) the label for the value you want to delete

        `lang` (optional) (string) The two-character ISO 639-1 language code to use for your label.
        None means use the default language for your agent.
        See [Config](./Config.m.html#IoticAgent.IOT.Config.Config.__init__)
        """
        evt = self.__client._request_point_value_delete(self.__lid, self.__pid, self.__foc, label, lang)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)


class PointDataObject(object):
    """Represents a point data reading or template for filling in values, ready to be e.g. shared. NOT threadsafe."""

    __slots__ = tuple(private_names_for('PointDataObject', ('__values', '__filter')))

    def __init__(self, values, value_filter):
        """Instantiated by
        [PointDataObjectHandler](./PointValueHelper.m.html#IoticAgent.IOT.PointValueHelper.PointDataObjectHandler)"""
        self.__values = _PointValueWrapper(values)
        self.__filter = value_filter

    @property
    def values(self):
        """List of all values"""
        return self.__values

    def unset(self):
        """Unsets all values"""
        for value in self.__values:
            del value.value

    @property
    def missing(self):
        """List of values which do not have a value set yet"""
        return [value for value in self.__values if value.unset]

    def filter_by(self, text=(), types=(), units=(), include_unset=False):
        """Return subset of values which match the given text, types and/or units. For a value to be matched, at least
        one item from each specified filter category has to apply to a value. Each of the categories must be specified
        as a sequence of strings. If `include_unset` is set, unset values will also be considered."""
        if not (isinstance(text, Sequence) and all(isinstance(phrase, string_types) for phrase in text)):
            raise TypeError('text should be sequence of strings')
        values = ([self.__values[name] for name in self.__filter.filter_by(types=types, units=units)
                   if include_unset or not self.__values[name].unset]
                  if types or units else self.__values)
        if text:
            # avoid unexpected search by individual characters if a single string was specified
            if isinstance(text, string_types):
                text = (ensure_unicode(text),)
            text = [phrase.lower() for phrase in text]
            values = [value for value in values
                      if any((phrase in value.label or phrase in value.description) for phrase in text)]
        return values

    def to_dict(self):
        """Converts the set of values into a dictionary. Unset values are excluded."""
        return {value.label: value.value for value in self.__values if not value.unset}

    @classmethod
    def _from_dict(cls, values, value_filter, dictionary, allow_unset=True):
        """Instantiates new PointDataObject, populated from the given dictionary. With allow_unset=False, a ValueError
        will be raised if any value has not been set. Used by PointDataObjectHandler"""
        if not isinstance(dictionary, Mapping):
            raise TypeError('dictionary should be mapping')
        obj = cls(values, value_filter)
        values = obj.__values
        for name, value in dictionary.items():
            if not isinstance(name, string_types):
                raise TypeError('Key %s is not a string' % str(name))
            setattr(values, name, value)
        if obj.missing and not allow_unset:
            raise ValueError('%d value(s) are unset' % len(obj.missing))
        return obj


class _PointValueWrapper(object):
    """Encapsulates a set of values, accessible by their label as well as an iterator. NOT threadsafe.

    pvw = PointValueWrapper(SEQUENCE_OF_VALUES)
    # This will produce a ValueError if the value has not been set yet
    print(pvw.some_value)
    pvw.some_value = 2
    print(pvw.some_value)

    for value in pvw:
        print('%s - %s' % (value.label, value.description))

    The whole value object can also be retrieved via key access:

    print(pvw['some_value'].value)
    """

    __slots__ = tuple(private_names_for('_PointValueWrapper', ('__values',)))

    def __init__(self, values):
        self.__values = {value.label: value.copy() for value in values}

    def __iter__(self):
        return iter(self.__values.values())

    def __getattr__(self, name):
        try:
            return self.__values[name].value
        except KeyError as ex:
            raise_from(AttributeError('no such value'), ex)

    def __getitem__(self, key):
        try:
            return self.__values[key]
        except KeyError as ex:
            raise_from(KeyError('no such value'), ex)

    def __setattr__(self, name, value):
        # private attributes belonging to class
        if name.startswith('_PointValueWrapper__'):
            super(_PointValueWrapper, self).__setattr__(name, value)
        else:
            try:
                self.__values[name].value = value
            except KeyError as ex:
                raise_from(AttributeError('no such value'), ex)

    def __delattr__(self, name):
        try:
            del self.__values[name].value
        except KeyError as ex:
            raise_from(AttributeError('no such value'), ex)
