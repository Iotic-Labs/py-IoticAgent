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
"""Wrapper object for Iotic resources
"""
from __future__ import unicode_literals

from IoticAgent.Core.Validation import Validation


class Resource(object):
    """Resource base class
    """

    def __init__(self, client, guid):
        self.__client = client
        self.__guid = Validation.guid_check_convert(guid)

    @property
    def guid(self):
        """The Globally Unique ID of this resource in hex form (undashed).
        """
        return self.__guid

    @property
    def _client(self):
        """For internal use: reference to IOT.Client instance"""
        return self.__client
