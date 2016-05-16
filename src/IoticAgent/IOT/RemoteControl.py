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
"""Helper object for Control Subscription.
A subscription the connection you have to another Thing's control.  This object allows you to pass data
to the other Things control in two ways, `ask` and `tell`:

`ask` where you "fire and forget" - the receiving object doesn't have to let you know whether it has actioned your
request

`tell` where you expect the receiving object to let you know whether or not has actioned your request
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.Validation import Validation

from .utils import hex_to_uuid


class RemoteControl(object):
    """Control Subscription helper object.
    When you attach to a Control this object will be returned from
    [Thing.attach()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.attach)
    This helper object exposes the `ask()` and `tell()` methods and some others.
    """

    def __init__(self, client, subid, controlid):
        self.__client = client
        self.__subid = Validation.guid_check_convert(subid)
        self.__controlid = Validation.guid_check_convert(controlid)

    @property
    def subid(self):
        """`Advanced users only`
        The global subscription ID for the connection to this remote control. In the 8-4-4-4-12 format
        """
        return hex_to_uuid(self.__subid)

    @property
    def guid(self):
        """The Globally Unique ID of the control to which you've attached.  In 8-4-4-4-12 format
        """
        return hex_to_uuid(self.__controlid)

    def ask(self, data, mime=None):
        """Request a remote control to do something.  Ask is "fire-and-forget" in that you won't receive
        any notification of the success or otherwise of the action at the far end.

        Returns True (which doesn't mean the action has happened, just that the request has been sent

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `data` (mandatory) (as applicable) The data you want to share

        `mime` (optional) (string) The mime type of the data you're sharing.  See:
        [share()](./Point.m.html#IoticAgent.IOT.Point.Point.share)
        """
        logger.info("ask() [subid=%s]", self.__subid)
        evt = self.__client._request_sub_ask(self.__subid, data, mime)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)

    def ask_async(self, data, mime=None):
        logger.info("ask_async() [subid=%s]", self.__subid)
        return self.__client._request_sub_ask(self.__subid, data, mime)

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
        [share()](./Point.m.html#IoticAgent.IOT.Point.Point.share)
        """
        logger.info("tell(timeout=%s) [subid=%s]", timeout, self.__subid)
        evt = self.__client._request_sub_tell(self.__subid, data, timeout, mime=mime)
        evt.wait(self.__client.sync_timeout)
        self.__client._except_if_failed(evt)
        return 'success' if evt.payload['success'] else evt.payload['reason']

    def tell_async(self, data, timeout=10, mime=None):
        """Asyncronous version of [tell()](./RemoteControl.m.html#IoticAgent.IOT.RemoteControl.RemoteControl.tell)

        `Note` payload contains the success and reason keys they are not separated out as in the synchronous version
        """
        logger.info("tell_async(timeout=%s) [subid=%s]", timeout, self.__subid)
        return self.__client._request_sub_tell(self.__subid, data, timeout, mime=mime)
