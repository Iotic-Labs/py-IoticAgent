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
"""The Client object used to initiate connection to Iotic Space
"""

from __future__ import unicode_literals

from warnings import warn
from functools import partial
import logging
logger = logging.getLogger(__name__)
DEBUG_ENABLED = logger.isEnabledFor(logging.DEBUG)

from IoticAgent.Core import Client as Core_Client, ThreadSafeDict, __version__ as Core_Version
from IoticAgent.Core.compat import Mapping, raise_from, string_types
from IoticAgent.Core.Const import (
    E_FAILED_CODE_NOTALLOWED, E_FAILED_CODE_UNKNOWN, E_FAILED_CODE_MALFORMED, E_FAILED_CODE_INTERNALERROR,
    E_FAILED_CODE_ACCESSDENIED,
    M_CLIENTREF, M_PAYLOAD,
    R_ENTITY, R_FEED, R_CONTROL, R_SUB,
    P_CODE, P_ID, P_LID, P_ENTITY_LID, P_EPID, P_RESOURCE, P_MESSAGE, P_POINT_TYPE, P_POINT_ID, P_DATA,
    SearchScope, SearchType, DescribeScope
)
from IoticAgent.Core.utils import validate_nonnegative_int
from IoticAgent.Core.Validation import Validation

from . import __version__
from .Thing import Thing
from .Config import Config
from .utils import uuid_to_hex, version_string_to_tuple, bool_from, foc_to_str
from .Exceptions import (
    IOTException, IOTUnknown, IOTMalformed, IOTInternalError, IOTAccessDenied, IOTClientError, IOTSyncTimeout,
    IOTNotAllowed
)
from .Point import Control, Point, _POINT_TYPES
from .RemotePoint import RemoteFeed, RemoteControl
from .PointValueHelper import PointDataObjectHandler, RefreshException


