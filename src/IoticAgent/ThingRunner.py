# Copyright (c) 2019 Iotic Labs Ltd. All rights reserved.
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

from sys import exc_info as get_exc_info
from enum import Enum, unique
from threading import Event, Thread
import logging
logger = logging.getLogger(__name__)
DEBUG_ENABLED = logger.isEnabledFor(logging.DEBUG)

from IoticAgent.IOT import Client
from IoticAgent.IOT.Exceptions import LinkException, IOTSyncTimeout
from IoticAgent.Core.utils import validate_nonnegative_int


@unique
class RunContext(Enum):
    """Passed to `ThingRunner.on_exception`"""
    ON_STARTUP = 'on_startup'
    MAIN = 'main'


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
        MyRunner('other', 'arguments', config='agent.ini').run()

    Optionally implement `on_startup` or `on_shutdown` to perform one-off actions at the beginning/end of the agent's
    run cycle.
    """

    def __init__(self, config=None, retry_timeout=15):
        """
        `config` (optional) IOT.Client config file to use (or None to try to use default location)

        `retry_timeout` (int, optional): Number of seconds to wait before retrying. See also `on_exception`.
        """
        self.__client = Client(config=config)
        self.__shutdown = Event()
        self.__bgthread = None
        self.__retry_timeout = validate_nonnegative_int(retry_timeout, 'retry_timeout')

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
        ctx = RunContext.ON_STARTUP

        while True:
            exc_occurred = False
            try:
                with self.__client:
                    if ctx == RunContext.ON_STARTUP:
                        logger.debug('Calling on_startup')
                        self.on_startup()
                        ctx = RunContext.MAIN

                    logger.debug('Calling main')
                    self.main()
            except KeyboardInterrupt:
                # Enable on_shutdown to run normally
                pass
            except:
                exc_occurred = True
                if self.__handle_exception(ctx):
                    logger.debug('Sleeping before retry')
                    if not self.wait_for_shutdown(self.__retry_timeout):
                        continue

            # Normal run finished
            break

        self.__shutdown.set()

        # Shutdown not applicable if on_startup did not finish
        if not (exc_occurred or ctx == RunContext.ON_STARTUP):
            logger.debug('Calling on_shutdown')
            try:
                self.on_shutdown(None)
            except:
                logger.exception('Exception in on_shutdown callback')

    # Will re-raise exception, where appropriate and also call relevant callbacks. A True response indicates the run
    # should be re-tried.
    def __handle_exception(self, ctx):
        exc_info = get_exc_info()

        try:
            if self.on_exception(ctx, exc_info):
                logger.debug('Will retry %s', ctx.value)
                return True
        except KeyboardInterrupt:
            # Exit immediately without running on_shutdown hook as no different to being caught inside on_shutdown.
            raise
        except:
            logger.exception('Exception in on_exception callback')

        self.__shutdown.set()

        # Failure in on_startup should not result in shutdown callback
        if ctx != RunContext.ON_STARTUP:
            try:
                if self.on_shutdown(exc_info):
                    return False
            except KeyboardInterrupt:
                raise
            except:
                logger.exception('Exception in on_shutdown callback')

        raise  # pylint: disable=misplaced-bare-raise

    def stop(self, timeout=None):
        """Requests device to stop running, waiting at most the given timout in seconds (fractional). Has no effect if
        `run()` was not called with background=True set. Returns True if successfully stopped (or already not running).
        """
        stopped = True
        self.__shutdown.set()
        if self.__bgthread:
            logger.debug('Stopping bgthread')
            self.__bgthread.join(timeout)
            if self.__bgthread.is_alive():
                logger.warning('bgthread did not finish within timeout')
                stopped = False
            self.__bgthread = None
        return stopped

    @property
    def client(self):
        """[Client](./IOT/Client.m.html#IoticAgent.IOT.Client.Client) instance in use by this runner"""
        return self.__client

    @property
    def shutdown_requested(self):
        """Whether `stop()` has been called, an exception has occurred (which does not result in a retry) or the
        implemented main loop has finished and thus the device should be shutting down."""
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

    def on_exception(self, ctx, exc_info):  # pylint: disable=no-self-use,unused-argument
        """Called when an exception occurs within runner methods (or initialisation). If the return value evalutes to
        True, the method in question will be re-tried (after `retry_timeout` seconds wait). Otherwise the exception will
        be re-raised (the default). Note that KeyboardInterrupt will not result in this method being called and instead
        cause a shutdown.

        `ctx` One of `RunContext`. Indicates at what point exception occurred.
        `exc_info` Tuple (as for `sys.exc_info()`) of the exception
        """
        pass

    def on_shutdown(self, exc_info):  # pylint: disable=no-self-use
        """One-off tasks to perform on just before agent shutdown. exc_info is a tuple (as for `sys.exc_info()`) of the
        exception which caused the shutdown (from the `main()` function) or None if the shutdown was graceful. This is
        useful if one only wants to perform certains tasks on success. This is not called if `on_startup()` was not
        successful. It is possible that due to e.g. network problems the agent cannot be used at this point. If the
        return value evalutes to False, the exception will be re-raised (the default). Note that KeyboardInterrupt will
        not be passed to this method (but will result in this method being called).
        """
        pass


class RetryingThingRunner(ThingRunner):
    """Automatically re-tries on_startup & on_main on network & timeout related failures only."""

    def on_exception(self, ctx, exc_info):
        if issubclass(exc_info[0], (LinkException, IOTSyncTimeout)):
            logger.warning('LinkException/IOTSyncTimeout caught, will retry %s', ctx.value,
                           exc_info=(exc_info if DEBUG_ENABLED else None))
            return True

        return False
