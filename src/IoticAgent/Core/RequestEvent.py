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

from .compat import Event


class RequestEvent(object):

    """Request event object. Uses threading.Event (factory function).
    https://docs.python.org/3/library/threading.html#event-objects
    """

    __slots__ = ('_RequestEvent__event', 'id_', 'success', 'payload', 'is_crud', 'exception', '_messages')

    def __init__(self, id_=None, is_crud=False):
        self.__event = Event()  # pylint: disable=assigning-non-slot
        #
        # request id used to communicate with the QAPI
        self.id_ = id_
        #
        # success True or failure False or None for not set yet
        self.success = None
        #
        # Complete/Error message payload or error message
        self.payload = None
        #
        # Whether the associated operation is a resource CRUD type (used by Client to serialise CRUD type responses)
        self.is_crud = is_crud
        #
        # If an exception occurred, this is instance
        self.exception = None
        #
        # Raw messages from the QAPI
        self._messages = []

    def is_set(self):
        """Returns True if the request has finished or False if it is still pending.

        Raises [LinkException](AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException) if the request failed due to a
        network related problem.
        """
        if self.__event.is_set():
            if self.exception is not None:
                # todo better way to raise errors on behalf of other Threads?
                raise self.exception  # pylint: disable=raising-bad-type
            return True
        return False

    def _set(self):
        """Called internally by Client to indicate this request has finished"""
        self.__event.set()

    def wait(self, timeout=None):
        """Wait for the request to finish, optionally timing out. Returns True if the request has finished or False if
        it is still pending.

        Raises [LinkException](AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException) if the request failed due to a
        network related problem.
        """
        if self.__event.wait(timeout):
            if self.exception is not None:
                # todo better way to raise errors on behalf of other Threads?
                raise self.exception  # pylint: disable=raising-bad-type
            return True
        return False
