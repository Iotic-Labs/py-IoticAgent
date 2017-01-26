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
"""Constants for Units and helper class to build complete JSON tree of units from
"""

from __future__ import print_function, unicode_literals

import os
import json
import logging
logger = logging.getLogger(__name__)

try:
    import rdflib
except ImportError:
    rdflib = None


#
# Common units constants
# - Base Units
AMPERE = 'http://purl.obolibrary.org/obo/UO_0000011'
'''Electric current unit'''
METRE = 'http://purl.obolibrary.org/obo/UO_0000008'
'''Metric distance unit = 100 cm'''
METER = 'http://purl.obolibrary.org/obo/UO_0000008'
'''Metric distance unit = 100 cm - alternative spelling'''
# - Temperature
CELSIUS = 'http://purl.obolibrary.org/obo/UO_0000027'
'''Temperature units where the freezing point of water at 273.15 Kelvin is considered 0C and the boiling point 283.15K
is 100C'''
FAHRENHEIT = 'http://purl.obolibrary.org/obo/UO_0000195'
'''A temperature unit which is equal to 5/9ths of a kelvin. Negative 40 degrees Fahrenheit is equal to negative 40
degrees Celsius'''
KELVIN = 'http://purl.obolibrary.org/obo/UO_0000012'
'''A thermodynamic temperature unit. 0K is "absolute zero", ~293K is "room temperature", i.e. 20C'''
# - Speed
METER_PER_SEC = 'http://purl.obolibrary.org/obo/UO_0000094'
'''A speed/velocity unit which is equal to the speed of an object traveling 1 meter distance in one second'''
# - Frequency
HERTZ = 'http://purl.obolibrary.org/obo/UO_0000106'
'''A frequency unit which is equal to 1 complete cycle of a recurring phenomenon in 1 second.'''
MEGAHERTZ = 'http://purl.obolibrary.org/obo/UO_0000325'
'''A frequency unit which is equal 1 Million Hz'''
# - Time
SECOND = 'http://purl.obolibrary.org/obo/UO_0000010'
''' A time unit which is equal to the duration of 9,192,631,770 periods of the radiation
 corresponding to the transition between the two hyperfine levels
 of the ground state of the caesium 133 atom
'''
# - Energy
JOULE = 'http://purl.obolibrary.org/obo/UO_0000112'
'''An energy unit which is equal to the energy required when a force of 1 newton moves an object 1 meter'''
WATT_HOUR = 'http://purl.obolibrary.org/obo/UO_0000223'
'''An energy unit which is equal to the amount of electrical energy equivalent to a one-watt load drawing power for one
hour'''
KILOWATT_HOUR = 'http://purl.obolibrary.org/obo/UO_0000224'
'''An energy unit which is equal to 1000 Watt-hours'''
# - Power
WATT = 'http://purl.obolibrary.org/obo/UO_0000114'
'''A power unit which is equal to the power used when work is done at the rate of 1 joule per second'''
# - Electric potential
VOLT = 'http://purl.obolibrary.org/obo/UO_0000218'
'''An electric potential difference unit which is equal to the work per unit charge'''
# - Force
NEWTON = 'http://purl.obolibrary.org/obo/UO_0000108'
'''A force unit which is equal to the force required to cause an acceleration of 1m/s2 of a mass of 1 Kg'''
# - Illuminance
LUX = 'http://purl.obolibrary.org/obo/UO_0000116'
'''An illuminance unit which is equal to the illuminance produced by 1 lumen evenly spread over an area 1 m^[2]'''
# - Pressure
MM_MERCURY = 'http://purl.obolibrary.org/obo/UO_0000272'
'''A unit of pressure equal to the amount of fluid pressure one millimeter deep in mercury at 0C'''
PASCAL = 'http://purl.obolibrary.org/obo/UO_0000110'
''' A pressure unit which is equal to the pressure or stress on a surface caused by a force of 1 newton spread over a
surface of 1 m^[2]'''
# - Radiation
ROENTGEN = 'http://purl.obolibrary.org/obo/UO_0000136'
'''An exposure unit which is equal to the amount of radiation required to liberate positive
 and negative charges of one electrostatic unit of charge in 1  cm^[3] of air
'''
BECQUEREL = 'http://purl.obolibrary.org/obo/UO_0000132'
'''An activity (of a radionuclide) unit which is equal to the activity of a quantity
 of radioactive material in which one nucleus decays per second or
 there is one atom disintegration per second
'''
COUNTS_PER_MIN = 'http://purl.obolibrary.org/obo/UO_0000148'
'''An activity (of a radionuclide) unit which is equal to the number of light
 emissions produced by ionizing radiation in one minute.
'''
# - Distance
CM = 'http://purl.obolibrary.org/obo/UO_0000015'
'''A length unit which is equal to one hundredth of a meter'''


class Units(object):

    def __init__(self, uofn=None):
        # Get a location for the uo.owl
        self.__owlfn = 'https://unit-ontology.googlecode.com/svn/trunk/uo.owl'
        if uofn is not None and os.path.exists(uofn):
            self.__owlfn = uofn
        else:
            pfn = os.path.join(os.getcwd(), 'uo.owl')
            if os.path.exists(pfn):
                self.__owlfn = pfn
        #
        self.__query = """
            ## SPARQL to get all labels and comments of all classes which are sub-classes of a parent
            prefix rdf:        <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            prefix rdfs:        <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?s ?label ?comment
            WHERE
            {
            ?s rdfs:subClassOf <%s> .
            ?s rdfs:label ?label .
            ?s rdfs:comment ?comment
            }
            """
        #
        if self.__owlfn.startswith('https://'):
            logger.warning("Downloading: " + self.__owlfn)
        self.__graph = rdflib.Graph()
        if rdflib is None:
            raise RuntimeError('rdflib module not available')
        self.__graph.parse(self.__owlfn, format="xml")
        #
        logger.warning("Building Units")
        self.units = self.__build_units()

    def __build_units(self, parent='http://purl.obolibrary.org/obo/UO_0000000'):
        ret = []
        qres = self.__graph.query(self.__query % parent)
        for s, label, comment in qres:
            ret.append((s, label, comment, self.__build_units(parent=s)))
        return ret

    def print_units(self, parent=None, indent=0, indentsize=4):
        if parent is None:
            parent = self.units
        for s, label, comment, children in parent:
            print("%s %s => %s (%s)" % ((' ' * indent), s, label, comment))
            if len(children):
                self.print_units(parent=children, indent=indent + indentsize, indentsize=indentsize)

    def save_json(self, jsonfn=None, pretty=True):
        """Write a .json file with the units tree
        jsonfn='path/file.name' default os.getcwd() + 'units.json'
        pretty=True use JSON dumps pretty print for human readability
        """
        if jsonfn is None:
            jsonfn = os.path.join(os.getcwd(), 'units.json')
        #
        jsondump = None
        sort_keys = False
        indent = 0
        if pretty:
            sort_keys = True
            indent = 4
        jsondump = json.dumps(self.units, sort_keys=sort_keys, indent=indent)
        #
        with open(jsonfn, 'w') as f:
            f.write(jsondump)
            return True
        return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    Units().save_json()
