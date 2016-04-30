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
"""Simple database for key-value data.  Used for saving the last feed data or control request recieved.
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from sys import argv
import os.path

from ubjson import dumpb as ubjdumpb, loadb as ubjloadb

from IoticAgent.Core.compat import Lock


class DB(object):

    def __init__(self, fn=None):
        self.__lock = Lock()
        self.__data = {
            'kv': {}}
        #
        self.__fn = fn
        if fn is None:
            self.__fn = self._file_loc()
        #
        self.__load()  # Load file if it exists

    def _file_loc(self):
        """_file_loc helper returns a possible DB filename.
        EG /tmp/stuff/fish.py -> /tmp/stuff/fish.db
        """
        if self.__fn is None:
            f = os.path.splitext(os.path.basename(argv[0]))[0] + '.db'
            cwd = os.getcwd()
            return os.path.join(cwd, f)
        return self.__fn

    def kv_set(self, key, value=None):
        """Set a key/value pair in the store. Will create, update or delete depending on the existence or otherwise
        of the `key`

        `key` (mandatory) (string) The key of the value to set

        `value` (optional) (as appropriate) The value to set against the `key`
        """
        with self.__lock:
            if value is None:
                self.__data['kv'].pop(key, None)
            else:
                self.__data['kv'][key] = value
        self.__save()

    def kv_get(self, key=None):
        """Get a value from the store or get all key/values if `key` is `None`

        Returns the entire key/value store if key is `None`, just the value of the key if set

        Raises `KeyError` if the key is specified but not found

        `key` (optional) (string) The key of the value to get or, if `None` get all the key/value pairs
        """
        with self.__lock:
            if key is None:
                return self.__data['kv']
            else:
                return self.__data['kv'][key]

    def __load(self):
        if os.path.exists(self.__fn):
            with self.__lock:
                with open(self.__fn, 'rb') as f:
                    data = f.read()
                    if len(data):
                        self.__data = ubjloadb(data)

    def __save(self):
        with self.__lock:
            with open(self.__fn, 'wb') as f:
                f.write(ubjdumpb(self.__data))
