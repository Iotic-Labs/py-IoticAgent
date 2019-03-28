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

import logging
logger = logging.getLogger(__name__)

from sys import version_info, exc_info

try:
    BlockingIOError
except NameError:
    # Python < 2.7.9 & < 3.4
    from io import BlockingIOError  # pylint: disable=redefined-builtin

from ssl import SSLError
from threading import Thread
from socket import timeout as SocketTimeout

from ..third.amqp import Connection, Message, exceptions

from .Profiler import profiled_thread
from .compat import raise_from, Event, RLock, monotonic, SocketError
from .Exceptions import LinkException

DEBUG_ENABLED = logger.isEnabledFor(logging.DEBUG)

# Currently this is not configurable
CONN_RETRY_DELAY_SECONDS = 5


class AmqpLink(object):  # pylint: disable=too-many-instance-attributes

    """Helper class to deal with AMQP connection.
    """

    def __init__(self, host, vhost, prefix, epid, passwd, msg_callback, ka_callback,  # pylint: disable=too-many-locals
                 send_ready_callback, sslca=None, prefetch=128, ackpc=0.5, acksecs=1, heartbeat=30, socket_timeout=10,
                 startup_ignore_exc=False):
        """
        `host`: Broker 'host:port'

        `vhost`: Virtualhost name

        `prefix`: username prefix for amqp login

        `epid`: entity process ID

        `passwd`: password

        `msg_callback`: function callback for messages. Arguments: message

        `ka_callback`: function callback for keepalives, Arguments: none

        `send_ready_callback`: callback on send thread readiness. Arguments: last disconnection time

        `sslca`: Server Certificate

        `prefetch` max number of messages to get on amqp connection drain

        `ackpc` 1..0 percentage of prefetch size of ack'

        `acksecs` max number of seconds between ack messages

        `heartbeat` Every n messages or acksecs send a amqp heartbeat tick

        `socket_timeout` Timeout of underlying sockets both for connection and subsequent operations

        `startup_ignore_exc` On startup only, whether to ignore exceptions until socket_timeout has elapsed. This means
                             that e.g. an access-refused will result in a retry on startup (assuming `socket_timeout`
                             seconds haven't elapsed yet) rather than immediately failing.
        """
        self.__host = host
        self.__vhost = vhost
        self.__prefix = prefix
        self.__epid = epid
        self.__passwd = passwd
        #
        self.__msg_callback = msg_callback
        self.__ka_callback = ka_callback
        self.__send_ready_callback = send_ready_callback
        #
        self.__sslca = sslca
        self.__prefetch = prefetch
        self.__ackpc = ackpc
        self.__ack_threshold = self.__prefetch * self.__ackpc
        self.__acksecs = acksecs
        self.__heartbeat = heartbeat
        self.__socket_timeout = socket_timeout
        #
        self.__unacked = 0
        self.__last_id = None
        #
        self.__end = Event()
        self.__recv_ready = Event()
        self.__recv_thread = None
        self.__send_ready = Event()
        self.__send_lock = RLock()
        self.__send_channel = None
        self.__ka_channel = None
        self.__send_thread = None
        self.__send_exc_time = None
        self.__send_exc = None     # Used to pass exceptions to blocking calls EG .start
        self.__recv_exc = None
        # Whether to only rely on timeout on startup
        self.__startup_ignore_exc = bool(startup_ignore_exc)

    def start(self):
        """start connection threads, blocks until started
        """
        if not (self.__recv_thread or self.__send_thread):
            self.__end.clear()
            self.__send_ready.clear()
            self.__recv_ready.clear()
            timeout = self.__socket_timeout + 1
            ignore_exc = self.__startup_ignore_exc
            self.__send_exc_clear()
            self.__recv_exc_clear()

            # start & await send thread success (unless timeout reached or an exception has occured)
            self.__send_thread = Thread(target=self.__send_run, name='amqplink_send')
            self.__send_thread.start()
            start_time = monotonic()
            success = False
            while not (success or (not ignore_exc and self.__send_exc) or monotonic() - start_time > timeout):
                success = self.__send_ready.wait(.25)

            if success:
                # start & await receiver thread success
                self.__recv_thread = Thread(target=self.__recv_run, name='amqplink_recv')
                self.__recv_thread.start()
                start_time = monotonic()
                success = False
                while not (success or (not ignore_exc and self.__recv_exc) or monotonic() - start_time >= timeout):
                    success = self.__recv_ready.wait(.25)

            # handler either thread's failure
            if not success:
                logger.warning("AmqpLink Failed to start.  Giving up.")
                self.stop()
                if self.__recv_exc:
                    # prioritise receive thread since this can get access-denied whereas send does not (until sending)
                    raise_from(LinkException('Receive thread failure'), self.__recv_exc)
                elif self.__send_exc:
                    raise_from(LinkException('Send thread failure'), self.__send_exc)
                else:
                    raise LinkException('Unknown link failure (timeout reached)')

        else:
            raise LinkException('amqplink already started')

    def is_alive(self):
        """Helper function to show if send & recv Threads are running
        """
        if self.__send_ready.is_set() and self.__recv_ready.is_set():
            if self.__send_thread is not None and self.__recv_thread is not None:
                return self.__send_thread.is_alive() and self.__recv_thread.is_alive()
        return False

    def stop(self):
        """disconnect, blocks until stopped
        """
        self.__end.set()
        if self.__recv_thread:
            self.__recv_thread.join()
            self.__recv_thread = None
        if self.__send_thread:
            self.__send_thread.join()
            self.__send_thread = None

    @property
    def last_send_exc_time(self):
        """Timestamp (or None) at which send thread last failed
        """
        return self.__send_exc_time

    def __del__(self):
        self.stop()

    def send(self, body, content_type='application/ubjson', timeout=5):
        """timeout indicates amount of time to wait for sending thread to be ready. set to larger than zero to wait
        (in seconds, fractional) or None to block.
        """
        if self.__send_ready.wait(timeout):
            try:
                with self.__send_lock:
                    # access denied response might be received inside send thread rather than here how to best handle?
                    self.__send_channel.basic_publish(msg=Message(body, delivery_mode=2, content_type=content_type),
                                                      exchange=self.__epid)
            except exceptions.AccessRefused as exc:
                raise_from(LinkException('Access denied'), exc)
            except (exceptions.AMQPError, SocketError) as exc:
                raise_from(LinkException('amqp/transport failure'), exc)
            except Exception as exc:  # pylint: disable=broad-except
                raise_from(LinkException('unexpected failure'), exc)
        else:
            exc = self.__send_exc
            if exc:
                raise_from(LinkException('Sender unavailable'), exc)
            else:
                raise LinkException('Sender unavailable (unknown error)')

    @classmethod
    def __get_ssl_context(cls, sslca=None):
        """Make an SSLConext for this Python version using public or sslca
        """
        if ((version_info[0] == 2 and (version_info[1] >= 7 and version_info[2] >= 5)) or
                (version_info[0] == 3 and version_info[1] >= 4)):
            logger.debug('SSL method for 2.7.5+ / 3.4+')
            # pylint: disable=no-name-in-module
            from ssl import SSLContext, PROTOCOL_TLSv1_2, CERT_REQUIRED, OP_NO_COMPRESSION
            ctx = SSLContext(PROTOCOL_TLSv1_2)
            ctx.set_ciphers('HIGH:!SSLv3:!TLSv1:!aNULL:@STRENGTH')
            # see CRIME security exploit
            ctx.options |= OP_NO_COMPRESSION
            # the following options are used to verify the identity of the broker
            if sslca:
                ctx.load_verify_locations(sslca)
                ctx.verify_mode = CERT_REQUIRED
                ctx.check_hostname = False
            else:
                # Verify public certifcates if sslca is None (default)
                from ssl import Purpose  # pylint: disable=no-name-in-module
                ctx.load_default_certs(purpose=Purpose.SERVER_AUTH)
                ctx.verify_mode = CERT_REQUIRED
                ctx.check_hostname = True

        elif version_info[0] == 3 and version_info[1] < 4:
            logger.debug('Using SSL method for 3.2+, < 3.4')
            # pylint: disable=no-name-in-module
            from ssl import SSLContext, CERT_REQUIRED, PROTOCOL_SSLv23, OP_NO_SSLv2, OP_NO_SSLv3, OP_NO_TLSv1
            ctx = SSLContext(PROTOCOL_SSLv23)
            ctx.options |= (OP_NO_SSLv2 | OP_NO_SSLv3 | OP_NO_TLSv1)
            ctx.set_ciphers('HIGH:!SSLv3:!TLSv1:!aNULL:@STRENGTH')
            # the following options are used to verify the identity of the broker
            if sslca:
                ctx.load_verify_locations(sslca)
                ctx.verify_mode = CERT_REQUIRED
            else:
                # Verify public certifcates if sslca is None (default)
                ctx.set_default_verify_paths()
                ctx.verify_mode = CERT_REQUIRED

        else:
            raise Exception("Unsupported Python version %s" % '.'.join(str(item) for item in version_info[:3]))

        return ctx

    def __recv_ka_cb(self, msg):
        try:
            if self.__recv_ready.wait(2):
                self.__ka_channel.basic_publish(msg=Message(b'', delivery_mode=1), routing_key='keep-alive',
                                                exchange=self.__epid)
            else:
                logger.warning('Recv thread not ready in 2 seconds, not sending KA response')
        except:
            logger.warning('Failed to send KA response')
        try:
            self.__ka_callback()
        except:
            logger.exception("__recv_ka_cb exception ignored.")

    def __recv_cb(self, msg):
        """Calls user-provided callback and marks message for Ack regardless of success
        """
        try:
            self.__msg_callback(msg)
        except:
            logger.exception("AmqpLink.__recv_cb exception calling msg_callback")
        finally:
            # only works if all messages handled in series
            self.__last_id = msg.delivery_tag
            self.__unacked += 1

    @profiled_thread  # noqa (complexity)
    def __recv_run(self):  # pylint: disable=too-many-branches,too-many-statements
        """Main receive thread/loop
        """
        while not self.__end.is_set():
            self.__unacked = 0
            self.__last_id = None

            try:
                self.__recv_ready.clear()  # Ensure event is cleared for EG network failure/retry loop
                with Connection(userid=self.__prefix + self.__epid,
                                password=self.__passwd,
                                virtual_host=self.__vhost,
                                heartbeat=self.__heartbeat,
                                connect_timeout=self.__socket_timeout,
                                operation_timeout=self.__socket_timeout,
                                ssl=self.__get_ssl_context(self.__sslca),
                                host=self.__host) as conn,\
                        conn.channel(auto_encode_decode=False) as channel_data,\
                        conn.channel() as channel_ka:
                    logger.debug('Connected, using cipher %s', conn.transport.sock.cipher()[0])

                    channel_data.basic_qos(prefetch_size=0, prefetch_count=self.__prefetch, a_global=False)
                    # exclusive=True.  There can be only one (receiver)
                    msgtag = channel_data.basic_consume(queue=self.__epid, exclusive=True, callback=self.__recv_cb)
                    acktag = channel_ka.basic_consume(queue=('%s_ka' % self.__epid), exclusive=True, no_ack=True,
                                                      callback=self.__recv_ka_cb)
                    self.__ka_channel = channel_ka
                    self.__recv_exc_clear(log_if_exc_set='reconnected')
                    self.__recv_ready.set()
                    try:
                        #
                        # Drain loop
                        while not self.__end.is_set():
                            try:
                                while not self.__end.is_set() and self.__unacked < self.__ack_threshold:
                                    # inner loop to handle all outstanding amqp messages
                                    conn.drain_events(.1)
                            except SocketTimeout:
                                pass
                            # either have waited for .1s or threshold reached, so always ack
                            if self.__unacked:
                                logger.debug('acking (%d) up to %s', self.__unacked, self.__last_id)
                                channel_data.basic_ack(self.__last_id, multiple=True)
                                self.__unacked = 0
                            conn.heartbeat_tick()
                    finally:
                        self.__recv_ready.clear()
                        try:
                            channel_data.basic_cancel(msgtag)
                            channel_ka.basic_cancel(acktag)
                        except:
                            pass

            except exceptions.AccessRefused:
                self.__recv_log_set_exc_and_wait('Access Refused (Credentials already in use?)')
            except exceptions.ConnectionForced:
                self.__recv_log_set_exc_and_wait('Disconnected by broker (ConnectionForced)')
            except SocketTimeout:
                self.__recv_log_set_exc_and_wait('SocketTimeout exception.  wrong credentials, vhost or prefix?')
            except SSLError:
                self.__recv_log_set_exc_and_wait('ssl.SSLError Bad Certificate?')
            except (exceptions.AMQPError, SocketError):
                self.__recv_log_set_exc_and_wait('amqp/transport failure, sleeping before retry')
            except:
                self.__recv_log_set_exc_and_wait('unexpected failure, exiting', wait_seconds=0)
                break

        logger.debug('finished')

    def __recv_log_set_exc_and_wait(self, msg, level=None, wait_seconds=CONN_RETRY_DELAY_SECONDS):
        """Equivalent to __send_log_set_exc_and_wait but for receiver thread"""
        logger.log(
            ((logging.DEBUG if self.__recv_exc else logging.ERROR) if level is None else level),
            msg,
            exc_info=DEBUG_ENABLED
        )
        self.__recv_exc = exc_info()[1]
        self.__end.wait(wait_seconds)

    def __recv_exc_clear(self, log_if_exc_set=None):
        """Equivalent to __send_exc_clear"""
        if not (log_if_exc_set is None or self.__recv_exc is None):
            logger.info(log_if_exc_set)
        self.__recv_exc = None

    @profiled_thread  # noqa (complexity)
    def __send_run(self):
        """Send request thread
        """
        while not self.__end.is_set():
            try:
                with Connection(userid=self.__prefix + self.__epid,
                                password=self.__passwd,
                                virtual_host=self.__vhost,
                                heartbeat=self.__heartbeat,
                                connect_timeout=self.__socket_timeout,
                                operation_timeout=self.__socket_timeout,
                                ssl=self.__get_ssl_context(self.__sslca),
                                host=self.__host) as conn,\
                        conn.channel(auto_encode_decode=False) as channel:

                    self.__send_channel = channel
                    self.__send_exc_clear(log_if_exc_set='reconnected')
                    self.__send_ready.set()
                    try:
                        self.__send_ready_callback(self.__send_exc_time)

                        while not self.__end.is_set():
                            with self.__send_lock:
                                try:
                                    # deal with any incoming messages (AMQP protocol only, not QAPI)
                                    conn.drain_events(0)
                                except (BlockingIOError, SocketTimeout):
                                    pass
                                conn.heartbeat_tick()
                            # idle
                            self.__end.wait(.25)
                    finally:
                        # locked so can make sure another call to send() is not made whilst shutting down
                        with self.__send_lock:
                            self.__send_ready.clear()

            except exceptions.AccessRefused:
                self.__send_log_set_exc_and_wait('Access Refused (Credentials already in use?)')
            except exceptions.ConnectionForced:
                self.__send_log_set_exc_and_wait('Disconnected by broker (ConnectionForced)')
            except SocketTimeout:
                self.__send_log_set_exc_and_wait('SocketTimeout exception.  wrong credentials, vhost or prefix?')
            except SSLError:
                self.__send_log_set_exc_and_wait('ssl.SSLError Bad Certificate?')
            except (exceptions.AMQPError, SocketError):
                self.__send_log_set_exc_and_wait('amqp/transport failure, sleeping before retry')
            except:
                self.__send_log_set_exc_and_wait('unexpected failure, exiting', wait_seconds=0)
                break
        logger.debug('finished')

    def __send_log_set_exc_and_wait(self, msg, level=None, wait_seconds=CONN_RETRY_DELAY_SECONDS):
        """To be called in exception context only.

        msg - message to log
        level - logging level. If not specified, ERROR unless it is a repeated failure in which case DEBUG. If
        specified, the given level will always be used.
        wait_seconds - how long to pause for (so retry is not triggered immediately)
        """
        logger.log(
            ((logging.DEBUG if self.__send_exc else logging.ERROR) if level is None else level),
            msg,
            exc_info=DEBUG_ENABLED
        )
        self.__send_exc_time = monotonic()
        self.__send_exc = exc_info()[1]
        self.__end.wait(wait_seconds)

    def __send_exc_clear(self, log_if_exc_set=None):
        """Clear send exception and time. If exception was previously was set, optionally log log_if_exc_set at INFO
        level.
        """
        if not (log_if_exc_set is None or self.__send_exc is None):
            logger.info(log_if_exc_set)
        self.__send_exc_time = None
        self.__send_exc = None
