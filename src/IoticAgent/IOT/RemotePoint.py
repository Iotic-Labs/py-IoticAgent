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

import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Validation import Validation
from IoticAgent.Core.utils import validate_nonnegative_int
from IoticAgent.Core.compat import Queue, Empty, monotonic

from .Point import PointDataObject


class RemotePoint(object):
    """Base class for remote point types"""

    def __init__(self, client, subid, pointid, lid):
        self.__client = client
        self.__subid = Validation.guid_check_convert(subid)
        self.__pointid = Validation.guid_check_convert(pointid)
        self.__lid = Validation.lid_check_convert(lid)

    @property
    def _client(self):
        """For internal use: reference to IOT.Client instance"""
        return self.__client

    @property
    def subid(self):
        """`Advanced users only`
        The global subscription ID for the connection to this remote point in hex form (undashed).
        """
        return self.__subid

    @property
    def guid(self):
        """The Globally Unique ID of the Point you've followed (or attached to) in hex form (undashed).
        """
        return self.__pointid

    @property
    def lid(self):
        """Local id of thing which is following to this feed / attached to this control"""
        return self.__lid


class RemoteFeed(RemotePoint):
    """Helper object for Feed Subscription.
    A subscription the connection you have to another Thing's feed.  This object allows you to simulate a feed
    being received by your Thing and also to return you the last known received feed data.

    When you subscribe to a Feed this object will be returned from
    [Thing.follow()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.follow)
    This helper object provides `simulate()` and `get_last()`
    """

    def get_last(self):
        """Returns None if no recent data is available for this point or a dict containing:

            #!python
            'data' # (decoded or raw bytes)
            'mime' # (None, unless payload was not decoded and has a mime type)
            'time' # (datetime representing UTC timestamp of share)

        Note: Shorthand for get_recent(1).
        """
        try:
            return next(self.get_recent(1))
        except StopIteration:
            pass

    def get_recent(self, count):
        """Get the last instance(s) of feeddata from the feed. Useful if the remote Thing doesn't publish very often.
        Returns an iterable of dicts (in chronologically ascending order) containing:

            #!python
            'data' # (decoded or raw bytes)
            'mime' # (None, unless payload was not decoded and has a mime type)
            'time' # (datetime representing UTC timestamp of share)

        `count` (mandatory) (integer) How many recent instances to retrieve. High values might be floored to a maximum
        as defined by the container.

        Note: Feed data is iterable as soon as it arrives, rather than when the request completes.
        """
        validate_nonnegative_int(count, 'count')
        evt = self._client._request_sub_recent(self.subid, count=count)

        queue = Queue()
        self._client._add_recent_cb_for(evt, queue.put)
        timeout_time = monotonic() + self._client.sync_timeout

        while True:
            try:
                yield queue.get(True, .1)
            except Empty:
                if evt.is_set() or monotonic() >= timeout_time:
                    break
        self._client._except_if_failed(evt)

    def get_recent_async(self, count, callback):
        """Similar to `get_recent` except instead of returning an iterable, passes each dict to the given function which
        must accept a single argument. Returns the request.

        `callback` (mandatory) (function) instead of returning an iterable, pass each dict (as described above) to the
        given function which must accept a single argument. Nothing is returned.
        """
        validate_nonnegative_int(count, 'count')
        Validation.callable_check(callback, allow_none=True)
        evt = self.__client._request_sub_recent(self.subid, count=count)
        self.__client._add_recent_cb_for(evt, callback)
        return evt

    def simulate(self, data=None, mime=None):
        """Simulate the arrival of feeddata into the feed.  Useful if the remote Thing doesn't publish
        very often.  Causes the callback function for this feed to be called with the last known value
        from the feed, if there is one.

        Raises `KeyError` - if there is no data to get.  Probably because you haven't received any and haven't
        called [simulate_feeddata()](./Client.m.html#IoticAgent.IOT.Client.Client.simulate_feeddata)
         with the data= and mime= parameters set

        Raises `RuntimeError` - if the key-value store "database" is disabled

        `data` (mandatory) (as applicable) The data you want to use to simulate the arrival of remote feed data

        `mime` (optional) (string) The mime type of your data.  See:
        [share()](./Point.m.html#IoticAgent.IOT.Point.Feed.share)
        """
        self._client.simulate_feeddata(self.__pointid, data, mime)