class Client(object):  # pylint: disable=too-many-public-methods, too-many-lines

    # Core version targeted by IOT client
    __core_version = '0.6.11'

    def __init__(self, config=None):
        """
        Creates an IOT.Client instance which provides access to Iotic Space

        Args:
            config (optional): The name of the config file containing the connection parameters. Defaults to the name
                of the script +".ini", e.g. `config="my_script.ini"`. Alternatively an existing
                :doc:`IoticAgent.IOT.Config` config object can be specified.
        """
        self.__core_version_check()
        logger.info('IOT version: %s', __version__)
        #
        if isinstance(config, string_types) or config is None:
            self.__config = Config(config)
        elif isinstance(config, Config):
            self.__config = config
        else:
            raise ValueError('config should be string or Config instance')
        #
        if any(self.__config.get('agent', item) is None for item in ('host', 'epid', 'passwd', 'token')):
            raise ValueError('Minimum configuration for IoticAgent is host, epid, passwd and token\n'
                             'Create file "%s" with contents\n[agent]\nhost = w\nepid = x\npasswd = y\ntoken = z'
                             % self.__config._file_loc())
        self.__sync_timeout = validate_nonnegative_int(self.__config.get('iot', 'sync_request_timeout'),
                                                       'iot.sync_request_timeout', allow_zero=False)
        self.__config.setup_logging()
        #
        try:
            self.__client = Core_Client(host=self.__config.get('agent', 'host'),
                                        vhost=self.__config.get('agent', 'vhost'),
                                        epId=self.__config.get('agent', 'epid'),
                                        lang=self.__config.get('agent', 'lang'),
                                        passwd=self.__config.get('agent', 'passwd'),
                                        token=self.__config.get('agent', 'token'),
                                        prefix=self.__config.get('agent', 'prefix'),
                                        sslca=self.__config.get('agent', 'sslca'),
                                        network_retry_timeout=self.__config.get('core', 'network_retry_timeout'),
                                        socket_timeout=self.__config.get('core', 'socket_timeout'),
                                        auto_encode_decode=bool_from(self.__config.get('core', 'auto_encode_decode'),
                                                                     default=True),
                                        send_queue_size=self.__config.get('core', 'queue_size'),
                                        throttle_conf=self.__config.get('core', 'throttle'),
                                        max_encoded_length=self.__config.get('core', 'max_encoded_length'),
                                        startup_ignore_exc=bool_from(self.__config.get('core', 'startup_ignore_exc'),
                                                                     default=False),
                                        conn_retry_delay=self.__config.get('core', 'conn_retry_delay'),
                                        conn_error_log_threshold=self.__config.get('core', 'conn_error_log_threshold'))
        except ValueError as ex:
            raise_from(ValueError('Configuration error'), ex)

        #
        # Callbacks for updating own resource cache (used internally only)
        self.__client.register_callback_created(self.__cb_created)
        self.__client.register_callback_duplicate(self.__cb_duplicated)
        self.__client.register_callback_reassigned(self.__cb_reassigned)
        self.__client.register_callback_deleted(self.__cb_deleted)
        self.__client.register_callback_recent_data(self.__cb_recent_data)
        #
        # Keeps track of newly created things (the requests for which originated from this agent)
        self.__new_things = ThreadSafeDict()
        # Allows client to forward e.g. Point creation callbacks to the relevant Thing instance. This contains the most
        # recent instance of any single Thing (since creation requests can be performed more than once).
        self.__private_things = ThreadSafeDict()
        # PointDataObjectHandler cache
        self.__point_data_handlers = ThreadSafeDict()
        # recent data callbacks by request id
        self.__recent_data_callbacks = ThreadSafeDict()

    @property
    def agent_id(self):
        """
        Agent id (aka epId) in use for this client instance
        """
        return self.__client.epId

    @property
    def default_lang(self):
        """
        Language in use when not explicitly specified (in meta related requests). Will be set to container default
        if was not set in configuration. Before client has started this might be None.
        """
        return self.__client.default_lang

    @property
    def local_meta(self):
        """
        Whether container-local metadata functionality (e.g. search) is available in this container. Before calling
        start() this will always be False.
        """
        return self.__client.local_meta

    def start(self):
        """
        Open a connection to Iotic Space.  `start()` is called by `__enter__` which allows the python `with` syntax to
         be used.

        **Example 0:**

        Calling start() implicitly using with. Minimal example with no exception handling:

        ::

            with IOT.Client(config="my_script.ini") as client:
                client.create_thing("my_thing")

        **Example 1**

        Calling start() implicitly using with.  This handles the finally for you.
        `Recommended`:

        ::

            try:
                with IOT.Client(config="my_script.ini") as client:
                    try:
                        client.create_thing("my_thing")
                    except IOTException as exc:
                        # handle exception
            except Exception as exc:  # not possible to connect
                print(exc)
                import sys
                sys.exit(1)

        **Example 2**

        Calling start() explicitly (no with). Be careful, you have to put a finally in your try blocks otherwise your
        client might remain connected.

        ::

            try:
                client = IOT.Client(config="my_script.ini")
                # wire up callbacks here
                client.start()
            except Exception as exc:
                print(exc)
                import sys
                sys.exit(1)

            try:
                client.create_thing("my_thing")
            except IOTException as exc:
                # handle individual exception
            finally:
                client.stop()

        Returns:
            This Client instance

        Raises:
            Exception
        """
        if not self.__client.is_alive():
            self.__client.start()
        return self

    def __enter__(self):
        return self.start()

    def stop(self):
        """
        Close the connection to Iotic Space.  `stop()` is called by `__exit()__` allowing the python `with`
        syntax to be used.  See :doc:`IoticAgent.IOT.Client` client start
        """
        if self.__client.is_alive():
            self.__client.stop()

    def __exit__(self, exc_type, exc_value, traceback):
        return self.stop()

    def __del__(self):
        try:
            self.stop()
        # Don't want on ignored exceptions
        except:
            pass

    @property
    def sync_timeout(self):
        """
        Value of iot.sync_request_timeout configuration option. Used by all synchronous requests to limit total
        request wait time.
        """
        return self.__sync_timeout

    @classmethod
    def __core_version_check(cls):
        core = version_string_to_tuple(Core_Version)
        expected = version_string_to_tuple(cls.__core_version)

        if core[0] != expected[0]:
            raise RuntimeError('Core client dependency major version difference: %s (%s expected)' %
                               (Core_Version, cls.__core_version))
        elif core[1] < expected[1]:
            raise RuntimeError('Core client minor version old: %s (%s known)' % (Core_Version, cls.__core_version))
        elif core[1] > expected[1]:
            warn('Core client minor version difference: %s (%s known)' % (Core_Version, cls.__core_version),
                 RuntimeWarning)
        elif core[2] > expected[2]:
            warn('Core client patch level change: %s (%s known)' % (Core_Version, cls.__core_version),
                 RuntimeWarning)
        else:
            logger.info('Core version: %s', Core_Version)

    def _notify_thing_lid_change(self, from_lid, to_lid):
        """
        Used by Thing instances to indicate that a rename operation has happened
        """
        try:
            with self.__private_things:
                self.__private_things[to_lid] = self.__private_things.pop(from_lid)
        except KeyError:
            logger.warning('Thing %s renamed (to %s), but not in private lookup table', from_lid, to_lid)
        else:
            # renaming could happen before get_thing is called on the original
            try:
                with self.__new_things:
                    self.__new_things[to_lid] = self.__new_things.pop(from_lid)
            except KeyError:
                pass

    def is_connected(self):
        """
        Returns:
            Client's alive state
        """
        return self.__client.is_alive()

    def register_catchall_feeddata(self, callback, callback_parsed=None):
        """
        Registers a callback that is called for all feeddata your Thing receives

        **Example**

        ::

            def feeddata_callback(data):
                print(data)
            ...
            client.register_catchall_feeddata(feeddata_callback)

        Args:
            callback: the function name that you want to be called on receipt of new feed data
            callback_parsed (function reference, optional): callback function to invoke on receipt of feed data. This
                is equivalent to `callback` except the dict includes the `parsed` key which holds the set of values in a
                :doc:`IoticAgent.IOT.Point` PointDataObject instance. If both `callback_parsed` and `callback` have been
                specified, the former takes precedence and `callback` is only called if the point data could not be
                parsed according to its current value description.

        Note:
            `callback_parsed` can only be used if `auto_encode_decode` is enabled for the client instance.

        More details on the contents of the `data` dictionary for feeds see :doc:`IoticAgent.IOT.Thing` Thing.follow.
        """
        if callback_parsed:
            callback = self._get_parsed_feed_callback(callback_parsed, callback)
        return self.__client.register_callback_feeddata(callback)

    def register_catchall_controlreq(self, callback, callback_parsed=None):
        """
        Registers a callback that is called for all control requests received by your Thing

        **Example**

        ::

            def controlreq_callback(data):
                print(data)
            ...
            client.register_catchall_controlreq(controlreq_callback)

        Args:
            callback: the function name that you want to be called on receipt of a new control request
            callback_parsed (function reference, optional): callback function to invoke on receipt of a control
                ask/tell. This is equivalent to `callback` except the dict includes the `parsed` key which holds the set
                of values in a :doc:`IoticAgent.IOT.Point` PointDataObject instance. If both `callback_parsed` and
                `callback` have been specified, the former takes precedence and `callback` is only called if the point
                data could not be parsed according to its current value description.

        More details on the contents of the `data` dictionary for controls see :doc:`IoticAgent.IOT.Thing`
        create_control
        """
        if callback_parsed:
            callback = self._get_parsed_control_callback(callback_parsed, callback)
        return self.__client.register_callback_controlreq(callback)

    def register_callback_subscription(self, callback):
        """
        Register a callback for subscription count change notification.  This gets called whenever something *else*
        subscribes to your thing.

        Note:
            It is not called when you subscribe to something else.

        The payload passed to your callback is an OrderedDict with the following keys

        ::

            r         : R_FEED or R_CONTROL # the type of the point
            lid       : <name>              # the local name of your *Point*
            entityLid : <name>              # the local name of your *Thing*
            subCount  : <count>             # the total number of remote Things
                                            # that subscribe to your point

        **Example**

        ::

            def subscription_callback(args):
                print(args)
            ...
            client.register_callback_subscription(subscription_callback)

        This would print out something like the following

        ::

            OrderedDict([('r', 2), ('lid', 'My_First_Point'),
                         ('entityLid', 'My_First_Thing'), ('subCount', 13)])
        """
        return self.__client.register_callback_subscription(callback)

    @classmethod
    def __callback_payload_only(cls, callback, msg):
        # Only pass the payload to callback
        callback(msg[M_PAYLOAD])

    def register_callback_created(self, func, serialised=True):
        """
        Register a callback for resource creation.  This will be called when any *new* resource
        is created within your agent.  If `serialised` is not set, the callbacks might arrive
        in a different order to they were requested.

        The payload passed to your callback is an OrderedDict with the following keys

        ::

            r         : R_ENTITY, R_FEED, etc # the type of resource created
            lid       : <name>                # the local name of the resource
            id        : <GUID>                # the global Id of the resource
            epId      : <GUID>                # the global Id of your agent

        Note:
            Resource types are defined in :doc:`IoticAgent.Core.Const`

        **Example**

        ::

            def created_callback(args):
                print(args)
            ...
            client.register_callback_created(created_callback)

        This would print out something like the following on creation of an R_ENTITY

        ::

            OrderedDict([(u'lid', u'new_thing1'), (u'r', 1),
                         (u'epId', u'ffd47b75ea786f55c76e337cdc47665a'),
                         (u'id', u'3f11df0a09588a6a1a9732e3837765f8')]))
        """
        self.__client.register_callback_created(partial(self.__callback_payload_only, func), serialised=serialised)

    def register_callback_duplicate(self, func, serialised=True):
        """
        Register a callback for resource creation but where the resource already exists in Iotic Space. In this case
         the existing reference is passed to you. If `serialised` is not set, the callbacks might arrive in a different
         order to they were requested.

        The payload passed to your callback is an OrderedDict with the following keys:

        ::

            r         : R_ENTITY, R_FEED, etc # the type of existing resource
            lid       : <name>                # the local name of the
                                              # existing resource
            id        : <GUID>                # the global Id of the
                                              # existing resource
            epId      : <GUID>                # the global Id of your agent

        Note:
            Resource types are defined in :doc:`IoticAgent.Core.Const`

        **Example**

        ::

            def duplicated_callback(args):
                print(args)
            ...
            client.register_callback_created(duplicated_callback)

        This would print out something like the following on re-creation of an R_ENTITY

        ::

            OrderedDict([(u'lid', u'new_thing1'), (u'r', 1),
                         (u'epId', u'ffd47b75ea786f55c76e337cdc47665a'),
                         (u'id', u'3f11df0a09588a6a1a9732e3837765f8')]))
        """
        self.__client.register_callback_duplicate(partial(self.__callback_payload_only, func), serialised=serialised)

    def register_callback_renamed(self, func, serialised=True):
        """
        Register a callback for resource rename.  This will be called when any resource is renamed within your agent.

        If `serialised` is not set, the callbacks might arrive in a different order to they were requested.

        The payload passed to your callback is an OrderedDict with the following keys

        ::

            r         : R_ENTITY, R_FEED, etc # the type of resource deleted
            lid       : <name>                # the new local name of the resource
            oldLid    : <name>                # the old local name of the resource
            id        : <GUID>                # the global Id of the resource

        Note:
            Resource types are defined in :doc:`IoticAgent.Core.Const`

        **Example**

        ::

            def renamed_callback(args):
                print(args)
            ...
            client.register_callback_renamed(renamed_callback)

        This would print out something like the following on renaming of an R_ENTITY

        ::

            OrderedDict([(u'lid', u'new_name'),
                         (u'r', 1),
                         (u'oldLid', u'old_name'),
                         (u'id', u'4448993b44738411de5fe2a6cf32d957')])
        """

        self.__client.register_callback_renamed(partial(self.__callback_payload_only, func), serialised=serialised)

    def register_callback_deleted(self, func, serialised=True):
        """
        Register a callback for resource deletion.  This will be called when any resource is deleted within your agent.
        If `serialised` is not set, the callbacks might arrive in a different order to they were requested.

        The payload passed to your callback is an OrderedDict with the following keys

        ::

            r         : R_ENTITY, R_FEED, etc # the type of resource deleted
            lid       : <name>                # the local name of the resource
            id        : <GUID>                # the global Id of the resource

        Note:
            Resource types are defined in :doc:`IoticAgent.Core.Const`

        **Example**

        ::

            def deleted_callback(args):
                print(args)
            ...
            client.register_callback_deleted(deleted_callback)

        This would print out something like the following on deletion of an R_ENTITY

        ::

            OrderedDict([(u'lid', u'old_thing1'),
                         (u'r', 1),
                         (u'id', u'315637813d801ec6f057c67728bf00c2')])
        """
        self.__client.register_callback_deleted(partial(self.__callback_payload_only, func), serialised=serialised)

    def register_callback_reassigned(self, func, serialised=True):
        """
        Register a callback for resource reassignment.  This will be called when any resource is reassigned to or from
        your agent. If `serialised` is not set, the callbacks might arrive in a different order to they were requested.

        The payload passed to your callback is an OrderedDict with the following keys:

        ::

            r         : R_ENTITY, R_FEED, etc # the type of resource reassigned
            lid       : <name>                # the local name of the resource
            epId      : <GUID>                # the global Id of the agent the
                                              # resource has been reassigned *to*
            id        : <GUID>                # the global Id of the resource

        Note:
            Resource types are defined in :doc:`IoticAgent.Core.Const`

        Note:
            You can check whether this is an assign "in" or "out" by comparing the epId with your current agent id,
            using the `IOT.Client.agent_id` property.  If it's the same it's a reassign to you.

        **Example**

        ::

            def reassigned_callback(args):
                print(args)
            ...
            client.register_callback_reassigned(reassigned_callback)

        This would print out something like the following on assignment of an R_ENTITY to:

        ::

            OrderedDict([(u'lid', u'moved_thing'),
                         (u'r', 1),
                         (u'epId', u'5a8d603ee757133d66d99875d0584c72'),
                         (u'id', u'4448993b44738411de5fe2a6cf32d957')])
        """
        self.__client.register_callback_reassigned(partial(self.__callback_payload_only, func), serialised)

    def __callback_subscribed_filter(self, callback, msg):
        payload = msg[M_PAYLOAD]
        if payload[P_RESOURCE] == R_SUB:
            cls = RemoteFeed if payload[P_POINT_TYPE] == R_FEED else RemoteControl
            callback(cls(self, payload[P_ID], payload[P_POINT_ID], payload[P_ENTITY_LID]))

    def register_callback_subscribed(self, callback):
        """
        Register a callback for new subscription. This gets called whenever one of *your* things subscribes to something
        else.

        Note:
            It is not called when whenever something else subscribes to your thing.

        The payload passed to your callback is either a :doc:`IoticAgent.IOT.RemotePoint` RemoteControl or RemoteFeed
        instance.
        """
        return self.__client.register_callback_created(partial(self.__callback_subscribed_filter, callback),
                                                       serialised=False)

    def simulate_feeddata(self, feedid, data, mime=None, time=None):
        """
        Simulate the last feeddata received for given feedid.
        Calls the registered callback for the feed with the last recieved feed data. Allows you to test your code
        without having to wait for the remote thing to share again.

        Args:
            feedid (string): local id of your Feed
            data (optional): The data you want to use to simulate the arrival of remote feed data
            mime (string, optional): The mime type of your data. See also :doc:`IoticAgent.IOT.Point` Feed.share
            time (datetime, optional): UTC timestamp for share. See also: :doc:`IoticAgent.IOT.Point` Feed.share
        """
        self.__client.simulate_feeddata(feedid, data, mime, time)

    #
    # todo: simulate_controlreq -- needs last data and Point instance
    #

    def confirm_tell(self, data, success):
        """
        Confirm that you've done as you were told.  Call this from your control callback to confirm action.
        Used when you are advertising a control and you want to tell the remote requestor that you have
        done what they asked you to.

        **Example**

        This is a minimal example to show the idea.

        Note:
            No Exception handling and ugly use of globals

        ::

            client = None

            def controlreq_cb(args):
                global client   # the client object you connected with

                # perform your action with the data they sent
                success = do_control_action(args['data'])

                if args['confirm']:  # you've been asked to confirm
                    client.confirm_tell(args, success)
                # else, if you do not confirm_tell() this causes a timeout at the requestor's end.

            client = IOT.Client(config='test.ini')
            thing = client.create_thing('test321')
            control = thing.create_control('control', controlreq_cb)

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communication problem between you and the infrastructure

        Args:
            data (dictionary):  The `"args"` dictionary that your callback was called with
            success (boolean):  Whether or not the action you have been asked to do has been sucessful

        More details on the contents of the `data` dictionary for controls see :doc:`IoticAgent.IOT.Thing`
        create_control.
        """
        logger.info("confirm_tell(success=%s) [lid=\"%s\",pid=\"%s\"]", success, data[P_ENTITY_LID], data[P_LID])
        evt = self._request_point_confirm_tell(R_CONTROL, data[P_ENTITY_LID], data[P_LID], success, data['requestId'])
        self._wait_and_except_if_failed(evt)

    def save_config(self):
        """
        Save the config, update the seqnum & default language
        """
        self.__config.set('agent', 'seqnum', self.__client.get_seqnum())
        self.__config.set('agent', 'lang', self.__client.default_lang)
        self.__config.save()

    def _get_parsed_feed_callback(self, callback_parsed, callback):
        Validation.callable_check(callback_parsed)
        return partial(self._parsed_callback_wrapper, callback_parsed, callback, R_FEED)

    def _get_parsed_control_callback(self, callback_parsed, callback):
        Validation.callable_check(callback_parsed)
        return partial(self._parsed_callback_wrapper, callback_parsed, callback, R_CONTROL)

    def _get_point_data_handler_for(self, point):
        """
        Used by point instances and data callbacks
        """
        with self.__point_data_handlers:
            try:
                return self.__point_data_handlers[point]
            except KeyError:
                return self.__point_data_handlers.setdefault(point, PointDataObjectHandler(point, self))

    def _parsed_callback_wrapper(self, callback_parsed, callback_plain, foc, data):
        """
        Used to by register_catchall_*data() and Thing class (follow, create_point) to present point data as an
        object.
        """
        # used by PointDataObjectHandler as reference
        if foc == R_FEED:
            point_ref = data['pid']
        else:  # R_CONTROL
            point_ref = Control(self, data[P_ENTITY_LID], data[P_LID], '0' * 32)

        try:
            data['parsed'] = self._get_point_data_handler_for(point_ref).get_template(data=data[P_DATA])
        except RefreshException:
            # No metadata available, do not produce warning
            if callback_plain:
                callback_plain(data)
        except:
            logger.warning('Failed to parse %s data for %s%s', foc_to_str(foc), point_ref,
                           '' if callback_plain else ', ignoring',
                           exc_info=DEBUG_ENABLED)
            if callback_plain:
                callback_plain(data)
        else:
            callback_parsed(data)

    __exception_mapping = {
        E_FAILED_CODE_ACCESSDENIED: IOTAccessDenied,
        E_FAILED_CODE_INTERNALERROR: IOTInternalError,
        E_FAILED_CODE_MALFORMED: IOTMalformed,
        E_FAILED_CODE_NOTALLOWED: IOTNotAllowed,
        E_FAILED_CODE_UNKNOWN: IOTUnknown
    }

    def _wait_and_except_if_failed(self, event, timeout=None):
        """
        Combines waiting for event and call to `_except_if_failed`. If timeout is not specified the configured
        sync_timeout is used.
        """
        event.wait(timeout or self.__sync_timeout)
        self._except_if_failed(event)

    @classmethod
    def _except_if_failed(cls, event):
        """
        Raises:

            IOTException from the given event if it was not successful. Assumes timeout success flag on event has not
                been set yet.
        """
        if event.success is None:
            raise IOTSyncTimeout('Requested timed out', event)
        if not event.success:
            msg = "Request failed, unknown error"
            if isinstance(event.payload, Mapping):
                if P_MESSAGE in event.payload:
                    msg = event.payload[P_MESSAGE]
                try:
                    exc_class = cls.__exception_mapping[event.payload[P_CODE]]
                except KeyError:
                    pass
                else:
                    raise exc_class(msg, event)

            raise IOTException(msg, event)

    def list(self, all_my_agents=False, limit=500, offset=0):
        """
        List `all` the things created by this client on this or all your agents

        Returns:
            QAPI list function payload

        Raises:
            LinkException: Communications problem between you and the infrastructure

        Args:
            all_my_agents (boolean, optional): If `False` limit search to just this agent, if `True` return list of
                things belonging to all agents you own.
            limit (integer, optional): Return this many Point details
            offset (integer, optional): Return Point details starting at this offset
        """
        logger.info("list(all_my_agents=%s, limit=%s, offset=%s)", all_my_agents, limit, offset)
        if all_my_agents:
            evt = self._request_entity_list_all(limit=limit, offset=offset)
        else:
            evt = self._request_entity_list(limit=limit, offset=offset)

        self._wait_and_except_if_failed(evt)
        return evt.payload['entities']  # pylint:disable=unsubscriptable-object

    def get_thing(self, lid):
        """
        Get the details of a newly created Thing. This only applies to asynchronous creation of Things and the
        new Thing instance can only be retrieved once.

        Returns:
            A :doc:`IoticAgent.IOT.Thing` Thing object, which corresponds to the Thing with the given local id
            (nickname)

        Raises:
            KeyError: The Thing has not been newly created (or has already been retrieved by a previous call)

        Args:
            lid (string): local identifier of your Thing.
        """
        with self.__new_things:
            try:
                return self.__new_things.pop(lid)
            except KeyError as ex:
                raise_from(KeyError('Thing %s not know as new' % lid), ex)

    def create_thing(self, lid):
        """
        Create a new Thing with a local id (lid).

        Returns:
            A :doc:`IoticAgent.IOT.Thing` Thing object if successful or if the Thing already exists

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            lid (string): local identifier of your Thing. The local id is your name or nickname for the
                thing. It's "local" in that it's only available to you on this container, not searchable and not visible
                to others.
        """
        evt = self.create_thing_async(lid)
        self._wait_and_except_if_failed(evt)
        try:
            with self.__new_things:
                return self.__new_things.pop(lid)
        except KeyError as ex:
            raise raise_from(IOTClientError('Thing %s not in cache (post-create)' % lid), ex)

    def create_thing_async(self, lid):
        logger.info("create_thing(lid=\"%s\")", lid)
        return self._request_entity_create(lid)

    def delete_thing(self, lid):
        """Delete a Thing

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        `lid` (string) local identifier of the Thing you want to delete
        """
        logger.info("delete_thing(lid=\"%s\")", lid)
        evt = self.delete_thing_async(lid)
        self._wait_and_except_if_failed(evt)

    def delete_thing_async(self, lid):
        logger.info("delete_thing(lid=\"%s\")", lid)
        return self._request_entity_delete(lid)

    def search(self, text=None, lang=None, location=None, unit=None, limit=50, offset=0, reduced=False, local=None,
               scope=SearchScope.PUBLIC):
        """
        Search the Iotic Space for public Things with metadata matching the search parameters:
        text, lang(uage), location, unit, limit, offset. Note that only things which have at least one point defined can
        be found.

        Returns:
            Dict of results as below (first with reduced=False, second with reduced=True)

        ::

            # reduced=False returns dict similar to below
            {
                "2b2d8b068e404861b19f9e060877e002": {
                    "long": -1.74803,
                    "matches": 3.500,
                    "lat": 52.4539,
                    "label": "Weather Station #2",
                    "owner": "3bbf307b43b1460289fe707619dece3d",
                    "points": {
                        "a300cc90147f4e2990195639de0af201": {
                            "matches": 3.000,
                            "label": "Feed 201",
                            "type": "Feed",
                            "storesRecent": true
                        },
                        "a300cc90147f4e2990195639de0af202": {
                            "matches": 1.500,
                            "label": "Feed 202",
                            "type": "Feed",
                            "storesRecent": false
                        }
                    }
                },
                "76a3b24b02d34f20b675257624b0e001": {
                    "long": 0.716356,
                    "matches": 2.000,
                    "lat": 52.244384,
                    "label": "Weather Station #1",
                    "owner": "3bbf307b43b1460289fe707619dece3d",
                    "points": {
                        "fb1a4a4dbb2642ab9f836892da93f101": {
                            "matches": 1.000,
                            "label": "My weather feed",
                            "type": "Feed",
                            "storesRecent": false
                        },
                        "fb1a4a4dbb2642ab9f836892da93c102": {
                            "matches": 1.000,
                            "label": None,
                            "type": "Control",
                            "storesRecent": false
                        }
                    }
                }
            }

        ::

            # reduced=True returns dict similar to below
            {
                "2b2d8b068e404861b19f9e060877e002": {
                    "a300cc90147f4e2990195639de0af201": "Feed",
                    "a300cc90147f4e2990195639de0af202": "Feed"
                },
                "76a3b24b02d34f20b675257624b0e001": {
                    "fb1a4a4dbb2642ab9f836892da93f101": "Feed",
                    "fb1a4a4dbb2642ab9f836892da93f102": "Control"
                }
            }

        **OR**

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            text (string, optional): The text to search for. Label and description will be searched for both Thing and
                Point and each word will be used as a tag search too. Text search is case-insensitive. Tag search is
                language neutral.
            lang (string, optional): The two-character ISO 639-1 language code to search in, e.g. "en" "fr".
                Language is used to limit search to only labels and descriptions in that language. You will only get
                labels `in that language` back from search and then only if there are any in that language.
            location (dictionary, optional): Latitude, longitude and radius to search within. All values are float,
                Radius is in kilometers (km). E.g. {"lat"=1.2345, "long"=54.321, "radius"=6.789}. If `text` has not been
                specified, radius can at most be 25km.
            unit (string, optional): Valid URL of a unit in an ontology. Or use a constant from the
                :doc:`IoticAgent.Units` class
            limit (integer, optional): Return this many search results
            offset (integer, optional): Return results starting at this offset - good for paging.
            reduced (boolean, optional): If `true`, return the reduced results just containing points and their type.
            local (boolean, optional): **Deprecated**, use `scope` instead. If `true`, perform search at container
                level. Check the local_meta flag to determine whether local metadata functionality is available. (Takes
                precedence over `scope`.)
            scope (optional): Whether to perform PUBLIC, LOCAL (container level) or LOCAL_OWN (container level
                restricted to own things) search. Check the :doc:`IoticAgent.IOT.Client` Client.local_meta) flag to
                determine whether local metadata functionality is available. (Note that PUBLIC and LOCAL_OWN scopes are
                always available.)
        """
        logger.info("search(text=\"%s\", lang=\"%s\", location=\"%s\", unit=\"%s\", limit=%s, offset=%s, reduced=%s)",
                    text, lang, location, unit, limit, offset, reduced)
        evt = self._request_search(text, lang, location, unit, limit, offset,
                                   SearchType.REDUCED if reduced else SearchType.FULL, local, scope)

        self._wait_and_except_if_failed(evt)
        return evt.payload['result']  # pylint: disable=unsubscriptable-object

    def search_reduced(self, text=None, lang=None, location=None, unit=None, limit=100, offset=0, local=None,
                       scope=SearchScope.PUBLIC):
        """
        Shorthand for search() from the :doc:`IoticAgent.IOT.Client` with `reduced=True`
        """
        return self.search(text, lang, location, unit, limit, offset, reduced=True, local=local, scope=scope)

    def search_located(self, text=None, lang=None, location=None, unit=None, limit=100, offset=0, local=None,
                       scope=SearchScope.PUBLIC):
        """
        See :doc:`IoticAgent.IOT.Client` Client.search for general documentation. Provides a thing-only result set
        comprised only of things which have a location set, e.g.:

        ::

            {
                # Keyed by thing id
                '2b2d8b068e404861b19f9e060877e002':
                    # location (g, lat & long), label (l, optional)
                    {'g': (52.4539, -1.74803), 'l': 'Weather Station #2'},
                '76a3b24b02d34f20b675257624b0e001':
                    {'g': (52.244384, 0.716356), 'l': None},
                '76a3b24b02d34f20b675257624b0e004':
                    {'g': (52.245384, 0.717356), 'l': 'Gasometer'},
                '76a3b24b02d34f20b675257624b0e005':
                    {'g': (52.245384, 0.717356), 'l': 'Zepellin'}
            }


        """
        logger.info("search_located(text=\"%s\", lang=\"%s\", location=\"%s\", unit=\"%s\", limit=%s, offset=%s)",
                    text, lang, location, unit, limit, offset)
        evt = self._request_search(text, lang, location, unit, limit, offset, SearchType.LOCATED, local, scope)

        self._wait_and_except_if_failed(evt)
        return evt.payload['result']  # pylint: disable=unsubscriptable-object

    # used by describe()
    __guid_resources = (Thing, Point, RemoteFeed, RemoteControl)

    def describe(self, guid_or_resource, lang=None, local=None, scope=DescribeScope.AUTO):
        """
        Describe returns the public (or local) description of a Thing or Point

        Returns:
            The description dict (see below for Thing example) if available, otherwise `None`

        ::

            {
                "type": "Entity",
                "meta": {
                    "long": 0.716356,
                    "lat": 52.244384,
                    "label": "Weather Station #1",
                    "parent": "3bbf307b43b1460289fe707619dece3d",
                    "points": [
                        {
                            "type": "Control",
                            "label": "Control 101",
                            "guid": "fb1a4a4dbb2642ab9f836892da93c101",
                            "storesRecent": false
                        },
                        {
                            "type": "Feed",
                            "label": "My weather feed",
                            "guid": "fb1a4a4dbb2642ab9f836892da93f101",
                            "storesRecent": true
                        }
                    ],
                    "comment": "A lovely weather station...",
                    "tags": [
                        "blue",
                        "garden"
                    ]
                }
            }

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure

        Args:
            guid_or_resource (string or object): If a `string`, it should contain the globally unique id
                of the resource you want to describe in 8-4-4-4-12 (or undashed) format. If an `object`, it should be an
                instance of Thing, Point, RemoteFeed or RemoteControl.  The system will return you the description of
                that object.
            lang (string, optional): The two-character ISO 639-1 language code for which labels and comments will be
                returned. This does not affect Values (i.e. when describing a Point, apart from value comments) and tags
                as these are language neutral).
            local (boolean, optional): **Deprecated**, use `scope` instead. If `true`, lookup metadata at container
                level. Check the local_meta flag to determine whether local metadata functionality is available. (Takes
                precedence over `scope`.)
            scope (optional): Whether to perform PUBLIC, LOCAL (container level) or LOCAL_OWN (container level
                restricted to own things) metadata lookup. Check the :doc:`IoticAgent.IOT.Client` Client.local_meta flag
                to determine whether local metadata functionality is available. (Note that AUTO, PUBLIC and LOCAL_OWN
                scopes are always available.). AUTO mode first attempts to look up private metadata, then public.
        """
        if isinstance(guid_or_resource, self.__guid_resources):
            guid = guid_or_resource.guid
        elif isinstance(guid_or_resource, string_types):
            guid = uuid_to_hex(guid_or_resource)
        else:
            raise ValueError("describe requires guid string or Thing, Point, RemoteFeed or RemoteControl instance")
        logger.info('describe() [guid="%s"]', guid)

        evt = self._request_describe(guid, lang, local, scope)

        self._wait_and_except_if_failed(evt)
        return evt.payload['result']  # pylint: disable=unsubscriptable-object

    def __cb_created(self, msg, duplicated=False):
        # Only consider solicitied creation events since there is no cache. This also applies to things reassigned to
        # this agent.
        payload = msg[M_PAYLOAD]

        if msg[M_CLIENTREF] is not None:
            if payload[P_RESOURCE] == R_ENTITY:
                lid = payload[P_LID]
                if payload[P_EPID] != self.__client.epId:
                    logger.warning('Created thing %s assigned to different agent: %s', lid, payload[P_EPID])
                thing = Thing(self, lid, payload[P_ID], payload[P_EPID])

                with self.__new_things:
                    self.__new_things[lid] = thing
                # second (permanent) reference kept so can forward to thing for e.g. point creation callbacks
                with self.__private_things:
                    self.__private_things[lid] = thing
                logger.debug('Added %sthing: %s (%s)', 'existing ' if duplicated else '', lid, payload[P_ID])

            elif payload[P_RESOURCE] in _POINT_TYPES or payload[P_RESOURCE] == R_SUB:
                with self.__private_things:
                    thing = self.__private_things.get(payload[P_ENTITY_LID], None)
                if thing:
                    thing._cb_created(payload, duplicated=duplicated)
                else:
                    logger.warning('Thing %s unknown internally, ignoring creation of point/sub', payload[P_ENTITY_LID])

            else:
                logger.error('Resource creation of type %d unhandled', payload[P_RESOURCE])

        else:
            logger.debug('Ignoring unsolicited creation request of type %d', payload[P_RESOURCE])

    def __cb_duplicated(self, msg):
        self.__cb_created(msg, duplicated=True)

    def __cb_reassigned(self, msg):
        payload = msg[M_PAYLOAD]

        if payload[P_RESOURCE] == R_ENTITY:
            with self.__private_things:
                thing = self.__private_things.get(payload[P_LID], None)
            if thing:
                thing._cb_reassigned(payload)
            else:
                logger.warning('Thing %s unknown internally, ignoring reassignment', payload[P_LID])
        else:
            logger.error('Resource reassignment of type %d unhandled', payload[P_RESOURCE])

    def __cb_deleted(self, msg):
        # only consider solicitied deletion events
        if msg[M_CLIENTREF] is not None:
            payload = msg[M_PAYLOAD]

            if payload[P_RESOURCE] == R_ENTITY:
                try:
                    with self.__private_things:
                        self.__private_things.pop(payload[P_LID])
                except KeyError:
                    logger.warning('Deleted thing %s unknown internally', payload[P_LID])
                else:
                    logger.debug('Deleted thing: %s', payload[P_LID])

            # currently no functionality benefits from these
            elif payload[P_RESOURCE] in (R_FEED, R_CONTROL, R_SUB):
                pass

            else:
                logger.error('Resource deletetion of type %d unhandled', payload[P_RESOURCE])

        else:
            logger.debug('Ignoring unsolicited deletion request of type %d', msg[M_PAYLOAD][P_RESOURCE])

    def __cb_recent_data(self, data):
        with self.__recent_data_callbacks:
            try:
                # determine specific callback
                callback = self.__recent_data_callbacks[data[M_CLIENTREF]]
            except KeyError:
                logger.debug('No callback for recent data request with id %s', data[M_CLIENTREF])
            else:
                try:
                    callback(data)
                except:
                    logger.warning('Recent data callback failed for point %s', data[P_POINT_ID], exc_info=DEBUG_ENABLED)

    # Registrer specific callback function (for a recent data callback) which will be removed on request completion. The
    # request is NOT checked first.
    def _add_recent_cb_for(self, req, func):
        with self.__recent_data_callbacks:
            self.__recent_data_callbacks[req.id_] = partial(self.__recent_cb_per_sample, func)
        req._run_on_completion(self.__remove_recent_cb_for)

    # multi-sample to per-sample callback wrapper
    @staticmethod
    def __recent_cb_per_sample(func, data):
        samples = data['samples']
        for sample in samples:
            func(sample)

    # used by _add_recent_cb_for only
    def __remove_recent_cb_for(self, req):
        with self.__recent_data_callbacks:
            try:
                self.__recent_data_callbacks.pop(req.id_, None)
            except KeyError:
                logger.warning('recent cb does not exist for request %s', req.id_)

    # Wrap Core.Client functions so IOT contains everything.
    # These are protected functions used by Client, Thing, Point etc.
    def _request_point_list(self, foc, lid, limit, offset):
        return self.__client.request_point_list(foc, lid, limit, offset)

    def _request_point_list_detailed(self, foc, lid, pid):
        return self.__client.request_point_list_detailed(foc, lid, pid)

    def _request_point_recent_info(self, foc, lid, pid):
        return self.__client.request_point_recent_info(foc, lid, pid)

    def _request_point_recent_config(self, foc, lid, pid, max_samples=0):
        return self.__client.request_point_recent_config(foc, lid, pid, max_samples)

    def _request_entity_list(self, limit=0, offset=500):
        return self.__client.request_entity_list(limit=limit, offset=offset)

    def _request_entity_list_all(self, limit=0, offset=500):
        return self.__client.request_entity_list_all(limit=limit, offset=offset)

    def _request_entity_create(self, lid):
        return self.__client.request_entity_create(lid)

    def _request_entity_rename(self, lid, new_lid):
        return self.__client.request_entity_rename(lid, new_lid)

    def _request_entity_delete(self, lid):
        return self.__client.request_entity_delete(lid)

    def _request_entity_reassign(self, lid, new_epid):
        return self.__client.request_entity_reassign(lid, new_epid)

    def _request_entity_meta_setpublic(self, lid, public):
        return self.__client.request_entity_meta_setpublic(lid, public)

    def _request_entity_tag_update(self, lid, tags, delete=False):
        return self.__client.request_entity_tag_update(lid, tags, delete)

    def _request_entity_tag_list(self, lid, limit, offset):
        return self.__client.request_entity_tag_list(lid, limit, offset)

    def _request_entity_meta_get(self, lid, fmt):
        return self.__client.request_entity_meta_get(lid, fmt)

    def _request_entity_meta_set(self, lid, rdf, fmt):
        return self.__client.request_entity_meta_set(lid, rdf, fmt)

    def _request_point_create(self, foc, lid, pid, control_cb=None, save_recent=0):
        return self.__client.request_point_create(foc, lid, pid, control_cb, save_recent)

    def _request_point_rename(self, foc, lid, pid, newpid):
        return self.__client.request_point_rename(foc, lid, pid, newpid)

    def _request_point_delete(self, foc, lid, pid):
        return self.__client.request_point_delete(foc, lid, pid)

    def _request_point_share(self, lid, pid, data, mime, time):
        return self.__client.request_point_share(lid, pid, data, mime, time)

    def _request_point_confirm_tell(self, foc, lid, pid, success, requestId):
        return self.__client.request_point_confirm_tell(foc, lid, pid, success, requestId)

    def _request_point_meta_get(self, foc, lid, pid, fmt):
        return self.__client.request_point_meta_get(foc, lid, pid, fmt)

    def _request_point_meta_set(self, foc, lid, pid, rdf, fmt):
        return self.__client.request_point_meta_set(foc, lid, pid, rdf, fmt)

    def _request_point_tag_update(self, foc, lid, pid, tags, delete=False):
        return self.__client.request_point_tag_update(foc, lid, pid, tags, delete)

    def _request_point_tag_list(self, foc, lid, pid, limit, offset):
        return self.__client.request_point_tag_list(foc, lid, pid, limit, offset)

    def _request_point_value_create(self, lid, pid, foc, label, vtype, lang, comment, unit):
        return self.__client.request_point_value_create(lid, pid, foc, label, vtype, lang, comment, unit)

    def _request_point_value_delete(self, lid, pid, foc, label=None):
        return self.__client.request_point_value_delete(lid, pid, foc, label=label)

    def _request_point_value_list(self, lid, pid, foc, limit, offset):
        return self.__client.request_point_value_list(lid, pid, foc, limit, offset)

    def _request_sub_create_local(self, slid, foc, lid, pid, callback):
        return self.__client.request_sub_create_local(slid, foc, lid, pid, callback)

    def _request_sub_create(self, lid, foc, gpid, callback):
        return self.__client.request_sub_create(lid, foc, gpid, callback)

    def _request_sub_ask(self, subid, data, mime):
        return self.__client.request_sub_ask(subid, data, mime)

    def _request_sub_tell(self, subid, data, timeout, mime):
        return self.__client.request_sub_tell(subid, data, timeout, mime)

    def _request_sub_delete(self, subid):
        return self.__client.request_sub_delete(subid)

    def _request_sub_list(self, lid, limit, offset):
        return self.__client.request_sub_list(lid, limit, offset)

    def _request_sub_recent(self, sub_id, count=None):
        return self.__client.request_sub_recent(sub_id, count)

    def _request_search(self, text, lang, location, unit, limit, offset, type_='full', local=None,
                        scope=SearchScope.PUBLIC):
        return self.__client.request_search(text, lang, location, unit, limit, offset, type_, local, scope)

    def _request_describe(self, guid, lang, local=None, scope=DescribeScope.AUTO):
        return self.__client.request_describe(guid, lang, local, scope)
