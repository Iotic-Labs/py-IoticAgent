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

from collections import namedtuple

from .compat import monotonic, unicode_type, int_types


class PreparedMessage(namedtuple('nt_PreparedMessage', 'inner_msg requestId time')):
    """Messages are stored within queue"""

    def __new__(cls, inner_msg, requestId, time=None):
        if not isinstance(inner_msg, dict):
            raise ValueError('inner_msg')
        if not isinstance(requestId, unicode_type):
            raise ValueError('requestId')
        if time is None:
            time = monotonic()
        elif not isinstance(time, int_types) and time > 0:
            raise ValueError('time')
        return super(PreparedMessage, cls).__new__(cls, inner_msg, requestId, time)