class RemoteControl(RemotePoint):
    """Helper object for Control Subscription.
    A subscription the connection you have to another Thing's control.  This object allows you to pass data
    to the other Things control in two ways, `ask` and `tell`:

    `ask` where you "fire and forget" - the receiving object doesn't have to let you know whether it has actioned your
    request

    `tell` where you expect the receiving object to let you know whether or not has actioned your request

    When you attach to a Control this object will be returned from
    [Thing.attach()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.attach).
    """

    def get_template(self):
        """Retreive [PointDataObject](./PointValueHelper.m.html#IoticAgent.IOT.PointValueHelper.PointDataObject)
        instance to use with this control."""
        return self._client._get_point_data_handler_for(self).get_template()

    def ask(self, data, mime=None):
        """Request a remote control to do something.  Ask is "fire-and-forget" in that you won't receive
        any notification of the success or otherwise of the action at the far end.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `data` (mandatory) (as applicable) The data you want to share

        `mime` (optional) (string) The mime type of the data you're sharing.  See:
        [share()](./Point.m.html#IoticAgent.IOT.Point.Feed.share)
        """
        logger.info("ask() [subid=%s]", self.subid)
        if mime is None and isinstance(data, PointDataObject):
            data = data.to_dict()
        evt = self._client._request_sub_ask(self.subid, data, mime)
        evt.wait(self._client.sync_timeout)
        self._client._except_if_failed(evt)

    def ask_async(self, data, mime=None):
        logger.info("ask_async() [subid=%s]", self.subid)
        return self._client._request_sub_ask(self.subid, data, mime)

    def tell(self, data, timeout=10, mime=None):
        """Order a remote control to do something.  Tell is confirmed in that you will receive
        a notification of the success or otherwise of the action at the far end via a callback

        `Example`

            #!python
            data = {"thermostat":18.0}
            retval = r_thermostat.tell(data, timeout=10, mime=None)
            if retval is not True:
                print("Thermostat not reset - reason: {reason}".format(reason=retval))

        Returns True on success or else returns the reason (string) one of:

            #!python
            "timeout"     # The request-specified timeout has been reached.
            "unreachable" # The remote control is not associated with an agent
                          #     or is not reachable in some other way.
            "failed"      # The remote control indicates it did not perform
                          #     the request.

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `data` (mandatory) (as applicable) The data you want to share

        `timeout` (optional) (int) Default 10.  The delay in seconds before your tell request times out.

        `mime` (optional) (string) See:
        [share()](./Point.m.html#IoticAgent.IOT.Point.Feed.share)
        """
        logger.info("tell(timeout=%s) [subid=%s]", timeout, self.subid)
        if mime is None and isinstance(data, PointDataObject):
            data = data.to_dict()
        evt = self._client._request_sub_tell(self.subid, data, timeout, mime=mime)
        evt.wait(self._client.sync_timeout)
        self._client._except_if_failed(evt)
        return True if evt.payload['success'] else evt.payload['reason']

    def tell_async(self, data, timeout=10, mime=None):
        """Asyncronous version of [tell()](./RemotePoint.m.html#IoticAgent.IOT.RemotePoint.RemoteControl.tell)

        `Note` payload contains the success and reason keys they are not separated out as in the synchronous version
        """
        logger.info("tell_async(timeout=%s) [subid=%s]", timeout, self.subid)
        return self._client._request_sub_tell(self.subid, data, timeout, mime=mime)
