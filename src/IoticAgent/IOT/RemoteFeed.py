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
"""Helper object for Feed Subscription.
A subscription the connection you have to another Thing's feed.  This object allows you to simulate a feed
being received by your Thing and also to return you the last known received feed data.
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from .utils import hex_to_uuid


class RemoteFeed(object):
    """Feed Subscription helper object.
    When you subscribe to a Feed this object will be returned from
    [Thing.follow()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.follow)
    This helper object provides `simulate()` and `get_last()`
    """

    def __init__(self, client, subid, feedid):
        self.__client = client
        self.__subid = subid
        self.__feedid = feedid

    @property
    def subid(self):
        """`Advanced users only`
        The global subscription ID for the connection to this remote feed. In the 8-4-4-4-12 format
        """
        return hex_to_uuid(self.__subid)

    @property
    def guid(self):
        """The Globally Unique ID of the Point you've followed.  In 8-4-4-4-12 format
        """
        return hex_to_uuid(self.__feedid)

    def get_last(self):
        """Get the last instance of feeddata from the feed.  Useful if the remote Thing doesn't publish
        very often.

        Returns last data for feedid and mime (as tuple), or tuple of (None, None) if not found

        Raises `KeyError` - if there is no data to get.  Probably because you haven't received any and haven't
        called [simulate_feeddata()](./Client.m.html#IoticAgent.IOT.Client.Client.simulate_feeddata)
         with the data= and mime= parameters set

        Raises `RuntimeError` - if the key-value store "database" is disabled
        """
        return self.__client.get_last_feeddata(self.__feedid)

    def simulate(self, data=None, mime=None):
        """Simulate the arrival of feeddata into the feed.  Useful if the remote Thing doesn't publish
        very often.  Causes the callback function for this feed to be called with the last known value
        from the feed, if there is one.

        Raises `KeyError` - if there is no data to get.  Probably because you haven't received any and haven't
        called [simulate_feeddata()](./Client.m.html#IoticAgent.IOT.Client.Client.simulate_feeddata)
         with the data= and mime= parameters set

        Raises `RuntimeError` - if the key-value store "database" is disabled

        `data` (optional) (as applicable) The data you want to use to simulate the arrival of remote feed data

        `mime` (optional) (string) The mime type of your data.  See:
        [share()](./Point.m.html#IoticAgent.IOT.Point.Point.share)
        """
        self.__client.simulate_feeddata(self.__feedid, data, mime)
