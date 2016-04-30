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
"""Utility functions
"""

from .compat import raise_from


def version_string_to_tuple(version):
    return tuple(int(part) if part.isdigit() else part for part in version.split('.'))


def validate_nonnegative_int(obj, name):
    try:
        obj = int(obj)
        if obj < 0:
            raise ValueError('%s negative' % name)
    except (ValueError, TypeError) as ex:
        raise_from(ValueError('%s invalid' % name), ex)
    return obj
