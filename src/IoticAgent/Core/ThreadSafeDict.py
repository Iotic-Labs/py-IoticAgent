#!/usr/bin/env python3
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

from threading import Thread
try:
    from time import perf_counter
except:
    from time import clock as perf_counter  # python2
import inspect

from .compat import Lock


class ThreadSafeDict(dict):

    """ThreadSafeDict: Simple locking dict.

    Create a dict in a familiar way.
    d = ThreadSafeDict({'a': 1, 'b': 2})

    Lock the dict using with.
    with d:
        d['c'] = 3
        del d['b']
    """

    def __init__(self, * p_arg, ** n_arg):
        dict.__init__(self, * p_arg, ** n_arg)
        self.__lock = Lock()
        self.__debug = False

    def set_debug(self, debug=True):
        self.__debug = debug

    def __enter__(self):
        if self.__debug:
            logger.debug("__enter__:" + inspect.stack()[1])
        self.__lock.acquire()
        return self

    def __exit__(self, typ, value, traceback):
        if self.__debug:
            logger.debug("__exit__:" + inspect.stack()[1])
        self.__lock.release()


# This test function could be moved to unit tests but it's not that interesting.
# pylint: disable=redefined-outer-name,invalid-name
def tester(i, d):
    x = 0  # pylint: disable=invalid-name
    while x < 25000:
        with d:
            if i not in d:
                d[i] = 0
            d[i] += 1
            x = d[i]
    with d:
        logger.info("tester %i done: %s", i, d)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    start = perf_counter()
    test_dict = ThreadSafeDict()
    # test_dict.set_debug()
    s = []
    for i in range(8):
        t = Thread(target=tester, args=(i, test_dict,))
        t.daemon = True
        t.start()
        s.append(t)
    for t in s:
        t.join()
    logger.info('time: %s', perf_counter() - start)
