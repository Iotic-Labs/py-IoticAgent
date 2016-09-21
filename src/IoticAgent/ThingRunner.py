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

from threading import Event, Thread
import logging
logger = logging.getLogger(__name__)

from IoticAgent import IOT


class ThingRunner(object):
    """Automates, starting, stopping and running of an Agent instance, either in the foreground (blocking) or
    background. Create a subclass to use, e.g.:

        #!python
        class MyRunner(ThingRunner):
            # only required if want to add own fields to class instance
            def __init__(self, other, arguments, config=None):
                super(ThingRunner, self).__init__(config=config)
                # own class setup goes here

            def main(self):
                while True:
                    # do stuff here

                    # end on shutdown request
                    if self.wait_for_shutdown(1):
                        break

        # runs in foreground, blocking
        MyRunner().run('other', 'arguments', config='agent.ini')

    Optionally implement `on_startup` or `on_shutdown` to perform one-off actions at the beginning/end of the agent's
    run cycle.
    """

    def __init__(self, config=None):
        """config: IOT.Client config file to use (or None to try to use default location"""
        self.__client = IOT.Client(config=config)
        self.__shutdown = Event()
        self.__bgthread = None

    def run(self, background=False):
        """Runs `on_startup`, `main` and `on_shutdown`, blocking until finished, unless background is set."""
        if self.__bgthread:
            raise Exception('run has already been called (since last stop)')
        self.__shutdown.clear()
        if background:
            self.__bgthread = Thread(target=self.__run, name=('bg_' + self.__client.agent_id))
            self.__bgthread.daemon = True
            self.__bgthread.start()
        else:
            self.__run()

    def __run(self):
        with self.__client:
            logger.debug('Calling on_startup')
            self.on_startup()
            logger.debug('Calling main')
            try:
                self.main()
            except Exception as ex:  # pylint: disable=broad-except
                exception = ex
                if not isinstance(ex, KeyboardInterrupt):
                    logger.warning('Exception in main(): %s', ex)
            else:
                exception = None
            logger.debug('Calling on_shutdown')
            self.on_shutdown(exception)

    def stop(self, timeout=None):
        """Requests device to stop running, waiting at most the given timout in seconds (fractional). Has no effect if
        `run()` was not called with background=True set."""
        self.__shutdown.set()
        if self.__bgthread:
            logger.debug('Stopping bgthread')
            self.__bgthread.join(timeout)
            if self.__bgthread.is_alive():
                logger.warning('bgthread did not finish within timeout')
            self.__bgthread = None

    @property
    def client(self):
        """[Client](./IOT/Client.m.html#IoticAgent.IOT.Client.Client) instance in use by this runner"""
        return self.__client

    @property
    def shutdown_requested(self):
        """Whether `stop()` has been called and thus the device should be shutting down"""
        return self.__shutdown.is_set()

    def wait_for_shutdown(self, timeout=None):
        """Blocks until shutdown has been requested (or the timeout has been reached, if specified). False is returned
        for the latter, True otherwise."""
        return self.__shutdown.wait(timeout)

    def on_startup(self):
        """One-off tasks to perform straight **after** agent startup."""
        pass

    def main(self):  # pylint: disable=no-self-use
        """Application logic goes here. Should return (or raise exception) to end program run. Should check whether the
        `shutdown_requested` property is True an return if this is the case."""
        pass

    def on_shutdown(self, exc):  # pylint: disable=no-self-use
        """One-off tasks to perform on just before agent shutdown. exc is the exception which caused the shutdown (from
        the `main()` function) or None if the shutdown was graceful. This is useful if one only wants to perform
        certains tasks on success. This is not called if `on_startup()` was not successful. It is possible that due to
        e.g. network problems the agent cannot be used at this point.
        If not overriden, the exception will be re-raised."""
        if exc is not None:
            raise exc
