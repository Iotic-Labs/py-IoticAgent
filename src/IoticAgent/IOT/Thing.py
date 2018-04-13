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
"""Wrapper object for Iotic Things
"""
from __future__ import unicode_literals

from contextlib import contextmanager
import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Const import (P_RESOURCE, R_FEED, R_CONTROL, R_SUB, P_ID, P_LID, P_ENTITY_LID, P_POINT_LID,
                                   P_POINT_ID, P_POINT_ENTITY_LID, P_POINT_TYPE, P_EPID)
from IoticAgent.Core import ThreadSafeDict
from IoticAgent.Core.compat import raise_from, string_types, Sequence
from IoticAgent.Core.Validation import Validation

from .Exceptions import IOTClientError
from .Resource import Resource
from .RemotePoint import RemoteFeed, RemoteControl
from .Point import Feed, Control
from .utils import foc_to_str, uuid_to_hex
from .ThingMeta import ThingMeta

_POINT_TYPE_TO_CLASS = {cls._type: cls for cls in (Feed, Control)}


class Thing(Resource):  # pylint: disable=too-many-public-methods
    """Thing class
    """

    def __init__(self, client, lid, guid, epId):
        super(Thing, self).__init__(client, guid)
        self.__lid = Validation.lid_check_convert(lid)
        self.__epId = Validation.guid_check_convert(epId)
        # Keep track of newly created points & subs (the requests for which originated from current agent)
        self.__new_feeds = ThreadSafeDict()
        self.__new_controls = ThreadSafeDict()
        self.__new_subs = ThreadSafeDict()

    def __str__(self):
        return '%s (thing, %s)' % (self.guid, self.__lid)

    def __hash__(self):
        # Why not just hash guid? Because Thing is used before knowing guid in some cases
        # Why not hash without guid? Because in two separate containers one could have identicial things
        # (if not taking guid into account)
        return hash(self.__lid) ^ hash(self.guid)

    def __eq__(self, other):
        return (isinstance(other, Thing) and
                self.guid == other.guid and
                self.__lid == other.__lid)

    @property
    def lid(self):
        """The local id of this Thing.  This is unique to you on this container.
        Think of it as a nickname for the Thing
        """
        return self.__lid

    @property
    def agent_id(self):
        """Agent id (aka epId) with which this Thing is associated. None indicates this Thing is not assigned to any
        agent. The following actions can only be performed with a Thing if operating in its associated agent:

        - Receive feed data from feeds the Thing is following
        - Share feed data for feeds this Thing owns
        - Receive control requests for controls the Thing owns
        - Perform ask/tell on a control this Thing is attached to

        Attempting to perform the above actions from another agent will result in either a local (e.g. ValueError) or
        remote ([IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)) exception to be raised.
        """
        return self.__epId

    def __list(self, foc, limit=500, offset=0):
        logger.info("__list(foc=\"%s\", limit=%s, offset=%s) [lid=%s]", foc_to_str(foc), limit, offset, self.__lid)
        evt = self._client._request_point_list(foc, self.__lid, limit=limit, offset=offset)
        self._client._wait_and_except_if_failed(evt)
        return evt.payload

    def list_feeds(self, limit=500, offset=0):
        """List `all` the feeds on this Thing.

        Returns QAPI list function payload

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `limit` (optional) (integer) Return this many Point details

        `offset` (optional) (integer) Return Point details starting at this offset
        """
        return self.__list(R_FEED, limit=limit, offset=offset)['feeds']

    def list_controls(self, limit=500, offset=0):
        """List `all` the controls on this Thing.

        Returns QAPI list function payload

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `limit` (optional) (integer) Return this many Point details

        `offset` (optional) (integer) Return Point details starting at this offset
        """
        return self.__list(R_CONTROL, limit=limit, offset=offset)['controls']

    def set_public(self, public=True):
        """Sets your Thing to be public to all.  If `public=True`.
        This means the tags, label and description of your Thing are now searchable by anybody, along with its
        location and the units of any values on any Points.
        If `public=False` the metadata of your Thing is no longer searchable.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `public` (optional) (boolean) Whether (or not) to allow your Thing's metadata
        to be searched by anybody
        """
        logger.info("set_public(public=%s) [lid=%s]", public, self.__lid)
        evt = self._client._request_entity_meta_setpublic(self.__lid, public)
        self._client._wait_and_except_if_failed(evt)

    def rename(self, new_lid):
        """Rename the Thing.

        `ADVANCED USERS ONLY`  This can be confusing.  You are changing the local id of a Thing to `new_lid`.  If you
        create another Thing using the "old_lid", the system will oblige, but it will be a completely _new_ Thing.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `new_lid` (required) (string) the new local identifier of your Thing
        """
        logger.info("rename(new_lid=\"%s\") [lid=%s]", new_lid, self.__lid)
        evt = self._client._request_entity_rename(self.__lid, new_lid)
        self._client._wait_and_except_if_failed(evt)
        self.__lid = new_lid
        self._client._notify_thing_lid_change(self.__lid, new_lid)

    def reassign(self, new_epid):
        """Reassign the Thing from one agent to another.

        `ADVANCED USERS ONLY`  This will lead to any local instances of a Thing being rendered useless.
        They won't be able to receive control requests, feed data or to share any feeds as they won't be in this agent.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `new_epid` (required) (string) the new agent id to which your Thing should be assigned. If None,
        current agent will be chosen. If False, existing agent will be unassigned.
        """
        logger.info("reassign(new_epid=\"%s\") [lid=%s]", new_epid, self.__lid)
        evt = self._client._request_entity_reassign(self.__lid, new_epid)
        self._client._wait_and_except_if_failed(evt)

    def create_tag(self, tags):
        """Create tags for a Thing in the language you specify. Tags can only contain alphanumeric (unicode) characters
        and the underscore. Tags will be stored lower-cased.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `tags` (mandatory) (list) - the list of tags you want to add to your Thing, e.g.
        `["garden", "soil"]`
        """
        if isinstance(tags, str):
            tags = [tags]

        evt = self._client._request_entity_tag_update(self.__lid, tags, delete=False)
        self._client._wait_and_except_if_failed(evt)

    def delete_tag(self, tags):
        """Delete tags for a Thing in the language you specify. Case will be ignored and any tags matching lower-cased
        will be deleted.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `tags` (mandatory) (list) - the list of tags you want to delete from your Thing, e.g.
        `["garden", "soil"]`
        """
        if isinstance(tags, str):
            tags = [tags]

        evt = self._client._request_entity_tag_update(self.__lid, tags, delete=True)
        self._client._wait_and_except_if_failed(evt)

    def list_tag(self, limit=500, offset=0):
        """List `all` the tags for this Thing

        Returns lists of tags, as below

            #!python
            [
                "mytag1",
                "mytag2"
                "ein_name",
                "nochein_name"
            ]

        - OR...

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `limit` (optional) (integer) Return at most this many tags

        `offset` (optional) (integer) Return tags starting at this offset
        """
        evt = self._client._request_entity_tag_list(self.__lid, limit=limit, offset=offset)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['tags']

    def get_meta(self):
        """Get the metadata object for this Thing

        Returns a [ThingMeta](ThingMeta.m.html#IoticAgent.IOT.ThingMeta.ThingMeta) object
        """
        rdf = self.get_meta_rdf(fmt='n3')
        return ThingMeta(self, rdf, self._client.default_lang, fmt='n3')

    def get_meta_rdf(self, fmt='n3'):
        """Get the metadata for this Thing in rdf fmt

        Advanced users who want to manipulate the RDF for this Thing directly without the
        [ThingMeta](ThingMeta.m.html#IoticAgent.IOT.ThingMeta.ThingMeta) helper object

        Returns the RDF in the format you specify. - OR -

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `fmt` (optional) (string) The format of RDF you want returned.
        Valid formats are: "xml", "n3", "turtle"
        """
        evt = self._client._request_entity_meta_get(self.__lid, fmt=fmt)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['meta']

    def set_meta_rdf(self, rdf, fmt='n3'):
        """Set the metadata for this Thing in RDF fmt

        Advanced users who want to manipulate the RDF for this Thing directly without the
        [ThingMeta](ThingMeta.m.html#IoticAgent.IOT.ThingMeta.ThingMeta) helper object

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `fmt` (optional) (string) The format of RDF you have sent.
        Valid formats are: "xml", "n3", "turtle"
        """
        evt = self._client._request_entity_meta_set(self.__lid, rdf, fmt=fmt)
        self._client._wait_and_except_if_failed(evt)

    def get_feed(self, pid):
        """Get the details of a newly created feed. This only applies to asynchronous creation of feeds and the new feed
        instance can only be retrieved once.

        `NOTE` - Destructive Read. Once you've called get_feed once, any further calls will raise a `KeyError`

        Returns a [Feed](Point.m.html#IoticAgent.IOT.Point.Feed) object,
        which corresponds to the cached entry for this local feed id

        `pid` (required) (string) Point id - local identifier of your feed.

        Raises `KeyError` if the feed has not been newly created (or has already been retrieved by a previous call)
        """
        with self.__new_feeds:
            try:
                return self.__new_feeds.pop(pid)
            except KeyError as ex:
                raise_from(KeyError('Feed %s not know as new' % pid), ex)

    def get_control(self, pid):
        """Get the details of a newly created control. This only applies to asynchronous creation of feeds and the new
        control instance can only be retrieved once.

        `NOTE` - Destructive Read. Once you've called get_control once, any further calls will raise a `KeyError`

        Returns a [Control](Point.m.html#IoticAgent.IOT.Point.Control) object,
        which corresponds to the cached entry for this local control id

        `pid` (required) (string) local identifier of your control.

        Raises `KeyError` if the control has not been newly created (or has already been retrieved by a previous call)
        """
        with self.__new_controls:
            try:
                return self.__new_controls.pop(pid)
            except KeyError as ex:
                raise_from(KeyError('Control %s not know as new' % pid), ex)

    def __create_point(self, foc, pid, control_cb=None, save_recent=0):
        evt = self.__create_point_async(foc, pid, control_cb=control_cb, save_recent=save_recent)
        self._client._wait_and_except_if_failed(evt)
        store = self.__new_feeds if foc == R_FEED else self.__new_controls
        try:
            with store:
                return store.pop(pid)
        except KeyError as ex:
            raise raise_from(IOTClientError('%s %s (from %s) not in cache (post-create)' %
                                            (foc_to_str(foc), pid, self.__lid)),
                             ex)

    def __create_point_async(self, foc, pid, control_cb=None, save_recent=0):
        return self._client._request_point_create(foc, self.__lid, pid, control_cb=control_cb, save_recent=save_recent)

    def create_feed(self, pid, save_recent=0):
        """Create a new Feed for this Thing with a local point id (pid).

        Returns a new [Feed](Point.m.html#IoticAgent.IOT.Point.Feed) object,
        or the existing one, if the Feed already exists

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `pid` (required) (string) local id of your Feed

        `save_recent` (optional) (int) how many shares to store for later retrieval. If not supported by container, this
        argument will be ignored. A value of zero disables this feature whilst a negative value requests the maximum
        sample store amount. See also
        [Feed.set_recent_config](./Point.m.html#IoticAgent.IOT.Point.Feed.set_recent_config).
        """
        logger.info("create_feed(pid=\"%s\") [lid=%s]", pid, self.__lid)
        return self.__create_point(R_FEED, pid, save_recent=save_recent)

    def create_feed_async(self, pid, save_recent=0):
        logger.info("create_feed_async(pid=\"%s\") [lid=%s]", pid, self.__lid)
        return self.__create_point_async(R_FEED, pid, save_recent=save_recent)

    def create_control(self, pid, callback, callback_parsed=None):
        """Create a control for this Thing with a local point id (pid) and a control request feedback

        Returns a new [Control](Point.m.html#IoticAgent.IOT.Point.Control) object
        or the existing one if the Control already exists

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `pid` (required) (string) local id of your Control

        `callback` (required) (function reference) callback function to invoke on receipt of a control request.
        The callback receives a single dict argument, with keys of:

            #!python
            'data'      # (decoded or raw bytes)
            'mime'      # (None, unless payload was not decoded and has a mime type)
            'subId'     # (the global id of the associated subscripion)
            'entityLid' # (local id of the Thing to which the control belongs)
            'lid'       # (local id of control)
            'confirm'   # (whether a confirmation is expected)
            'requestId' # (required for sending confirmation)

        `callback_parsed` (optional) (function reference) callback function to invoke on receipt of control data. This
        is equivalent to `callback` except the dict includes the `parsed` key which holds the set of values in a
        [PointDataObject](./Point.m.html#IoticAgent.IOT.Point.PointDataObject) instance. If both
        `callback_parsed` and `callback` have been specified, the former takes precedence and `callback` is only called
        if the point data could not be parsed according to its current value description.

        `NOTE`: `callback_parsed` can only be used if `auto_encode_decode` is enabled for the client instance.
        """
        logger.info("create_control(pid=\"%s\", control_cb=%s) [lid=%s]", pid, callback, self.__lid)
        if callback_parsed:
            callback = self._client._get_parsed_control_callback(callback_parsed, callback)
        return self.__create_point(R_CONTROL, pid, control_cb=callback)

    def create_control_async(self, pid, callback, callback_parsed=None):
        logger.info("create_control_async(pid=\"%s\", control_cb=%s) [lid=%s]", pid, callback, self.__lid)
        if callback_parsed:
            callback = self._client._get_parsed_control_callback(callback_parsed, callback)
        return self.__create_point_async(R_CONTROL, pid, control_cb=callback)

    def __delete_point(self, foc, pid):
        evt = self.__delete_point_async(foc, pid)
        self._client._wait_and_except_if_failed(evt)

    def __delete_point_async(self, foc, pid):
        return self._client._request_point_delete(foc, self.__lid, pid)

    def delete_feed(self, pid):
        """Delete a feed, identified by its local id.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `pid` (required) (string) local identifier of your feed you want to delete

        """
        logger.info("delete_feed(pid=\"%s\") [lid=%s]", pid, self.__lid)
        return self.__delete_point(R_FEED, pid)

    def delete_feed_async(self, pid):
        logger.info("delete_feed_async(pid=\"%s\") [lid=%s]", pid, self.__lid)
        return self.__delete_point_async(R_FEED, pid)

    def delete_control(self, pid):
        """Delete a control, identified by its local id.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `pid` (required) (string) local identifier of your control you want to delete
        """
        logger.info("delete_control(pid=\"%s\") [lid=%s]", pid, self.__lid)
        return self.__delete_point(R_CONTROL, pid)

    def delete_control_async(self, pid):
        logger.info("delete_control_async(pid=\"%s\") [lid=%s]", pid, self.__lid)
        return self.__delete_point_async(R_CONTROL, pid)

    def __get_sub(self, foc, gpid):
        # global
        if isinstance(gpid, string_types):
            gpid = uuid_to_hex(gpid)
        # not local
        elif not (isinstance(gpid, Sequence) and len(gpid) == 2):
            raise ValueError('gpid must be string or two-element tuple')
        try:
            sub = self.__new_subs.pop((foc, gpid))
        except KeyError as ex:
            raise_from(KeyError('Remote%s subscription %s not know as new' % (foc_to_str(foc).capitalize(), gpid)), ex)
        if sub is None:
            raise ValueError('Either subscription not complete yet or point %s is of opposite type. (In which case'
                             ' call %s instead' % (gpid, 'attach()' if foc == R_FEED else 'follow()'))
        return sub

    def get_remote_feed(self, gpid):
        """Retrieve `RemoteFeed` instance for a follow. This only applies to asynchronous follow requests and the
        new `RemoteFeed` instance can only be retrieved once.

        `NOTE` - Destructive Read. Once you've called get_remote_feed once, any further calls will raise a `KeyError`

        Raises `KeyError` if the follow-subscription has not been newly created (or has already been retrieved by a
        previous call)

        Raises `ValueError` if the followed Point is actually a control instead of a feed, or if the subscription has
        not completed yet.
        """
        return self.__get_sub(R_FEED, gpid)

    def get_remote_control(self, gpid):
        """Retrieve `RemoteControl` instance for an attach. This only applies to asynchronous attach requests and the
        new `RemoteControl` instance can only be retrieved once.

        `NOTE` - Destructive Read. Once you've called get_remote_control once, any further calls will raise a `KeyError`

        Raises `KeyError` if the attach-subscription has not been newly created (or has already been retrieved by a
        previous call)

        Raises `ValueError` if the followed Point is actually a feed instead of a control, or if the subscription has
        not completed yet."""
        return self.__get_sub(R_CONTROL, gpid)

    @contextmanager
    def __sub_add_reference(self, key):
        """Used by __sub_make_request to save reference for pending sub request"""
        new_subs = self.__new_subs
        with new_subs:
            # don't allow multiple subscription requests to overwrite internal reference
            if key in new_subs:
                raise ValueError('subscription for given args pending: %s', key)
            new_subs[key] = None
        try:
            yield
        except:
            # don't preserve reference if request creation failed
            with new_subs:
                new_subs.pop(key, None)
            raise

    def __sub_make_request(self, foc, gpid, callback):
        """Make right subscription request depending on whether local or global - used by __sub*"""
        # global
        if isinstance(gpid, string_types):
            gpid = uuid_to_hex(gpid)
            with self.__sub_add_reference((foc, gpid)):
                return self._client._request_sub_create(self.__lid, foc, gpid, callback=callback)
        # local
        elif isinstance(gpid, Sequence) and len(gpid) == 2:
            with self.__sub_add_reference((foc, tuple(gpid))):
                return self._client._request_sub_create_local(self.__lid, foc, *gpid, callback=callback)
        else:
            raise ValueError('gpid must be string or two-element tuple')

    def __sub(self, foc, gpid, callback=None):
        logger.info("__sub(foc=%s, gpid=\"%s\", callback=%s) [lid=%s]", foc_to_str(foc), gpid, callback, self.__lid)
        evt = self.__sub_async(foc, gpid, callback=callback)
        self._client._wait_and_except_if_failed(evt)
        try:
            return self.__get_sub(foc, gpid)
        except KeyError as ex:
            raise raise_from(IOTClientError('Subscription for %s (from %s) not in cache (post-create)' %
                                            gpid, self.__lid),
                             ex)

    def __sub_async(self, foc, gpid, callback=None):
        logger.info("__sub(foc=%s, gpid=\"%s\", callback=%s) [lid=%s]", foc_to_str(foc), gpid, callback, self.__lid)
        return self.__sub_make_request(foc, gpid, callback)

    def follow(self, gpid, callback=None, callback_parsed=None):
        """Create a subscription (i.e. follow) a Feed/Point with a global point id (gpid) and a feed data callback

        Returns a new [RemoteFeed](RemotePoint.m.html#IoticAgent.IOT.RemotePoint.RemoteFeed)
        object or the existing one if the subscription already exists - OR -

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `gpid` (required) (uuid) global id of the Point you want to follow `-OR-`

        `gpid` (required) (lid,pid) tuple of `(thing_localid, point_localid)` for local subscription

        `callback` (optional) (function reference) callback function to invoke on receipt of feed data.
        The callback receives a single dict argument, with keys of:

            #!python
            'data' # (decoded or raw bytes)
            'mime' # (None, unless payload was not decoded and has a mime type)
            'pid'  # (the global id of the feed from which the data originates)
            'time' # (datetime representing UTC timestamp of share)

        `callback_parsed` (optional) (function reference) callback function to invoke on receipt of feed data. This is
        equivalent to `callback` except the dict includes the `parsed` key which holds the set of values in a
        [PointDataObject](./Point.m.html#IoticAgent.IOT.Point.PointDataObject) instance. If both
        `callback_parsed` and `callback` have been specified, the former takes precedence and `callback` is only called
        if the point data could not be parsed according to its current value description.

        `NOTE`: `callback_parsed` can only be used if `auto_encode_decode` is enabled for the client instance.
        """
        if callback_parsed:
            callback = self._client._get_parsed_feed_callback(callback_parsed, callback)
        return self.__sub(R_FEED, gpid, callback=callback)

    def follow_async(self, gpid, callback=None, callback_parsed=None):
        if callback_parsed:
            callback = self._client._get_parsed_feed_callback(callback_parsed, callback)
        return self.__sub_async(R_FEED, gpid, callback=callback)

    def attach(self, gpid):
        """Create a subscription (i.e. attach) to a Control-Point with a global point id (gpid) and a feed data callback

        Returns a new [RemoteControl](RemotePoint.m.html#IoticAgent.IOT.RemotePoint.RemoteControl)
        object or the existing one if the subscription already exists

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `gpid` (required) (uuid) global id of the Point to which you want to attach `-OR-`

        `gpid` (required) (lid,pid) tuple of `(thing_localid, point_localid)` for local subscription
        """
        return self.__sub(R_CONTROL, gpid)

    def attach_async(self, gpid):
        return self.__sub_async(R_CONTROL, gpid)

    def __sub_delete(self, subid):
        if isinstance(subid, (RemoteFeed, RemoteControl)):
            subid = subid.subid
        evt = self._client._request_sub_delete(subid)
        self._client._wait_and_except_if_failed(evt)

    def unfollow(self, subid):
        """Remove a subscription of a Feed with a global subscription id (gpid)

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `subid` (required) `Either` (uuid) global id of the subscription you want to delete `or`
        (object) The instance of a RemoteFeed object corresponding to the feed you want to cease
        following.
        """
        return self.__sub_delete(subid)

    def unattach(self, subid):
        """Remove a subscription of a control with a global subscription id (gpid)

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `subid` (required) ( `Either` (uuid) global id of the subscription you want to delete `or`
        (object) The instance of a RemoteControl object corresponding to the control you want
        to cease being able to actuate.
        """
        return self.__sub_delete(subid)

    def list_connections(self, limit=500, offset=0):
        """List Points to which this Things is subscribed.
        I.e. list all the Points this Thing is following and controls it's attached to

        Returns subscription list e.g.

            #!python
            {
                "<Subscription GUID 1>": {
                    "id": "<Control GUID>",
                    "entityId":  "<Control's Thing GUID>",
                    "type": 3  # R_CONTROL from IoticAgent.Core.Const
                },
                "<Subscription GUID 2>": {
                    "id": "<Feed GUID>",
                    "entityId":  "<Feed's Thing GUID>",
                    "type": 2  # R_FEED from IoticAgent.Core.Const
            }

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        Note: For Things following a Point see
        [list_followers](./Point.m.html#IoticAgent.IOT.Point.Point.list_followers)
        """
        evt = self._client._request_sub_list(self.__lid, limit=limit, offset=offset)

        self._client._wait_and_except_if_failed(evt)
        return evt.payload['subs']

    def _cb_created(self, payload, duplicated):
        """Indirect callback (via Client) for point & subscription creation responses"""
        if payload[P_RESOURCE] in _POINT_TYPE_TO_CLASS:
            store = self.__new_feeds if payload[P_RESOURCE] == R_FEED else self.__new_controls
            cls = _POINT_TYPE_TO_CLASS[payload[P_RESOURCE]]
            with store:
                store[payload[P_LID]] = cls(self._client, payload[P_ENTITY_LID], payload[P_LID], payload[P_ID])
            logger.debug('Added %s: %s (for %s)', foc_to_str(payload[P_RESOURCE]), payload[P_LID],
                         payload[P_ENTITY_LID])

        elif payload[P_RESOURCE] == R_SUB:
            # local
            if P_POINT_ENTITY_LID in payload:
                key = (payload[P_POINT_TYPE], (payload[P_POINT_ENTITY_LID], payload[P_POINT_LID]))
            # global
            else:
                key = (payload[P_POINT_TYPE], payload[P_POINT_ID])

            new_subs = self.__new_subs
            with new_subs:
                if key in new_subs:
                    cls = RemoteFeed if payload[P_POINT_TYPE] == R_FEED else RemoteControl
                    new_subs[key] = cls(self._client, payload[P_ID], payload[P_POINT_ID], payload[P_ENTITY_LID])
                else:
                    logger.warning('Ignoring subscription creation for unexpected %s: %s',
                                   foc_to_str(payload[P_POINT_TYPE]), key[1])

        else:
            logger.error('Resource creation of type %d unhandled', payload[P_RESOURCE])

    def _cb_reassigned(self, payload):
        self.__epId = payload[P_EPID]
        logger.info('Thing %s reassigned to agent %s', self.__lid, self.__epId)
