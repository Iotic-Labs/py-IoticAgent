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
"""QAPI Constants
"""

from __future__ import unicode_literals

from enum import Enum, unique

# Action types the container accepts
C_CREATE = 1
C_UPDATE = 2
C_DELETE = 3
C_LIST = 4

# Action types on calls from the container
E_COMPLETE = 1
E_PROGRESS = 2
E_PROGRESS_CODE_ACCEPTED = 1
E_PROGRESS_CODE_REMOTEDELAY = 2
E_PROGRESS_CODE_UPDATE = 3  # additional progress update
E_FAILED = 3
E_FAILED_CODE_NOTALLOWED = 1
E_FAILED_CODE_UNKNOWN = 2
E_FAILED_CODE_MALFORMED = 3
E_FAILED_CODE_DUPLICATE = 4
E_FAILED_CODE_INTERNALERROR = 5
E_FAILED_CODE_LOWSEQNUM = 6
E_FAILED_CODE_ACCESSDENIED = 7
E_CREATED = 4
E_DUPLICATED = 5
E_DELETED = 6
E_FEEDDATA = 7
E_CONTROLREQ = 8
E_SUBSCRIBED = 9
E_RENAMED = 10
E_REASSIGNED = 11
E_RECENTDATA = 12

# Resource types
R_PING = 0
R_ENTITY = 1
R_FEED = 2
R_CONTROL = 3
R_SUB = 4
R_ENTITY_META = 5
R_FEED_META = 6
R_CONTROL_META = 7
R_VALUE_META = 8
R_ENTITY_TAG_META = 9
R_FEED_TAG_META = 10
R_CONTROL_TAG_META = 11
# R_VALUE_TAG_META = 12  # Note: removed from QAPI
R_SEARCH = 13
R_DESCRIBE = 14

# Wrapper
W_SEQ = 's'
W_HASH = 'h'
W_COMPRESSION = 'c'
W_MESSAGE = 'm'

# Compression levels
COMP_NONE = 0
COMP_ZLIB = 1
COMP_LZ4F = 2

# Message
M_RESOURCE = 'r'
M_TYPE = 't'
M_CLIENTREF = 'c'
M_ACTION = 'a'
M_PAYLOAD = 'p'
M_RANGE = 'g'

# Payload
P_CODE = 'c'
P_RESOURCE = 'r'
P_MESSAGE = 'm'
P_LID = 'lid'
P_ENTITY_LID = 'entityLid'
P_POINT_ENTITY_LID = 'pointEntityLid'
P_POINT_LID = 'pointLid'
P_OLD_LID = 'oldLid'
P_EPID = 'epId'
P_ID = 'id'
P_POINT_ID = 'pointId'
P_FEED_ID = 'feedId'
P_POINT_TYPE = 'pointType'
P_MIME = 'mime'
P_DATA = 'data'
P_SUCCESS = 'success'
P_CONFIRM = 'confirm'
P_SUB_ID = 'subId'
P_TIME = 'time'
P_SAMPLES = 'samples'

#
# Configuration
# Compression Default when the COMP_SIZE threshold is passed
# Can set default or size to COMP_NONE or 0 for no compression
# Client.set_compression overwrites this!
COMP_DEFAULT = COMP_ZLIB

# comp_size when innerMsg is longer than this (selected) compression will be used
COMP_SIZE = 768


# Request-specific enumerations

@unique
class SearchScope(Enum):
    """Determines how search is performed

    `PUBLIC` - Public metadata search

    `LOCAL` - Container-local search (only available if container running in 'private' mode)

    `LOCAL_OWN` - Container-local search for own things only
    """
    PUBLIC = 'public'
    LOCAL = 'local'
    LOCAL_OWN = 'localOwn'


@unique
class SearchType(Enum):
    """Determines what results a search returns

    `FULL` - Provides most information

    `REDUCED` - Limit output including only points and their type

    `LOCATED` - Minimal location + label format (e.g. for display on a map)
    """
    FULL = 'full'
    REDUCED = 'reduced'
    LOCATED = 'located'


@unique
class DescribeScope(Enum):
    """Determines how a resource is described

    `AUTO` - Uses local meta if available, otherwise public

    `PUBLIC` - Public metadata (public)

    `LOCAL` - Container-local meta (only available if container running in 'private' mode)

    `LOCAL_OWN` - Container-local meta for own resource only
    """
    AUTO = 'auto'
    PUBLIC = 'public'
    LOCAL = 'local'
    LOCAL_OWN = 'localOwn'
