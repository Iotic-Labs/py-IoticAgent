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
"""
Wrapper object for Iotic Points.

Points are come in two types:

* Feed's where they output data from a Thing
* Control's where they are a way of sending data to a Thing
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.Const import R_FEED, R_CONTROL
from IoticAgent.Core.compat import Sequence, Mapping, raise_from, string_types, ensure_unicode

from .Resource import Resource
from .utils import private_names_for, foc_to_str
from .PointMeta import PointMeta

_POINT_TYPES = frozenset((R_FEED, R_CONTROL))


class Point(Resource):

    # overridden by subclasses (e.g. R_FEED)
    _type = None

    """
    Point class. A base class for feed or control.
    """
    def __init__(self, client, lid, pid, guid):
        if self._type not in _POINT_TYPES:
            raise TypeError('_type not set to a valid point type')
        super(Point, self).__init__(client, guid)
        self.__lid = Validation.lid_check_convert(lid)
        self.__pid = Validation.pid_check_convert(pid)

    def __hash__(self):
        # Why not just hash guid? Because Point is used before knowing guid in some cases
        # Why not hash without guid? Because in two separate containers one could have identicial points
        # (if not taking guid into account)
        return hash(self.__lid) ^ hash(self.__pid) ^ hash(self._type) ^ hash(self.guid)

    def __eq__(self, other):
        return (isinstance(other, Point) and
                self.guid == other.guid and
                self._type == other._type and
                self.__lid == other.__lid and
                self.__pid == other.__pid)

    def __str__(self):
        return '%s (%s: %s, %s)' % (self.guid, foc_to_str(self._type), self.__lid, self.__pid)

    @property
    def lid(self):
        """
        The local id of the Thing that advertises this Point.  This is unique to you on this container.
        """
        return self.__lid

    @property
    def pid(self):
        """
        Point id - the local id of this Point.  This is unique to you on this container.
        Think of it as a nickname for the Point
        """
        return self.__pid

    @property
    def foc(self):
        """
        Whether this Point is a feed or control.  String of either `"feed"` or `"control"`
        """
        return foc_to_str(self._type)

    def rename(self, new_pid):
        """
        Rename the Point.

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            new_pid (string): The new local identifier of your Point
        """
        logger.info("rename(new_pid=\"%s\") [lid=%s, pid=%s]", new_pid, self.__lid, self.__pid)
        evt = self._client._request_point_rename(self._type, self.__lid, self.__pid, new_pid)
        self._client._wait_and_except_if_failed(evt)
        self.__pid = new_pid

    def list(self, limit=50, offset=0):
        """
        List `all` the values on this Point.

        Returns:
            QAPI list function payload

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            limit (integer, optional): Return this many value details
            offset (integer, optional): Return value details starting at this offset
        """
        logger.info("list(limit=%s, offset=%s) [lid=%s,pid=%s]", limit, offset, self.__lid, self.__pid)
        evt = self._client._request_point_value_list(self.__lid, self.__pid, self._type, limit=limit, offset=offset)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['values']

    def list_followers(self):
        """
        List followers for this point, i.e. remote follows for feeds and remote attaches for controls.

        Returns:
            QAPI subscription list function payload

        ::

            {
                "<Subscription GUID 1>": "<GUID of follower1>",
                "<Subscription GUID 2>": "<GUID of follower2>"
            }

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            limit (integer, optional): Return this many value details
            offset (integer, optional): Return value details starting at this offset
        """
        evt = self._client._request_point_list_detailed(self._type, self.__lid, self.__pid)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['subs']

    def get_meta(self):
        """
        Get the metadata object for this Point

        Returns:
            A :doc:`IoticAgent.IOT.PointMeta` PointMeta object

        **OR**

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure
        """
        rdf = self.get_meta_rdf(fmt='n3')
        return PointMeta(self, rdf, self._client.default_lang, fmt='n3')

    def get_meta_rdf(self, fmt='n3'):
        """
        Get the metadata for this Point in rdf fmt

        Advanced users who want to manipulate the RDF for this Point directly without the
        :doc:`IoticAgent.IOT.PointMeta` PointMeta)helper object

        Returns:
            The RDF in the format you specify.

        **OR**

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            fmt (string, optional): The format of RDF you want returned. Valid formats are: "xml", "n3", "turtle"
        """
        evt = self._client._request_point_meta_get(self._type, self.__lid, self.__pid, fmt=fmt)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['meta']

    def set_meta_rdf(self, rdf, fmt='n3'):
        """
        Set the metadata for this Point in rdf fmt
        """
        evt = self._client._request_point_meta_set(self._type, self.__lid, self.__pid, rdf, fmt=fmt)
        self._client._wait_and_except_if_failed(evt)

    def create_tag(self, tags):
        """
        Create tags for a Point in the language you specify. Tags can only contain alphanumeric (unicode) characters
        and the underscore. Tags will be stored lower-cased.

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            tags (list): The list of tags you want to add to your Point, e.g. ["garden", "soil"]
        """
        if isinstance(tags, str):
            tags = [tags]

        evt = self._client._request_point_tag_update(self._type, self.__lid, self.__pid, tags, delete=False)
        self._client._wait_and_except_if_failed(evt)

    def delete_tag(self, tags):
        """
        Delete tags for a Point in the language you specify. Case will be ignored and any tags matching lower-cased
        will be deleted.

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            tags (list): The list of tags you want to delete from your Point, e.g. ["garden", "soil"]
        """
        if isinstance(tags, str):
            tags = [tags]

        evt = self._client._request_point_tag_update(self._type, self.__lid, self.__pid, tags, delete=True)
        self._client._wait_and_except_if_failed(evt)

    def list_tag(self, limit=50, offset=0):
        """
        List `all` the tags for this Point

        Returns:
            List of tags, as below

        ::

            [
                "mytag1",
                "mytag2"
                "ein_name",
                "nochein_name"
            ]

        **OR**

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            limit (integer, optional): Return at most this many tags
            offset (integer, optional): Return tags starting at this offset
        """
        evt = self._client._request_point_tag_list(self._type, self.__lid, self.__pid, limit=limit, offset=offset)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['tags']

    def create_value(self, label, vtype, lang=None, description=None, unit=None):
        """
        Create a value on this Point.  Values are descriptions in semantic metadata of the individual data items
        you are sharing (or expecting to receive, if this Point is a control).  This will help others to search for
        your feed or control. If a value with the given label (and language) already exists, its fields are updated
        with the provided ones (or unset, if None).

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            label (string): The label for this value e.g. "Temperature".  The label must be unique for this
                Point.  E.g. You can't have two data values called "Volts" but you can have "volts1" and "volts2".
            lang (string, optional): The two-character ISO 639-1 language code to use for the description. None means
                use the default language for your agent. See :doc:`IoticAgent.IOT.Config`
            vtype (xsd:datatype): The datatype of the data you are describing, e.g. dateTime. We recommend
                you use a Iotic Labs-defined constant from :doc:`IoticAgent.Datatypes`
            description (string, optional): The longer descriptive text for this value.
            unit (ontology url, optional): The url of the ontological description of the unit of your value. We
                recommend you use a constant from :doc:`IoticAgent.Units`

        ::

            # example with no units as time is unit-less
            my_feed.create_value("timestamp",
                                 Datatypes.DATETIME,
                                 "en",
                                 "time of reading")

        ::

            # example with a unit from the Units class
            my_feed.create_value("temperature",
                                 Datatypes.DECIMAL,
                                 "en",
                                 "Fish-tank temperature in celsius",
                                 Units.CELSIUS)
        """
        evt = self._client._request_point_value_create(self.__lid, self.__pid, self._type, label, vtype, lang,
                                                       description, unit)
        self._client._wait_and_except_if_failed(evt)

    def delete_value(self, label=None):
        """
        Delete the labelled value (or all values) on this Point

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            label (string, optional): The label for the value you want to delete. If not specified, all values for this
                point will be removed.
        """
        evt = self._client._request_point_value_delete(self.__lid, self.__pid, self._type, label=label)
        self._client._wait_and_except_if_failed(evt)


class Feed(Point):
    """
    `Feeds` are advertised when a Thing has data to share.  They are for out-going data which will get shared with
    any remote Things that have followed them.  Feeds are one-to-many.
    """
    _type = R_FEED

    def get_template(self):
        """
        Get new :doc:`IoticAgent.IOT.PointValueHelper` PointDataObject instance to use for sharing data.
        """
        return self._client._get_point_data_handler_for(self).get_template()

    def share(self, data, mime=None, time=None):
        """
        Share some data from this Feed

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            data: The data you want to share
            time (datetime): UTC time for this share. If not specified, the container's time will be used.
                Thus it makes almost no sense to specify `datetime.utcnow()` here. This parameter can be used to
                indicate that the share time does not correspond to the time to which the data applies, e.g. to populate
                recent storage with historical data.
            mime (string): The mime type of the data you're sharing.  There are some Iotic Labs-defined default values.

        `"idx/1"` corresponds to "application/ubjson" - the recommended way to send mixed data. Share a python
        dictionary as the data and the agent will to the encoding and decoding for you.

        ::

            data = {}
            data["temperature"] = self._convert_to_celsius(ADC.read(1))
            # ...etc...
            my_feed.share(data)

        `"idx/2"` Corresponds to "text/plain" - the recommended way to send textual data.
        Share a utf8 string as data and the agent will pass it on, unchanged.

        ::

            my_feed.share(u"string data")

        `"text/xml"` or any other valid mime type.  To show the recipients that
         you're sending something more than just bytes

        ::

            my_feed.share("<xml>...</xml>".encode('utf8'), mime="text/xml")
        """
        evt = self.share_async(data, mime=mime, time=time)
        self._client._wait_and_except_if_failed(evt)

    def share_async(self, data, mime=None, time=None):
        logger.info("share() [lid=\"%s\",pid=\"%s\"]", self.lid, self.pid)
        if mime is None and isinstance(data, PointDataObject):
            data = data.to_dict()
        return self._client._request_point_share(self.lid, self.pid, data, mime, time)

    def get_recent_info(self):
        """
        Retrieves statistics and configuration about recent storage for this Feed.

        Returns:
            QAPI recent info function payload

        ::

            {
                "maxSamples": 0,
                "count": 0
            }

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure
        """
        evt = self._client._request_point_recent_info(self._type, self.lid, self.pid)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['recent']

    def set_recent_config(self, max_samples=0):
        """
        Update/configure recent data settings for this Feed. If the container does not support recent storage or it
        is not enabled for this owner, this function will have no effect.

        Args:
            max_samples (int, optional): How many shares to store for later retrieval. If not supported by container,
                this argument will be ignored. A value of zero disables this feature whilst a negative value requests
                the maximum sample store amount.

        Returns:
            QAPI recent config function payload

        ::

            {
                "maxSamples": 0
            }

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure
        """
        evt = self._client._request_point_recent_config(self._type, self.lid, self.pid, max_samples)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload


class Control(Point):
    """
    `Controls` are where a Thing invites others to send it data.  Controls can be used to activate some hardware,
    reset counters, change reporting intervals - pretty much anything you want to change the state of a Thing.
    Controls are many-to-one.
    """

    _type = R_CONTROL


class PointDataObject(object):
    """
    Represents a point data reading or template for filling in values, ready to be e.g. shared. NOT threadsafe.
    """

    __slots__ = tuple(private_names_for('PointDataObject', ('__values', '__filter')))

    def __init__(self, values, value_filter):
        """Instantiated by :doc:IoticAgent.IOT.`PointValueHelper` PointDataObjectHandler"""
        self.__values = _PointValueWrapper(values)
        self.__filter = value_filter

    def __bool__(self):
        """Short-hand for empty()"""
        return not self.empty

    @property
    def values(self):
        """List of all values"""
        return self.__values

    def unset(self):
        """Unsets all values"""
        for value in self.__values:
            del value.value

    @property
    def empty(self):
        """
        Returns:
            True if no values have been set yet."""
        return all(value.unset for value in self.__values)

    @property
    def missing(self):
        """List of values which do not have a value set yet"""
        return [value for value in self.__values if value.unset]

    def filter_by(self, text=(), types=(), units=(), include_unset=False):
        """
        Return subset of values which match the given text, types and/or units. For a value to be matched, at least
        one item from each specified filter category has to apply to a value. Each of the categories must be specified
        as a sequence of strings. If `include_unset` is set, unset values will also be considered.
        """
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
            new_values = []
            for value in values:
                label = value.label.lower()
                description = value.description.lower() if value.description else ''
                if any(phrase in label or (description and phrase in description) for phrase in text):
                    new_values.append(value)
            values = new_values

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
