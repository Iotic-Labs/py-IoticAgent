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

from __future__ import division, unicode_literals

from collections import deque
from threading import Lock
from time import sleep
import logging
logger = logging.getLogger(__name__)

from .compat import monotonic, int_types, raise_from


class RateLimiter(object):
    """Allows an action to be automatically limited to at most N iterations over time interval T"""

    def __init__(self, interval, max_iterations, wait_cmd=None):
        """
        `interval` - (int) time period in seconds to which max_iterations applies

        `max_iterations` - (int) absolute maximum number of iterations to allow in given interval

        `wait_cmd` - (func) use a custom wait function instead of time.sleep. Can be used to e.g. supply an
                     automatically interruptable wait.
        """
        if not all(isinstance(param, int_types) and param > 0 for param in (interval, max_iterations)):
            raise ValueError('Parameters must be positive integers')
        if wait_cmd is None:
            self.__wait_cmd = sleep
        else:
            try:
                wait_cmd(0)
            except Exception as ex:  # pylint: disable=broad-except
                raise_from(ValueError('wait_cmd should be called taking one argument'), ex)
            self.__wait_cmd = wait_cmd

        self.__interval = interval
        self.__max_iterations = max_iterations
        self.__iterations = deque()
        self.__lock = Lock()

    def throttle(self):
        """Uses time.monotonic() (or time.sleep() if not available) to limit to the desired rate. Should be called once
        per iteration of action which is to be throttled. Returns None unless a custom wait_cmd was specified in the
        constructor in which case its return value is used if a wait was required.
        """
        iterations = self.__iterations
        timestamp = monotonic()
        outdated_threshold = timestamp - self.__interval

        with self.__lock:
            # remove any iterations older than interval
            try:
                while iterations[0] < outdated_threshold:
                    iterations.popleft()
            except IndexError:
                pass
            # apply throttling if rate would be exceeded
            if len(iterations) <= self.__max_iterations:
                iterations.append(timestamp)
                retval = None
            else:
                # wait until oldest sample is too old
                delay = max(0, iterations[0] + self.__interval - timestamp)
                # only notify user about longer delays
                if delay > 1:
                    logger.warning('Send throttling delay (interval=%d, max_iterations=%d): %.2fs', self.__interval,
                                   self.__max_iterations, delay)
                retval = self.__wait_cmd(delay)
                # log actual addition time
                iterations.append(monotonic())

            return retval
