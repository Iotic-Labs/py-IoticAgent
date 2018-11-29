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

"""Interruptable threading primitives for Python v2.7+ (not 3)"""

from threading import Lock, RLock, Condition, Event
from time import time


class _InterruptableLock(object):

    def __init__(self, lock):
        """Creates a new lock."""
        self.__lock = lock
        self.__condition = Condition(Lock())

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def acquire(self, blocking=True, timeout=-1):
        """Acquire a lock, blocking or non-blocking.
        Blocks until timeout, if timeout a positive float and blocking=True. A timeout
        value of -1 blocks indefinitely, unless blocking=False."""
        if not isinstance(timeout, (int, float)):
            raise TypeError('a float is required')

        if blocking:
            # blocking indefinite
            if timeout == -1:
                with self.__condition:
                    while not self.__lock.acquire(False):
                        # condition with timeout is interruptable
                        self.__condition.wait(60)
                return True

            # same as non-blocking
            elif timeout == 0:
                return self.__lock.acquire(False)

            elif timeout < 0:
                raise ValueError('timeout value must be strictly positive (or -1)')

            # blocking finite
            else:
                start = time()
                waited_time = 0
                with self.__condition:
                    while waited_time < timeout:
                        if self.__lock.acquire(False):
                            return True
                        else:
                            self.__condition.wait(timeout - waited_time)
                            waited_time = time() - start
                return False

        elif timeout != -1:
            raise ValueError('can\'t specify a timeout for a non-blocking call')

        else:
            # non-blocking
            return self.__lock.acquire(False)

    def release(self):
        """Release a lock."""
        self.__lock.release()
        with self.__condition:
            self.__condition.notify()


class InterruptableLock(_InterruptableLock):
    """Lock class for Python v2.7 which behaves more like Python v3.2 threading.Lock
       and allows signals to interrupt waits (by using a threading.Condition with a
       timeout which is interruptable). Supports the context management protocol."""

    def __init__(self):
        super(InterruptableLock, self).__init__(Lock())


class InterruptableRLock(_InterruptableLock):

    def __init__(self):
        super(InterruptableRLock, self).__init__(RLock())


class InterruptableEvent(object):
    """Event class for for Python v2.7 which behaves more like Python v3.2
    threading.Event and allows signals to interrupt waits"""

    def __init__(self):
        self.__event = Event()

    def is_set(self):
        return self.__event.is_set()

    def set(self):
        self.__event.set()

    def clear(self):
        self.__event.clear()

    def wait(self, timeout=None):
        # infinite
        if timeout is None:
            # event with timeout is interruptable
            while not self.__event.wait(60):
                pass
            return True

        # finite - underlying Event will perform timeout argument validation
        return self.__event.wait(timeout)
