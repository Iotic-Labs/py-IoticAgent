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
"""Helper object for getting and setting metadata for Iotic Things programmatically
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

try:
    from rdflib import Literal
    from rdflib.namespace import Namespace, XSD
except ImportError:
    # ResourceMeta (parent class) will log & raise so ignore here
    pass

from IoticAgent.Core import Validation

from .ResourceMeta import ResourceMeta, IOTIC_NS


GEO_NS = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")


class ThingMeta(ResourceMeta):
    """Metadata helper for Thing class.  Wraps RDF graph and provides simple
    get/set/delete methods for location.  All other methods inherited from ResourceMeta
    """

    _labelPredicate = IOTIC_NS.entityLabel
    _commentPredicate = IOTIC_NS.entityComment

    def set_location(self, lat, lon):
        Validation.location_check(lat, lon)
        # should only have one location, so delete old lat/lon first
        self.delete_location()
        subj = self._get_uuid_uriref()
        self._graph.add((subj, GEO_NS.lat, Literal('%s' % lat, datatype=XSD.float)))
        self._graph.add((subj, GEO_NS.long, Literal('%s' % lon, datatype=XSD.float)))

    def get_location(self):
        """Gets the current geo location of your Thing

        Returns tuple of `(lat, lon)` in `float` or `(None, None)` if location is not set for this Thing
        """
        lat = None
        lon = None
        # note: always picks from first triple
        for _, _, o in self._graph.triples((None, GEO_NS.lat, None)):
            lat = float(o)
            break
        for _, _, o in self._graph.triples((None, GEO_NS.long, None)):
            lon = float(o)
            break

        return lat, lon

    def delete_location(self):
        """Deletes all the `geo:lat` and `geo:long` metadata properties on your Thing
        """
        # normally this should only remove one triple each
        for s, p, o in self._graph.triples((None, GEO_NS.lat, None)):
            self._graph.remove((s, p, o))
        for s, p, o in self._graph.triples((None, GEO_NS.long, None)):
            self._graph.remove((s, p, o))
