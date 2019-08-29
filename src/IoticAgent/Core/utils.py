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
"""Utility functions
"""

from .compat import raise_from, Lock, Event, monotonic


def version_string_to_tuple(version):
    return tuple(int(part) if part.isdigit() else part for part in version.split('.'))


def validate_int(obj, name):
    try:
        obj = int(obj)
    except (ValueError, TypeError) as ex:
        raise_from(ValueError('%s invalid' % name), ex)
    return obj


def validate_nonnegative_int(obj, name, allow_zero=False):
    try:
        obj = int(obj)
        if obj < 0:
            raise ValueError('%s negative' % name)
        if (not allow_zero) and obj == 0:
            raise ValueError('%s zero' % name)
    except (ValueError, TypeError) as ex:
        raise_from(ValueError('%s invalid' % name), ex)
    return obj


class EventWithChangeTimes(Event):
    """Keeps track of last clear and set calls (which actually change the state of the event) using time.monotonic."""

    # Equivalent to maxint in Python 2
    UNSET_VALUE = 2**63 - 1

    def __init__(self):
        super(EventWithChangeTimes, self).__init__()
        self.__lock = Lock()
        self.__last_clear = None
        self.__last_set = None

    @property
    def time_since_last_set(self):
        """Time (in fractional seconds) since event was set. If the event has never been set, UNSET_VALUE will be
        returned.
        """
        if self.__last_set is None:
            return self.UNSET_VALUE
        return monotonic() - self.__last_set

    @property
    def time_since_last_clear(self):
        """Time (in fractional seconds) since event was cleared. If the event has never been (explicitly) cleared,
        UNSET_VALUE will be returned.
        """
        if self.__last_clear is None:
            return self.UNSET_VALUE
        return monotonic() - self.__last_clear

    def set(self):
        if not self.is_set():
            with self.__lock:
                super(EventWithChangeTimes, self).set()
                self.__last_set = monotonic()

    def clear(self):
        if self.is_set():
            with self.__lock:
                super(EventWithChangeTimes, self).clear()
                self.__last_clear = monotonic()
