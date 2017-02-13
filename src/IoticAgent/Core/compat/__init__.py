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

"""Python 2.7 & 3.2/3.3 compatibility"""

# pylint: disable=unused-import,invalid-name,import-error,undefined-variable,ungrouped-imports,no-name-in-module
# pylint: disable=wrong-import-order

from __future__ import unicode_literals

from sys import version_info
from keyword import kwlist

PY3 = (version_info[0] == 3)


# PY3K
if PY3:  # noqa (complexity)
    from queue import Queue, Empty, Full  # noqa (unused import)
    from threading import Lock, RLock, Event  # noqa (unsed import)
    from urllib.parse import urlparse

    string_types = str
    unicode_type = str
    int_types = (int,)
    number_types = (int, float)

    def u(obj):
        """Casts obj to unicode string, unless already one"""
        return obj if isinstance(obj, str) else str(obj)

    def ensure_ascii(obj, name=None):
        """Checks whether obj is an ascii string. For Python 2 only also decodes plain (old) str objects"""
        if isinstance(obj, str):
            try:
                obj.encode('ascii')
            except:
                pass
            else:
                return obj
        raise ValueError('%s not a valid (ascii) string' % (name if name else 'Argument'))

    def ensure_unicode(obj, name=None):
        """Checks whether obj is a unicode string. For Python 2 only also decodes plain (old) str objects"""
        if isinstance(obj, str):
            return obj
        else:
            raise ValueError('%s not a valid (unicode) string' % (name if name else 'Argument'))

    # add keywords which are specified in PY2
    __KEYWORDS = frozenset(kwlist + ['exec', 'print'])

    def valid_identifier(name):
        """Determines whether the given name could be used a Python identifier"""
        try:
            name = ensure_unicode(name)
        except ValueError:
            return False
        return name.isidentifier() and name not in __KEYWORDS

# PY2k
else:
    import ast as _ast
    from Queue import Queue, Empty, Full  # noqa (unused import)
    from urlparse import urlparse  # noqa (unsed import)

    from .thread_utils import (InterruptableLock as Lock, InterruptableRLock as RLock,  # noqa (unsed import)
                               InterruptableEvent as Event)

    string_types = basestring  # noqa (undefined in py3)
    unicode_type = unicode  # noqa
    int_types = (int, long)  # noqa
    number_types = (int, long, float)  # noqa (long undefined in py3)

    def u(obj):
        """Casts obj to unicode string, unless already one"""
        return obj if isinstance(obj, unicode) else unicode(obj)  # noqa

    def ensure_ascii(obj, name=None):
        """Checks whether obj is an ascii string (in unicode object). For Python 2 only also decodes plain (old) str
           objects"""
        if isinstance(obj, (unicode, str)):  # noqa (undefined in py3)
            try:
                return obj.decode('ascii')
            except:
                pass
        raise ValueError('%s not a valid (ascii) string' % (name if name else 'Argument'))

    def ensure_unicode(obj, name=None):
        """Checks whether obj is a unicode string. For Python 2 only also decodes plain (old) str objects"""
        if isinstance(obj, unicode):  # noqa (undefined in py3)
            return obj
        elif isinstance(obj, str):
            return obj.decode('utf-8')
        else:
            raise ValueError('%s not a valid (unicode) string' % (name if name else 'Argument'))

    # add keywords which are specified in PY3
    __KEYWORDS = frozenset(kwlist + ['True', 'False', 'None', 'nonlocal'])

    def valid_identifier(name):
        """Determines whether the given name could be used a Python identifier"""
        try:
            name = ensure_unicode(name)
        except ValueError:
            return False

        if name in __KEYWORDS:
            return False

        try:
            root = _ast.parse(name)
        except:
            return False

        return (isinstance(root, _ast.Module) and
                len(root.body) == 1 and
                isinstance(root.body[0], _ast.Expr) and
                isinstance(root.body[0].value, _ast.Name) and
                root.body[0].value.id == name)


if version_info[:2] == (3, 2):
    # pylint: disable=exec-used
    exec("""def raise_from(value, from_value):
    if from_value is None:
        raise value
    raise value from from_value
""")
elif version_info[:2] > (3, 2):
    # pylint: disable=exec-used
    exec("""def raise_from(value, from_value):
    raise value from from_value
""")
else:
    def raise_from(value, _):
        raise value

try:
    # only available since 3.3
    from collections.abc import Sequence, Mapping, Iterable  # noqa (unused import)
except ImportError:
    from collections import Sequence, Mapping, Iterable  # noqa (unused import)

try:
    # only available since 3.3
    from time import monotonic  # noqa (unused import)
except ImportError:
    from time import time as monotonic  # noqa (unused import)


def py_version_check():
    if not ((version_info[0] == 3 and version_info[1] >= 2) or
            (version_info[0] == 2 and version_info[1] >= 7 and version_info[2] >= 5)):
        # Note: added >= 2.7.5 as SSL version can be upgraded
        raise Exception('At least Python v2.7.5 or v3.2 required (found %s)' %
                        '.'.join(str(item) for item in version_info[:3]))


def ssl_version_check():
    from ssl import OPENSSL_VERSION_INFO as sslv, OPENSSL_VERSION
    if not (sslv[0] > 1 or
            (sslv[0] == 1 and sslv[1] > 0) or
            (sslv[0] == 1 and sslv[1] == 0 and sslv[2] > 0)):
        raise Exception('At least SSL v1.0.1 required for TLS v1.2 (found %s)' % OPENSSL_VERSION)


# callback function check helper
try:  # noqa (complexity)
    # v3.3+ only
    from inspect import signature

    def arg_checker(func, *args, **kwargs):
        try:
            signature(func).bind(*args, **kwargs)
        except TypeError:
            return False
        else:
            return True

except ImportError:
    # deprecated in v3.5+
    from inspect import getcallargs
    from functools import partial

    def arg_checker(func, *args, **kwargs):
        # getcallargs doesn't support partials, hence this workaround
        if isinstance(func, partial):
            args += func.args
            if func.keywords:
                kwargs.update(func.keywords)
            func = func.func
        try:
            getcallargs(func, *args, **kwargs)  # pylint: disable=deprecated-method
        except TypeError:
            return False
        else:
            return True
