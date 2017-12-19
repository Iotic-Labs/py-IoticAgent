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

from threading import Thread
import logging
logger = logging.getLogger(__name__)

from .compat import Queue, Empty, Event, Lock
from .Profiler import profiled_thread

DEBUG_ENABLED = logger.isEnabledFor(logging.DEBUG)


@profiled_thread
def worker(num, queue, stop):
    stop_is_set = stop.is_set
    queue_get = queue.get
    queue_task_done = queue.task_done

    while not stop_is_set():
        try:
            qmsg = queue_get(timeout=0.2)
        except Empty:
            continue  # queue.get timeout ignore

        logger.debug("worker %i calling func %s", num, qmsg['func'])
        try:
            qmsg['func'](*qmsg['args'], **qmsg['kwargs'])
        except:
            try:
                func_name = qmsg['func'].__name__
            except AttributeError:
                func = qmsg['func']
                try:
                    # allow for functools.partial
                    func_name = '%s (partial: %s, %s)' % (func.func.__name__, func.args, func.keywords)
                except:
                    func_name = 'unknown'
            logger.warning("Call failed: %s", func_name, exc_info=DEBUG_ENABLED)
        finally:
            queue_task_done()


class ThreadPool(object):

    def __init__(self, num_workers=1, daemonic=False):
        self.__queue = Queue()
        self.__stop = Event()
        self.__stop.set()
        self.__lock = Lock()
        self.__num_workers = num_workers
        self.__daemonic = daemonic
        self.__threads = []

    def start(self):
        if self.__stop.is_set():
            self.__stop.clear()
            for i in range(0, self.__num_workers):
                thread = Thread(target=worker, name=('tp-%d' % i), args=(i, self.__queue, self.__stop,))
                thread.daemon = self.__daemonic
                self.__threads.append(thread)
            for thread in self.__threads:
                thread.start()

    def submit(self, func, *args, **kwargs):
        with self.__lock:
            self.__queue.put({'func': func, 'args': args, 'kwargs': kwargs})

    def stop(self):
        if not self.__stop.is_set():
            self.__stop.set()
            for thread in self.__threads:
                thread.join()
            del self.__threads[:]
