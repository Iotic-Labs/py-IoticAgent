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

import binascii

from . import Const

# Action types
C_TYPES = {
    Const.C_CREATE: 'CREATE',
    Const.C_UPDATE: 'UPDATE',
    Const.C_DELETE: 'DELETE',
    Const.C_LIST: 'LIST'}

# Resources
R_TYPES = {
    Const.R_PING: 'PING',
    Const.R_ENTITY: 'ENTITY',
    Const.R_FEED: 'FEED',
    Const.R_CONTROL: 'CONTROL',
    Const.R_SUB: 'SUB',
    Const.R_ENTITY_META: 'ENTITY_META',
    Const.R_FEED_META: 'FEED_META',
    Const.R_CONTROL_META: 'CONTROL_META',
    Const.R_VALUE_META: 'VALUE_META',
    Const.R_ENTITY_TAG_META: 'ENTITY_TAG_META',
    Const.R_FEED_TAG_META: 'FEED_TAG_META',
    # Const.R_VALUE_TAG_META: 'VALUE_TAG_META',  # Note: Removed from QAPI
    Const.R_CONTROL_TAG_META: 'CONTROL_TAG_META',
    Const.R_SEARCH: 'SEARCH',
    Const.R_DESCRIBE: 'DESCRIBE',
    Const.R_PROPERTY_META: 'PROP_META',
    Const.R_PROPERTY_SEARCH_META: 'PROP_SEARCH'
}

# Container responses
M_TYPES = {
    Const.E_COMPLETE: 'COMPLETE',
    Const.E_PROGRESS: 'PROGRESS',
    Const.E_FAILED: 'FAILED',
    Const.E_CREATED: 'CREATED',
    Const.E_DUPLICATED: 'DUPLICATED',
    Const.E_DELETED: 'DELETED',
    Const.E_FEEDDATA: 'FEEDDATA',
    Const.E_CONTROLREQ: 'CONTROLREQ',
    Const.E_SUBSCRIBED: 'SUBSCRIBED',
    Const.E_RENAMED: 'RENAMED',
    Const.E_REASSIGNED: 'REASSIGNED',
    Const.E_RECENTDATA: 'RECENTDATA'}

M_SUB_TYPES = {
    Const.E_FAILED: {Const.E_FAILED_CODE_NOTALLOWED: 'NOTALLOWED',
                     Const.E_FAILED_CODE_UNKNOWN: 'UNKNOWN',
                     Const.E_FAILED_CODE_MALFORMED: 'MALFORMED',
                     Const.E_FAILED_CODE_DUPLICATE: 'DUPLICATE',
                     Const.E_FAILED_CODE_INTERNALERROR: 'INTERNALERROR',
                     Const.E_FAILED_CODE_LOWSEQNUM: 'LOWSEQNUM',
                     Const.E_FAILED_CODE_ACCESSDENIED: 'ACCESSDENIED'},
    Const.E_PROGRESS: {Const.E_PROGRESS_CODE_ACCEPTED: 'ACCEPTED',
                       Const.E_PROGRESS_CODE_REMOTEDELAY: 'REMOTEDELAY',
                       Const.E_PROGRESS_CODE_UPDATE: 'UPDATE'}
}

M_TYPES_FAILED = {
    Const.E_FAILED_CODE_NOTALLOWED: 'NOTALLOWED',
    Const.E_FAILED_CODE_UNKNOWN: 'UNKNOWN',
    Const.E_FAILED_CODE_MALFORMED: 'MALFORMED',
    Const.E_FAILED_CODE_DUPLICATE: 'DUPLICATE',
    Const.E_FAILED_CODE_INTERNALERROR: 'INTERNALERROR',
    Const.E_FAILED_CODE_LOWSEQNUM: 'LOWSEQNUM',
    Const.E_FAILED_CODE_ACCESSDENIED: 'ACCESSDENIED'}


def decode_sent_msg(pref, message, pretty=False):
    """decode_sent_msg: Return a string of the decoded message
    """
    newline = "\n" if pretty else " "
    indent = "    " if pretty else ""
    start = newline + indent

    out = []
    out.append("%s%s{%sSEQNUM: %d," % (pref, newline, start, message[Const.W_SEQ]))
    out.append("%sCOMPRESSION: %d," % (start, message[Const.W_COMPRESSION]))
    out.append("%sHASH: %s...," % (start, str(binascii.b2a_hex(message[Const.W_HASH]).decode('ascii'))[:10]))
    out.append("%sMESSAGE:%s{%sCLIENTREF: %s," % (start, start, start + indent,
                                                  message[Const.W_MESSAGE][Const.M_CLIENTREF]))
    out.append("%sRESOURCE: %s," % (start + indent, R_TYPES[message[Const.W_MESSAGE][Const.M_RESOURCE]]))
    out.append("%sTYPE: %s," % (start + indent, C_TYPES[message[Const.W_MESSAGE][Const.M_TYPE]]))
    out.append("%sACTION: %s," % (start + indent, message[Const.W_MESSAGE][Const.M_ACTION]))
    if Const.M_RANGE in message[Const.W_MESSAGE]:
        out.append("%sRANGE: %s," % (start + indent, message[Const.W_MESSAGE][Const.M_RANGE]))
    out.append("%sPAYLOAD: %s%s}%s}" % (start + indent, message[Const.W_MESSAGE][Const.M_PAYLOAD], start, newline))

    return ''.join(out)


def decode_rcvd_msg(pref, message, seqnum, pretty=False):
    """decode_rcvd_msg: Return string of received message expanding short codes, optionally with newlines and indent
    """
    newline = "\n" if pretty else " "
    indent = "    " if pretty else ""
    start = newline + indent

    out = []
    out.append("%s%s{%sSEQNUM: %d," % (pref, newline, start, seqnum))
    out.append("%sCLIENTREF: %s," % (start, message[Const.M_CLIENTREF]))
    out.append("%sTYPE: %s," % (start, M_TYPES[message[Const.M_TYPE]]))
    if message[Const.M_TYPE] in M_SUB_TYPES:
        out.append("%sPAYLOAD: {CODE: %s, MESSAGE: %s}" %
                   (start, M_SUB_TYPES[message[Const.M_TYPE]][message[Const.M_PAYLOAD][Const.P_CODE]],
                    message[Const.M_PAYLOAD][Const.P_MESSAGE]))
    else:
        payload = None
        if message[Const.M_PAYLOAD] is not None:
            payload = {}
            for item in message[Const.M_PAYLOAD]:
                if item == Const.P_RESOURCE:
                    payload['RESOURCE'] = R_TYPES[message[Const.M_PAYLOAD][Const.P_RESOURCE]]
                else:
                    payload[item] = message[Const.M_PAYLOAD][item]
        out.append("%sPAYLOAD: %s" % (start, payload))
    out.append("%s}" % newline)

    return ''.join(out)
