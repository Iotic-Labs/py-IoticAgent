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
    pass


class IOTUnknown(IOTException):
    """A request failed because of Unkown resource (EG Thing not found)"""
    pass


class IOTMalformed(IOTException):
    """Any failed request FAILED (Not allowed resource, malformed request)"""
    pass


class IOTInternalError(IOTException):
    """Request FAILED with Internal Error"""
    pass


class IOTAccessDenied(IOTException):
    """Request FAILED with ACL Access Denied"""
    pass


class IOTClientError(IOTException):
    """Unexpected agent-local failure"""
    pass
