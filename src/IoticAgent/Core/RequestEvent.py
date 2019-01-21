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

from functools import partial
import logging
logger = logging.getLogger(__name__)
DEBUG_ENABLED = logger.isEnabledFor(logging.DEBUG)

from .compat import Event


class RequestEvent(object):  # pylint: disable=too-many-instance-attributes

    """Request event object. Uses threading.Event (factory function).
    https://docs.python.org/3/library/threading.html#event-objects
    """

    def __init__(self, id_, inner_msg_out=None, is_crud=False):
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
        # Time at which request was sent by transport. (Can change if transport failure triggers retry due to no
        # response having been received for a certain amount of time.)
        self._send_time = None
        #
        # Raw outgoing message (without wrapper), as sent via QAPI
        self._inner_msg_out = inner_msg_out
        #
        # Raw messages from the QAPI
        self._messages = []
        #
        # function to run on completion
        self._complete_func = None

    def _sent_without_response(self, send_time_before):
        """Used internally to determine whether the request has not received any response from the container and was
           send before the given time. Unsent requests are not considered."""
        return not self._messages and self._send_time and self._send_time < send_time_before

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
        if self._complete_func:
            self.__run_completion_func(self._complete_func, self.id_)

    @staticmethod
    def __run_completion_func(func, req_id):
        logger.debug('Completion func for %s: %s', req_id, func)
        try:
            func()
        except:
            logger.warning('Post-completion function failed to run', exc_info=DEBUG_ENABLED)

    def _run_on_completion(self, func, *args, **kwargs):
        """Function to call when request has finished, after having been _set(). The first argument passed to func will
        be the request itself. Additional parameters are NOT validated. If the request is already finished, the given
        function will be run immediately (in same thread).
        """
        if self._complete_func is not None:
            raise ValueError('Completion function already set for %s: %s' % (self.id_, self._complete_func))

        if not self.__event.is_set():
            self._complete_func = partial(func, self, *args, **kwargs)
        else:
            self.__run_completion_func(partial(func, self, *args, **kwargs), self.id_)

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
