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

import warnings
import logging
logger = logging.getLogger(__name__)
DEBUG_ENABLED = (logger.getEffectiveLevel() == logging.DEBUG)

from IoticAgent.Core import Client as Core_Client, ThreadSafeDict, __version__ as Core_Version
from IoticAgent.Core.compat import Mapping, raise_from, string_types
from IoticAgent.Core.Const import (E_FAILED_CODE_NOTALLOWED, E_FAILED_CODE_UNKNOWN, E_FAILED_CODE_MALFORMED,
                                   E_FAILED_CODE_INTERNALERROR, E_FAILED_CODE_ACCESSDENIED, M_CLIENTREF, M_PAYLOAD,
                                   R_ENTITY, R_FEED, R_CONTROL, R_SUB, P_CODE, P_ID, P_LID, P_ENTITY_LID, P_EPID,
                                   P_RESOURCE, P_MESSAGE, P_DATA, P_MIME)

from .Thing import Thing
from .Config import Config
from .DB import DB
from .utils import uuid_to_hex, version_string_to_tuple
from .Exceptions import IOTException, IOTUnknown, IOTMalformed, IOTInternalError, IOTAccessDenied, IOTClientError
from .Point import Point, _POINT_TYPES
from .RemoteFeed import RemoteFeed
from .RemoteControl import RemoteControl


