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
"""Constants to hide XSD Datatypes used by Point Values
These help to describe the data in a feed so the receiving Thing can know what kind of data to expect

See also http://www.w3.org/TR/xmlschema-2/#built-in-datatypes
"""

from __future__ import unicode_literals

BASE64 = 'base64Binary'
'''Represents a sequence of binary octets (bytes) encoded according to RFC 2045,
the standard defining the MIME types (look under "6.8 Base64 Content-Transfer-Encoding").
'''
BOOLEAN = 'boolean'
'''A Boolean true or false value. Representations of true are "true" and "1"; false is denoted as "false" or "0".'''
BYTE = 'byte'
'''A signed 8-bit integer in the range [-128 -> +127]. Derived from the short datatype.'''
UNSIGNED_BYTE = 'unsignedByte'
'''An unsigned 8-bit integer in the range [0, 255]. Derived from the unsignedShort datatype.'''
DATE = 'date'
'''Represents a specific date. The syntax is the same as that for the date part of dateTime,
with an optional time zone indicator. Example: "1889-09-24".
'''
DATETIME = 'dateTime'
'''
Represents a specific instant of time. It has the form YYYY-MM-DDThh:mm:ss followed by an optional time-zone suffix.

`YYYY` is the year, `MM` is the month number, `DD` is the day number,
`hh` the hour in 24-hour format, `mm` the minute, and `ss` the second (a decimal and fraction are allowed for the
seconds part).

The optional zone suffix is either `"Z"` for Universal Coordinated Time (UTC), or a time offset of the form
`"[+|-]hh:mm"`, giving the difference between UTC and local time in hours and minutes.

Example: "2004-10-31T21:40:35.5-07:00" is a time on Halloween 2004 in Mountain Standard time. The equivalent UTC would
be "2004-11-01T04:40:35.5Z".
'''
DECIMAL = 'decimal'
'''Any base-10 fixed-point number. There must be at least one digit to the left of the decimal point, and a leading "+"
or "-" sign is allowed.
Examples: "42", "-3.14159", "+0.004".
'''
DOUBLE = 'double'
'''A 64-bit floating-point decimal number as specified in the IEEE 754-1985 standard. The external form is the same as
the float datatype.'''
DURATION = 'duration'
'''
Represents a duration of time, as a composite of years, months, days, hours, minutes, and seconds. The syntax of a
duration value has these parts:

If the duration is negative, it starts with "-".

A capital "P" is always included.

If the duration has a years part, the number of years is next, followed by a capital "Y".

If there is a months part, it is next, followed by capital "M".

If there is a days part, it is next, followed by capital "D".

If there are any hours, minutes, or seconds in the duration, a capital "T" comes next; otherwise the duration ends here.

If there is an hours part, it is next, followed by capital "H".

If there is a minutes part, it is next, followed by capital "M".

If there is a seconds part, it is next, followed by capital "S". You can use a decimal point and fraction to specify
part of a second.

Missing parts are assumed to be zero. Examples: "P1347Y" is a duration of 1347 Gregorian years;
"P1Y2MT2H5.6S" is a duration of one year, two months, two hours, and 5.6 seconds.
'''
FLOAT = 'float'
'''A 32-bit floating-point decimal number as specified in the IEEE 754-1985 standard.
Allowable values are the same as in the decimal type, optionally followed by an exponent,
or one of the special values "INF" (positive infinity), "-INF" (negative infinity), or "NaN" (not a number).

The exponent starts with either "e" or "E", optionally followed by a sign, and one or more digits.

Example: "6.0235e-23".
'''
ID = 'ID'
'''A unique identifier as in the ID attribute type from the XML standard.  Derived from the NCName datatype. '''
INT = 'int'
'''Represents a 32-bit signed integer in the range [-2,147,483,648, 2,147,483,647]. Derived from the long datatype.'''
INTEGER = 'integer'
'''Represents a signed integer. Values may begin with an optional "+" or "-" sign. Derived from the decimal datatype.'''
LANGUAGE = 'language'
'''One of the standardized language codes defined in RFC 1766. Example: "fj" for Fijian. Derived from the token type.
RFC 1766 : http://www.ietf.org/rfc/rfc1766.txt
'''
LONG = 'long'
'''A signed, extended-precision integer; at least 18 digits are guaranteed. Derived from the integer datatype. '''
STRING = 'string'
'''Any sequence of zero or more characters.'''
TIME = 'time'
'''A moment of time that repeats every day. The syntax is the same as that for dateTime,
omitting everything up to and including the separator "T". Examples: "00:00:00" is midnight,
and "13:04:00" is an hour and four minutes after noon.
'''
URI = 'anyUri'
'''
The data must conform to the syntax of a Uniform Resource Identifier (URI), as defined in RFC 2396
as amended by RFC 2732. Example: "http://www.nmt.edu/tcc/"
is the URI for the New Mexico Tech Computer Center's index page.
'''
