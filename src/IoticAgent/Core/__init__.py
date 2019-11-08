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
"""IoticAgent.Core module provides a Thread Safe AMQP Client connection to the Iotic Labs QAPI

Calling a request function returns a Core.RequestEvent instance on which the caller can .wait
Or check using the RequestEvent.is_set function

When the event is complete event.requestId, success and payload will be populated.
RequestEvent._messages will contain the raw messages from the queue.
"""

from __future__ import unicode_literals

__version__ = '0.6.12'

from . import Const  # noqa

from .Client import Client  # noqa

from .RequestEvent import RequestEvent  # noqa
from .ThreadSafeDict import ThreadSafeDict  # noqa
from .Validation import Validation  # noqa

from . import MessageDecoder  # noqa
