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
"""Wrapper object for the Client Configuration file
"""

from __future__ import unicode_literals

from sys import argv
from io import StringIO
import os.path
import logging
logger = logging.getLogger(__name__)

from IoticAgent.Core.compat import PY3

if PY3:
    from configparser import ConfigParser  # pylint: disable=import-error,wrong-import-order
else:
    from ConfigParser import ConfigParser  # pylint: disable=import-error,wrong-import-order


class Config(object):

    def __init__(self, fn=None, string=None):
        """Config helper reads/writes .ini files.
        If a setting is not specified in the .ini file the default from `self.__defaults` will be used. Alternatively
        a textual configuration can be specified using the `string` argument. `fn` takes precedence over `string`.

        `[agent] =` This section is used for AMQP Login details.

            #!python
            host =   # ip:port of the AMQP broker
            vhost =  # virtualhost name
            prefix = # username (agent id) prefix for login
            sslca =  # SSL CA file for non-public (dns) broker connections
            lang =   # The two-character ISO 639-1 language code to use by
                     # default for your agent.  Uses container default
                     # if not specified

        `[iot] =` Settings for the IOT wrapper

            sync_request_timeout = # 330 (default). How long synchronous requests at most wait before timing out. This
                                   # option should have a higher value set than core.network_retry_timeout.


        `[logging] =` Logging preferences

            amqp and rdflib are both set to Warning to prevent verbose/boring output

        `[core] =` advanced settings

            #!python
            network_retry_timeout = # seconds to retry message sending for if no
                                    # connection. 0 to disable.
                                    # IOT functions that make requests without
                                    # internet access will block until success
                                    # or retry_timeout

            socket_timeout = # 10 (default) Underlying socket connection/operation timeout

            auto_encode_decode = # 1 (default). If a dict is shared it can be
                                 # automatically encoded and decoded.
                                 # Disable with = 0.

            queue_size = # 128 (default). Maximum number of (outgoing) requests to allow in pending
                         # request queue before blocking. Set to zero for unlimited. Whether queue
                         # fills up depends on latency & throughput of network & container as well as
                         # throttling setting.

            throttle = # Automatic request (outgoing) throttling, specified as comma-separate list of
                       # REQUESTS/INTERVAL pairs. E.g. '180/60,600/300' would result in no more than 180
                       # requests being sent over the last 60 seconds and no more than 600 requests over the
                       # last 5 minutes. Used to prevent rate-limiting containers from temporarily banning
                       # the client without requiring application code to introduce artificial delays. Note:
                       # The limits should be set a bit lower than the hard limits imposed by container.
        """
        self.__fname = None
        self.__config = {}
        #
        # Defaults if not specified in config file
        self.__defaults = {
            'agent': {
                'vhost': 'container1',
                'prefix': ''
            },
            'iot': {
                'sync_request_timeout': 330
            },
            'core': {
                'network_retry_timeout': 300,
                'socket_timeout': 10,
                'auto_encode_decode': 1,
                'queue_size': 128,
                'throttle': '480/30,1680/300'
            },
            'logging': {
                'amqp': 'warning',
                'rdflib': 'warning'
            }
        }
        #
        self.__config = {
            'iot': {},
            'core': {},
            'agent': {},
            'logging': {}
        }
        # Sanity, check the config file exists and is valid
        self.__fname = fn
        if string is not None and fn is None:
            conf_stream = StringIO(string)
            conf_name = 'string'
        else:
            self.__fname = self._file_loc()
            conf_name = self.__fname
            if os.path.exists(self.__fname):
                conf_stream = open(self.__fname, 'r')
            else:
                conf_stream = StringIO()
        #
        cpa = ConfigParser()
        try:
            if PY3:
                cpa.read_file(conf_stream, source=conf_name)  # pylint: disable=no-member
            else:
                cpa.readfp(conf_stream, conf_name)  # pylint: disable=deprecated-method
        finally:
            conf_stream.close()

        for ese in cpa.sections():
            for eva in cpa.options(ese):
                self.update(ese, eva, cpa.get(ese, eva))

    def _file_loc(self):
        """_file_loc helper returns a possible config filename.
        EG /tmp/stuff/fish.py -> /tmp/stuff/fish.ini
        """
        if self.__fname is None:
            f = os.path.splitext(os.path.basename(argv[0]))[0] + '.ini'
            cwd = os.getcwd()
            # todo: prefer script path or current path ??
            # print(os.path.realpath(sys.argv[0]))
            # todo: if os.path.exists(os.path.join(cwd, main.__file__)):
            return os.path.join(cwd, f)
        return self.__fname

    def setup_logging(self):
        """Setup logging module based on known modules in the config file
        """
        logging.getLogger('amqp').setLevel(str_to_logging(self.get('logging', 'amqp')))
        logging.getLogger('rdflib').setLevel(str_to_logging(self.get('logging', 'rdflib')))

    def save(self, filename=None):
        """Write config to file."""
        if self.__fname is None and filename is None:
            raise ValueError('Config loaded from string, no filename specified')
        conf = self.__config
        cpa = dict_to_cp(conf)
        with open(self.__fname if filename is None else filename, 'w') as f:
            cpa.write(f)

    def get(self, section, val):
        """Get a setting or the default

        `Returns` The current value of the setting `val` or the default, or `None` if not found

        `section` (mandatory) (string) the section name in the config E.g. `"agent"`

        `val` (mandatory) (string) the section name in the config E.g. `"host"`
        """
        val = val.lower()
        if section in self.__config:
            if val in self.__config[section]:
                # logger.debug('get config %s %s = %s', section, val, self.__config[section][val])
                return self.__config[section][val]
        if section in self.__defaults:
            if val in self.__defaults[section]:
                # logger.debug('get defaults %s %s = %s', section, val, self.__defaults[section][val])
                return self.__defaults[section][val]
        return None

    def set(self, section, val, data):
        """Add a setting to the config

        `section` (mandatory) (string) the section name in the config E.g. `"agent"`

        `val` (mandatory) (string) the section name in the config E.g. `"host"`

        `data` (mandatory) (as appropriate) the new value for the `val`
        """
        val = val.lower()
        if section in self.__config:
            # logger.debug('set %s %s = %s', section, val, data)
            self.__config[section][val] = data

    def update(self, section, val, data):
        """Add a setting to the config, but if same as default or None then no action.
        This saves the .save writing the defaults

        `section` (mandatory) (string) the section name in the config E.g. `"agent"`

        `val` (mandatory) (string) the section name in the config E.g. `"host"`

        `data` (mandatory) (as appropriate) the new value for the `val`
        """
        k = self.get(section, val)
        # logger.debug('update %s %s from: %s to: %s', section, val, k, data)
        if data is not None and k != data:
            self.set(section, val, data)


def dict_to_cp(dic):
    ret = ConfigParser()
    for esc in dic:
        if dic[esc]:
            ret.add_section(esc)
        for eva in dic[esc]:
            ret.set(esc, eva, str(dic[esc][eva]))
    return ret


def str_to_logging(level):
    level = level.lower()
    if level == 'critical':
        return logging.CRITICAL
    if level == 'error':
        return logging.ERROR
    if level == 'warning':
        return logging.WARNING
    if level == 'debug':
        return logging.DEBUG
    return logging.INFO