class Client(object):  # pylint: disable=too-many-public-methods

    # Core version targeted by IOT client
    __core_version = '0.2.0'

    def __init__(self, config=None, db=None):
        """
        Creates an IOT.Client instance which provides access to Iotic Space

        `config` (optional): The name of the config file containing the connection parameters.
        Defaults to the name of the script +".ini", e.g. `config="my_script.ini"`. Alternatively
        an existing [Config](Config.m.html#IoticAgent.IOT.Config.Config) object can be specified.

        `db` (optional): The name of the database file to be used for storing key-value pairs by the agent.
        Defaults to the name of the script +".db", e.g. `db="my_script.db"`
        """
        self.__core_version_check()
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
        #
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
                                        seqnum=self.__config.get('agent', 'seqnum'),
                                        sslca=self.__config.get('agent', 'sslca'),
                                        network_retry_timeout=self.__config.get('core', 'network_retry_timeout'),
                                        auto_encode_decode=self.__config.get('core', 'auto_encode_decode'))
        except ValueError as ex:
            raise_from(ValueError('Configuration error'), ex)

        #
        # Callbacks for updating own resource cache (used internally only)
        self.__client.register_callback_created(self.__cb_created)
        self.__client.register_callback_duplicate(self.__cb_duplicated)
        self.__client.register_callback_reassigned(self.__cb_reassigned)
        self.__client.register_callback_deleted(self.__cb_deleted)
        #
        # Setup catchall for unsolicited feeddata and controlreq and write data to the key/value DB
        self.__db = None
        if self.__config.get('iot', 'db_last_value').lower() not in ('0', 'False'):
            self.__db = DB(fn=db)
            self.__client.register_callback_feeddata(self.__cb_catchall_feeddata)
            self.__client.register_callback_controlreq(self.__cb_catchall_controlreq)
        #
        # Keeps track of newly created things (the requests for which originated from this agent)
        self.__new_things = ThreadSafeDict()
        # Allows client to forward e.g. Point creation callbacks to the relevant Thing instance. This contains the most
        # recent instance of any single Thing (since creation requests can be performed more than once).
        self.__private_things = ThreadSafeDict()

    @property
    def agent_id(self):
        """Agent id (aka epId) in use for this client instance"""
        return self.__client.epId

    @property
    def default_lang(self):
        """Language in use when not explicitly specified (in meta related requests). Will be set to container default
        if was not set in configuration. Before client has started this might be None."""
        return self.__client.default_lang

    def start(self):
        """Open a connection to Iotic Space.  `start()` is called by `__enter__` which allows the python
        `with` syntax to be used.

        `Example 0` - Calling start() implicitly using with.  minimal example with no exception handling

            #!python
            with IOT.Client(config="my_script.ini") as client:
                client.create_thing("my_thing")

        `Example 1` - Calling start() implicitly using with.  This handles the finally for you. `Recommended`

            #!python
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

        `Example 2` - Calling start() explicitly (no with)  Be careful, you have to put a finally in your try blocks
        otherwise your client might remain connected.

            #!python
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

        Returns This Client instance

        Raises Exception
        """
        if not self.__client.is_alive():
            self.__client.start()
        return self

    def __enter__(self):
        return self.start()

    def stop(self):
        """Close the connection to Iotic Space.  `stop()` is called by `__exit()__` allowing the python `with`
        syntax to be used.  See [start()](./Client.m.html#IoticAgent.IOT.Client.Client.start)
        """
        if self.__client.is_alive():
            self.__client.stop()

    def close(self):
        """`DEPRECATED`. Please note IOT.Client now requires a .start call.  close becomes stop.
        """
        warnings.warn('close() has been deprecated, use stop() instead', DeprecationWarning)
        self.stop()

    def __exit__(self, exc_type, exc_value, traceback):
        return self.stop()

    def __del__(self):
        try:
            self.stop()
        # Don't want on ignored exceptions
        except:
            pass

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
            logger.warning('Core client minor version difference: %s (%s known)', Core_Version, cls.__core_version)
        elif core[2] > expected[2]:
            logger.info('Core client patch level change: %s (%s known)', Core_Version, cls.__core_version)
        else:
            logger.debug('Core version: %s', Core_Version)

    def _notify_thing_lid_change(self, from_lid, to_lid):
        """Used by Thing instances to indicate that a rename operation has happened"""
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
        Returns client's alive state
        """
        return self.__client.is_alive()

    def register_catchall_feeddata(self, callback):
        """
        Registers a callback that is called for all feeddata your Thing receives

        `Example`

            #!python
            def feeddata_callback(data):
                print(data)
            ...
            client.register_catchall_feeddata(feeddata_callback)

       `callback` (required) the function name that you want to be called on receipt of new feed data

        More details on the contents of the `data` dictionary for feeds see:
        [follow()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.follow)
        """
        return self.__client.register_callback_feeddata(callback)

    def register_catchall_controlreq(self, callback):
        """
        Registers a callback that is called for all control requests received by your Thing

        `Example`

            #!python
            def controlreq_callback(data):
                print(data)
            ...
            client.register_catchall_controlreq(controlreq_callback)

        `callback` (required) the function name that you want to be called on receipt of a new control request

        More details on the contents of the `data` dictionary for controls see:
        [create_control()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.create_control)
        """
        return self.__client.register_callback_controlreq(callback)

    def register_callback_subscription(self, callback):
        """
        Register a callback for subscription count change notification
        """
        return self.__client.register_callback_subscription(callback)

    def simulate_feeddata(self, feedid, data=None, mime=None):
        """Simulate the last feeddata received for given feedid
        Calls the registered callback for the feed with the last recieved feed data. Allows you to test your code
        without having to wait for the remote thing to share again.

        Raises KeyError - if there is no data with which to simulate.  I.e. you haven't received any and haven't
        used the data= and mime= parameters

        Raises RuntimeError - if the key-value store "database" is disabled

        `feedid` (required) (string) local id of your Feed

        `data` (optional) (as applicable) The data you want to use to simulate the arrival of remote feed data

        `mime` (optional) (string) The mime type of your data.  See:
        [share()](./Point.m.html#IoticAgent.IOT.Point.Point.share)
        """
        if data is None:
            if self.__db is None:
                raise RuntimeError("simulate_feeddata disabled with [iot] db_last_value = 0")
            # can raise KeyError if not available
            data, mime = self.__db.kv_get(feedid)
        self.__client.simulate_feeddata(feedid, data, mime)

    #
    # todo: simulate_controlreq -- needs last data and Point instance
    #

    def get_last_feeddata(self, feedid):
        """Get the value of the last feed data from a remote thing, if any has been received

        Returns last data for feedid and mime (as tuple), or tuple of (None, None) if not found

        Raises KeyError - if there is no data to get.  Probably because you haven't received any and haven't
        called [simulate_feeddata()](./Client.m.html#IoticAgent.IOT.Client.Client.simulate_feeddata)
         with the data= and mime= parameters set

        Raises RuntimeError - if the key-value store "database" is disabled

        `feedid` (required) (string) local id of your Feed
        """
        if self.__db is None:
            raise RuntimeError("get_last_feeddata disabled with [iot] db_last_value = 0")
        try:
            return self.__db.kv_get(feedid)  # data, mime
        except KeyError:
            return None, None

    def confirm_tell(self, data, success):
        """Confirm that you've done as you were told.  Call this from your control callback to confirm action.
        Used when you are advertising a control and you want to tell the remote requestor that you have
        done what they asked you to.

        `Example:` this is a minimal example to show the idea.  Note - no Exception handling and ugly use of globals

            #!python
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

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `data` (mandatory) (dictionary)  The `"args"` dictionary that your callback was called with

        `success` (mandatory) (boolean)  Whether or not the action you have been asked to do has been
        sucessful.

        More details on the contents of the `data` dictionary for controls see:
        [create_control()](./Thing.m.html#IoticAgent.IOT.Thing.Thing.create_control)
        """
        logger.info("confirm_tell(success=%s) [lid=\"%s\",pid=\"%s\"]", success, data[P_ENTITY_LID], data[P_LID])
        evt = self._request_point_confirm_tell(R_CONTROL, data[P_ENTITY_LID], data[P_LID], success, data['requestId'])
        evt.wait()
        self._except_if_failed(evt)

    def save_config(self):
        """Save the config, update the seqnum & default language
        """
        self.__config.set('agent', 'seqnum', self.__client.get_seqnum())
        self.__config.set('agent', 'lang', self.__client.default_lang)
        self.__config.save()

    @staticmethod
    def _except_if_failed(event):
        """Raises an IOTException from the given event if it was not successful"""
        if not event.success:
            msg = "Request failed, unknown error"
            if isinstance(event.payload, Mapping):
                if P_MESSAGE in event.payload:
                    msg = event.payload[P_MESSAGE]
                if P_CODE in event.payload:
                    code = event.payload[P_CODE]
                    if code == E_FAILED_CODE_ACCESSDENIED:
                        raise IOTAccessDenied(msg)
                    if code == E_FAILED_CODE_INTERNALERROR:
                        raise IOTInternalError(msg)
                    if code in (E_FAILED_CODE_MALFORMED, E_FAILED_CODE_NOTALLOWED):
                        raise IOTMalformed(msg)
                    if code == E_FAILED_CODE_UNKNOWN:
                        raise IOTUnknown(msg)
            raise IOTException(msg)

    def list(self, all_my_agents=False, limit=500, offset=0):
        """List `all` the things created by this client on this or all your agents

        Returns QAPI list function payload

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `all_my_agents` (optional) (boolean) Default False.  If `False` limit search to just this agent,
        if `True` return list of things belonging to all agents you own.

        `limit` (optional) (integer) Default 500.  Return this many Point details

        `offset` (optional) (integer) Default 0.  Return Point details starting at this offset
        """
        logger.info("list(all_my_agents=%s, limit=%s, offset=%s)", all_my_agents, limit, offset)
        if all_my_agents:
            evt = self._request_entity_list_all(limit=limit, offset=offset)
        else:
            evt = self._request_entity_list(limit=limit, offset=offset)

        evt.wait()
        self._except_if_failed(evt)
        return evt.payload

    def get_thing(self, lid):
        """Get the details of a newly created Thing. This only applies to asynchronous creation of Things and the
        new Thing instance can only be retrieved once.

        Returns a [Thing](Thing.m.html#IoticAgent.IOT.Thing.Thing) object,
        which corresponds to the Thing with the given local id (nickname)

        Raises `KeyError` if the Thing has not been newly created (or has already been retrieved by a previous call)

        `lid` (required) (string) local identifier of your Thing.
        """
        with self.__new_things:
            try:
                return self.__new_things.pop(lid)
            except KeyError as ex:
                raise_from(KeyError('Thing %s not know as new' % lid), ex)

    def create_thing(self, lid):
        """Create a new Thing with a local id (lid).

        Returns a [Thing](Thing.m.html#IoticAgent.IOT.Thing.Thing)  object if successful
        or if the Thing already exists

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `lid` (required) (string) local identifier of your Thing.  The local id is your name or nickname for the thing.
        It's "local" in that it's only available to you on this container.  It's not searchable, and never shown to others
        """
        logger.info("create_thing(lid=\"%s\")", lid)
        evt = self._request_entity_create(lid)
        evt.wait()
        self._except_if_failed(evt)
        try:
            with self.__new_things:
                return self.__new_things.pop(lid)
        except KeyError as ex:
            raise raise_from(IOTClientError('Thing %s not in cache (post-create)' % lid), ex)

    def create_thing_async(self, lid):
        logger.info("create_thing_async(lid=\"%s\")", lid)
        return self._request_entity_create(lid)

    def delete_thing(self, lid):
        """Delete a Thing

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `lid` (required) (string) local identifier of the Thing you want to delete
        """
        logger.info("delete_thing(lid=\"%s\")", lid)
        evt = self._request_entity_delete(lid)
        evt.wait()
        self._except_if_failed(evt)

    def delete_thing_async(self, lid):
        logger.info("delete_thing_async(lid=\"%s\")", lid)
        return self._request_entity_delete(lid)

    def search(self, text=None, lang=None, location=None, unit=None, limit=100, offset=0, reduced=False):
        """Search the Iotic Space for public Things
        with metadata matching the search parameters:
        text, (lang, location, unit, limit, offset)=optional

        Returns dict of results as below (first with reduced=False, second with reduced=True)- OR -

            #!python
            # reduced=False returns dict similar to below
            {
                "2b2d8b068e404861b19f9e060877e002": {
                    "long": "-1.74803",
                    "matches": 3.500,
                    "lat": "52.4539",
                    "label": "Weather Station #2",
                    "tags": {
                    },
                    "points": {
                        "a300cc90147f4e2990195639de0af201": {
                            "matches": 3.000,
                            "label": "Feed 201",
                            "tags": {
                            },
                            "type": "Feed"
                        },
                        "a300cc90147f4e2990195639de0af202": {
                            "matches": 1.500,
                            "label": "Feed 202",
                            "tags": {
                            },
                            "type": "Feed"
                        }
                    }
                },
                "76a3b24b02d34f20b675257624b0e001": {
                    "long": "0.716356",
                    "matches": 2.000,
                    "lat": "52.244384",
                    "label": "Weather Station #1",
                    "tags": {
                    },
                    "points": {
                        "fb1a4a4dbb2642ab9f836892da93f101": {
                            "matches": 1.000,
                            "label": "My weather feed",
                            "tags": {
                            },
                            "type": "Feed"
                        },
                        "fb1a4a4dbb2642ab9f836892da93c101": {
                            "matches": 1.000,
                            "label": null,
                            "tags": {
                            },
                            "type": "Control"
                        }
                    }
                }
            }

            # reduced=True returns dict similar to below
            {
                "fb1a4a4dbb2642ab9f836892da93f101": "Feed",
                "fb1a4a4dbb2642ab9f836892da93c101": "Control"
            }

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `text` (required) (string) The text to search for.  Label and description will be searched
        for both Thing and Point and each word will be used as a tag search too

        `lang` (optional) (string) Default None. The two-character ISO 639-1 language code to search in, e.g. "en" "fr"
        Language is used to limit search to only labels and descriptions in that language. You will only get labels `in
        that language` back from search and then only if there are any in that language

        `location` (optional) (dictionary) Default None.  Latitude, longitude and radius to search within.
        All values are float, Radius is in kilometers (km).  E.g.  `{"lat"=1.2345, "lon"=54.321, "radius"=6.789}`

        `unit` (optional) (string) Default None.  Valid URL of a unit in an ontology.  Or use a constant from the
        [units](../Units.m.html#IoticAgent.Units) class - such as [METRE](../Units.m.html#IoticAgent.Units.METRE)

        `limit` (optional) (integer) Default 500.  Return this many search results

        `offset` (optional) (integer) Default 0.  Return results starting at this offset - good for paging.

        `reduced` (optional) (boolean) Default False.  If `true`, Return the reduced results just containing points and their type
        """
        logger.info("search(text=\"%s\", lang=\"%s\", location=\"%s\", unit=\"%s\", limit=%s, offset=%s, reduced=%s)",
                    text, lang, location, unit, limit, offset, reduced)
        evt = self._request_search(text, lang, location, unit, limit, offset, reduced)
        evt.wait()

        self._except_if_failed(evt)
        return evt.payload

    def search_reduced(self, text=None, lang=None, location=None, unit=None, limit=100, offset=0):
        return self.search(text, lang, location, unit, limit, offset, reduced=True)

    # used by describe()
    __guid_resources = (Thing, Point, RemoteFeed, RemoteControl)

    def describe(self, guid_or_thing):
        """Describe returns the public description of a Thing

        Returns the description dict (see below) if Thing or Point is public, otherwise `None`

            #!python
            {
                "result": {
                    "type": "Entity",
                    "meta": {
                            "long": 0.716356,
                            "lat": 52.244384,
                            "labels": [
                                {
                                    "label": "Weather Station #1",
                                    "lang": "en"
                                },
                                {
                                    "label": "Station du temps#1",
                                    "lang": "fr"
                                }
                            ],
                            "points": [
                                {
                                    "type": "Control",
                                    "labels": [
                                        {
                                            "label": "Control 101",
                                            "lang": "en"
                                        }
                                    ],
                                    "guid": "fb1a4a4dbb2642ab9f836892da93c101"
                                },
                                {
                                    "type": "Feed",
                                    "labels": [
                                        {
                                            "label": "My weather feed",
                                            "lang": "en"
                                        },
                                        {
                                            "label": "Mon temps feed",
                                            "lang": "fr"
                                        }
                                    ],
                                    "guid": "fb1a4a4dbb2642ab9f836892da93f101"
                                }
                            ],
                            "comments": [
                                {
                                    "comment": "A lovely weather station...",
                                    "lang": "en"
                                },
                                {
                                    "comment": "La plus belle station meteo...",
                                    "lang": "fr"
                                }
                            ],
                            "tags": {
                                "en": [
                                    "blue",
                                    "garden"
                                ],
                                "fr": [
                                    "ouest"
                                ]
                            }
                        }
                    }
                }
            }

        Raises [IOTException](./Exceptions.m.html#IoticAgent.IOT.Exceptions.IOTException)
        containing the error if the infrastructure detects a problem

        Raises [LinkException](../Core/AmqpLink.m.html#IoticAgent.Core.AmqpLink.LinkException)
        if there is a communications problem between you and the infrastructure

        `guid_or_thing` (mandatory) (string or object).
        If a `string`, it should contain the globally unique id of the resource you want to describe in 8-4-4-4-12
        format.
        If an `object`, it should be an instance of Thing, Point, RemoteFeed or RemoteControl.  The system will return
        you the description of that object.
        """
        if isinstance(guid_or_thing, self.__guid_resources):
            guid = guid_or_thing.guid
        elif isinstance(guid_or_thing, string_types):
            guid = uuid_to_hex(guid_or_thing)
        else:
            raise ValueError("describe requires guid string or Thing, Point, RemoteFeed or RemoteControl instance")
        logger.info('describe() [guid="%s"]', guid)

        evt = self._request_describe(guid)
        evt.wait()

        self._except_if_failed(evt)
        return evt.payload

    def __cb_created(self, msg, duplicated=False):
        # Only consider solicitied creation events since there is no cache. This also applies to things reassigned to
        # this agent.
        if msg[M_CLIENTREF] is not None:
            payload = msg[M_PAYLOAD]

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

    def __cb_catchall_feeddata(self, data):
        try:
            # todo - confusing to store feed & control data in same dictionary?
            self.__db.kv_set(data['pid'], (data[P_DATA], data[P_MIME]))
        except (IOError, OSError):
            logger.warning('Failed to write feed data for %s to db', data['pid'], exc_info=DEBUG_ENABLED)

    def __cb_catchall_controlreq(self, data):
        try:
            # todo - confusing to store feed & control data in same dictionary?
            # (although shouldn't clash since here includes spae and pid (above for feeds) should not
            self.__db.kv_set('%s %s' % (data[P_ENTITY_LID], data[P_LID]), (data[P_DATA], data[P_MIME]))
        except (IOError, OSError):
            logger.warning('Failed to write control request data for lid=%s pid=%s to db', data[P_ENTITY_LID],
                           data[P_LID], exc_info=DEBUG_ENABLED)

    # Wrap Core.Client functions so IOT contains everything.
    # These are protected functions used by Client, Thing, Point etc.
    def _request_point_list(self, foc, lid, limit, offset):
        return self.__client.request_point_list(foc, lid, limit, offset)

    def _request_point_list_detailed(self, foc, lid, pid):
        return self.__client.request_point_list_detailed(foc, lid, pid)

    def _request_entity_list(self, limit=0, offset=500):
        return self.__client.request_entity_list_all(limit=limit, offset=offset)

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

    def _request_entity_tag_create(self, lid, tags, lang, delete=False):
        return self.__client.request_entity_tag_create(lid, tags, lang, delete)

    def _request_entity_tag_delete(self, lid, tags, lang):
        return self._request_entity_tag_create(lid, tags, lang, delete=True)

    def _request_entity_tag_list(self, lid, limit, offset):
        return self.__client.request_entity_tag_list(lid, limit, offset)

    def _request_entity_meta_get(self, lid, fmt):
        return self.__client.request_entity_meta_get(lid, fmt)

    def _request_entity_meta_set(self, lid, rdf, fmt):
        return self.__client.request_entity_meta_set(lid, rdf, fmt)

    def _request_point_create(self, foc, lid, pid, control_cb=None):
        return self.__client.request_point_create(foc, lid, pid, control_cb)

    def _request_point_rename(self, foc, lid, pid, newpid):
        return self.__client.request_point_rename(foc, lid, pid, newpid)

    def _request_point_delete(self, foc, lid, pid):
        return self.__client.request_point_delete(foc, lid, pid)

    def _request_point_share(self, lid, pid, data, mime):
        return self.__client.request_point_share(lid, pid, data, mime)

    def _request_point_confirm_tell(self, foc, lid, pid, success, requestId):
        return self.__client.request_point_confirm_tell(foc, lid, pid, success, requestId)

    def _request_point_meta_get(self, foc, lid, pid, fmt):
        return self.__client.request_point_meta_get(foc, lid, pid, fmt)

    def _request_point_meta_set(self, foc, lid, pid, rdf, fmt):
        return self.__client.request_point_meta_set(foc, lid, pid, rdf, fmt)

    def _request_point_tag_create(self, foc, lid, pid, tags, lang, delete=False):
        return self.__client.request_point_tag_create(foc, lid, pid, tags, lang, delete)

    def _request_point_tag_delete(self, foc, lid, pid, tags, lang):
        return self._request_point_tag_create(foc, lid, pid, tags, lang, delete=True)

    def _request_point_tag_list(self, foc, lid, pid, limit, offset):
        return self.__client.request_point_tag_list(foc, lid, pid, limit, offset)

    def _request_point_value_create(self, lid, pid, foc, label, vtype, lang, comment, unit):
        return self.__client.request_point_value_create(lid, pid, foc, label, vtype, lang, comment, unit)

    def _request_point_value_delete(self, lid, pid, foc, label, lang):
        return self.__client.request_point_value_delete(lid, pid, foc, label, lang)

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

    def _request_search(self, text, lang, location, unit, limit, offset, reduced):
        return self.__client.request_search(text, lang, location, unit, limit, offset, reduced)

    def _request_describe(self, guid):
        return self.__client.request_describe(guid)
