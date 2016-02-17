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

from sys import version_info

try:
    BlockingIOError
except NameError:
    # Python < 2.7.9 & < 3.4
    from io import BlockingIOError  # pylint: disable=redefined-builtin

from ssl import SSLError
from threading import Thread
from socket import timeout as SocketTimeout

from ..third.amqp import Connection, Message, exceptions

from .compat import raise_from, Event, RLock
from .Exceptions import LinkException


class AmqpLink(object):  # pylint: disable=too-many-instance-attributes

    """Helper class to deal with AMQP connection.
    """

    def __init__(self, host, vhost, prefix, epid, passwd, msg_callback, ka_callback,
                 sslca=None, prefetch=128, ackpc=0.5, acksecs=1, heartbeat=30, draintimeout=0.1):
        """
        `host`: Broker 'host:port'
        `vhost`: Virtualhost name
        `prefix`: username prefix for amqp login
        `epid`: entity process ID
        `passwd`: password
        `msg_callback`: function callback for messages
        `ka_callback`: functionc callback for keepalives

        `sslca`: Server Certificate
        `prefetch` (default 128) max number of messages to get on amqp connection drain
        `ackpc` (default 0.5) 1..0 percentage of prefetch size of ack'
        `acksecs` (default 1) max number of seconds between ack messages
        `heartbeat` (default 10) Every n messages or acksecs send a amqp heartbeat tick
        `draintimeout` (default 0.05) 0.05=1s/20 Wait for messages from the network.
        """
        self.__host = host
        self.__vhost = vhost
        self.__prefix = prefix
        self.__epid = epid
        self.__passwd = passwd
        #
        self.__msg_callback = msg_callback
        self.__ka_callback = ka_callback
        #
        self.__sslca = sslca
        self.__prefetch = prefetch
        self.__ackpc = ackpc
        self.__ack_threshold = self.__prefetch * self.__ackpc
        self.__acksecs = acksecs
        self.__heartbeat = heartbeat
        self.__draintimeout = draintimeout
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
        self.__send_exc = None     # Used to pass exceptions to blocking calls EG .start
        self.__recv_exc = None

    def start(self):
        """start connection threads, blocks until started
        """
        if not (self.__recv_thread or self.__send_thread):
            # Ensure Events are clear
            self.__end.clear()
            self.__send_ready.clear()
            self.__recv_ready.clear()
            # Start the Threads and ensure send is ready first !
            self.__send_thread = Thread(target=self.__send_run, name='amqplink_send')
            self.__send_thread.start()
            # note: connect_timeout in amqp Connection instance below!
            success = self.__send_ready.wait(timeout=2.5)
            if success:
                self.__recv_thread = Thread(target=self.__recv_run, name='amqplink_recv')
                self.__recv_thread.start()
                success = self.__recv_ready.wait(timeout=2.5)
            #
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

    def __del__(self):
        self.stop()

    def send(self, body, content_type='application/ubjson', timeout=5):
        """send
           timeout indicates amount of time to wait for receiving thread to be ready. set to larger
           than zero to wait (in seconds, fractional) or None to block.
        """
        # logger.debug('sending: %s', body)
        if self.__send_ready.wait(timeout):
            try:
                with self.__send_lock:
                    # access denied response might be received inside send thread rather than here how to best handle?
                    self.__send_channel.basic_publish(msg=Message(body, delivery_mode=2, content_type=content_type),
                                                      exchange=self.__epid)
            except exceptions.AccessRefused as exc:
                raise_from(LinkException('Access denied'), exc)
            except (exceptions.AMQPError, OSError) as exc:
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
        if (version_info[0] == 2 and (version_info[1] >= 7 and version_info[2] >= 9)) or (version_info[0] == 3 and version_info[1] >= 4):
            logger.debug('SSL method for 2.7.9+ / 3.4+')
            from ssl import SSLContext, PROTOCOL_TLSv1_2, CERT_REQUIRED, OP_NO_COMPRESSION  # pylint: disable=no-name-in-module
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

    def __recv_run(self):  # noqa (complexity) pylint: disable=too-many-branches,too-many-statements
        """Main receive thread/loop
        """
        while not self.__end.is_set():
            self.__unacked = 0
            self.__last_id = None
            #
            # Connect
            try:
                self.__recv_ready.clear()  # Ensure event is cleared for EG network failure/retry loop
                with Connection(userid=self.__prefix + self.__epid,
                                password=self.__passwd,
                                virtual_host=self.__vhost,
                                heartbeat=self.__heartbeat,
                                connect_timeout=2,
                                operation_timeout=2,
                                ssl=self.__get_ssl_context(self.__sslca),
                                host=self.__host) as conn,\
                        conn.channel(auto_encode_decode=False) as channel_data,\
                        conn.channel() as channel_ka:
                    channel_data.basic_qos(prefetch_size=0, prefetch_count=self.__prefetch, a_global=False)
                    # exclusive=True.  There can be only one (receiver)
                    msgtag = channel_data.basic_consume(queue=self.__epid, exclusive=True, callback=self.__recv_cb)
                    acktag = channel_ka.basic_consume(queue=('%s_ka' % self.__epid), exclusive=True, no_ack=True,
                                                      callback=self.__recv_ka_cb)
                    self.__recv_exc = None
                    self.__recv_ready.set()
                    self.__ka_channel = channel_ka
                    logger.debug('ready')

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
                            pass  # note: Can't do anything here? EG network down
                        # todo: also clear other channel (for KA) here
                        # todo: ACK any remaining messages if possible. Otherwise might have to keep track of seq numbers
                        # of processed messages so can ACK when connection comes back up.

            except exceptions.AccessRefused as exc:
                logger.error("Access Refused (Credentials already in use?)")
                self.__recv_exc = exc
                self.__end.wait(2)
            except exceptions.ConnectionForced as exc:
                logger.error('Disconnected by broker: %s', exc)
                self.__send_exc = exc
                self.__end.wait(2)
            except SocketTimeout as exc:
                logger.warning("SocketTimeout exception.  wrong credentials, vhost or prefix?")
                self.__recv_exc = exc
                self.__end.wait(2)
            except SSLError as exc:
                logger.error("ssl.SSLError Bad Certificate?")
                self.__recv_exc = exc
                self.__end.wait(2)
            except (exceptions.AMQPError, OSError) as exc:
                logger.error('amqp/transport failure, sleeping before retry')
                self.__recv_exc = exc
                self.__end.wait(2)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception('unexpected failure, exiting')
                # pylint: disable=redefined-variable-type
                self.__recv_exc = exc
                break

        logger.debug('finished')

    def __send_run(self):
        """Send requests only
        """
        while not self.__end.is_set():
            try:
                with Connection(userid=self.__prefix + self.__epid,
                                password=self.__passwd,
                                virtual_host=self.__vhost,
                                heartbeat=self.__heartbeat,
                                connect_timeout=2,
                                operation_timeout=2,
                                ssl=self.__get_ssl_context(self.__sslca),
                                host=self.__host) as conn,\
                        conn.channel(auto_encode_decode=False) as channel:
                    self.__send_channel = channel
                    self.__send_ready.set()
                    logger.debug('ready')
                    try:
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

            except exceptions.ConnectionForced as exc:
                logger.error('Disconnected by broker, will re-try: %s', exc)
                self.__send_ready.clear()
                self.__send_exc = exc
                self.__end.wait(2)
            except (exceptions.AMQPError, OSError) as exc:
                logger.error('amqp/transport failure, sleeping before retry', exc_info=True)
                self.__send_ready.clear()
                self.__send_exc = exc
                self.__end.wait(2)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception('unexpected failure, exiting')
                self.__send_ready.clear()
                # pylint: disable=redefined-variable-type
                self.__send_exc = exc
                break
        logger.debug('finished')
