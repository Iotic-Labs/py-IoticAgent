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


# Make Core.Exceptions easily accessible to IOT Wrapper
from IoticAgent.Core.Exceptions import LinkException, LinkShutdownException  # noqa  pylint: disable=unused-import


class IOTException(Exception):
    """Base Exception class for IOT"""

    def __init__(self, msg, event=None):
        super(IOTException, self).__init__(msg)
        self.__event = event

    @property
    def event(self):
        """
        Returns:
            RequestEvent instance associated with exception, or None if not available/applicable
        """
        return self.__event


class IOTSyncTimeout(IOTException):
    """Synchronous request timeout (see IOT.sync_request_timeout configuration option). Raised when a request does not
    complete within the timeout."""


class IOTUnknown(IOTException):
    """Request FAILED because of Unkown resource (EG Thing not found)"""


class IOTMalformed(IOTException):
    """Request FAILED due to invalid parameters (this might indicate agent incompatibility)"""


class IOTNotAllowed(IOTException):
    """Request FAILED to unsupporter request (e.g. a feature is not enabled/available)"""


class IOTInternalError(IOTException):
    """Request FAILED with Internal Error"""


class IOTAccessDenied(IOTException):
    """Request FAILED with ACL Access Denied"""


class IOTClientError(IOTException):
    """Unexpected agent-local failure"""
