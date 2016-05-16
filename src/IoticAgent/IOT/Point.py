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

from IoticAgent.Core.Const import R_FEED, R_CONTROL
from IoticAgent.Core.Validation import Validation

from .utils import hex_to_uuid, foc_to_str

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

    @property
    def guid(self):
        """The Globally Unique ID of this Point.  In the 8-4-4-4-12 format
        """
        return hex_to_uuid(self.__guid)

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
        logger.info("list(limit=%s, offset=%s) [lid=%s,pid=%s]", self.__lid, self.__pid, limit, offset)
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
        evt = self.__client._request_point_share(self.__lid, self.__pid, data, mime)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def share_async(self, data, mime=None):
        logger.info("share_async() [lid=\"%s\",pid=\"%s\"]", self.__lid, self.__pid)
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
