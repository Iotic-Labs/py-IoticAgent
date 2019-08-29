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
"""
Base class for Helper objects for getting and setting metadata programmatically
"""
from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import Namespace, RDFS

from IoticAgent.Core import Validation

from .utils import uuid_to_hex

IOTIC_NS = Namespace('http://purl.org/net/iotic-labs#')


class ResourceMeta(object):
    """
    `Base class` for metadata helpers. Inherited by:

    * :doc:`IoticAgent.IOT.PointMeta`
    * :doc:`IoticAgent.IOT.ThingMeta`

    **Do not instantiate directly**
    """

    # overridden by subclasses
    _labelPredicate = RDFS.label
    _commentPredicate = RDFS.comment

    def __init__(self, parent, rdf, default_lang, fmt='n3'):
        #
        self.__parent = parent
        self.__fmt = fmt
        self._default_lang = default_lang
        self._graph = Graph()  # "Protected" member variable, accessible by subclasses
        self._graph.parse(data=rdf, format=fmt)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if all(item is None for item in (exc_type, exc_value, traceback)):
            self.set()

    def _get_uuid(self):
        # note: always picks from first triple
        for s, _, _ in self._graph:
            return uuid_to_hex(s)

    def _get_uuid_uriref(self):
        # note: always picks from first triple
        for s, _, _ in self._graph:
            return URIRef(s)

    def _get_properties(self, predicate):
        # returns properties as n3() encoded string
        ret = []
        for _, _, o in self._graph.triples((None, predicate, None)):
            ret.append(o.n3())
        return ret

    def _get_properties_rdf(self, predicate):
        # returns properties as rdflib objects
        ret = []
        for _, _, o in self._graph.triples((None, predicate, None)):
            ret.append(o)
        return ret

    def _remove_properties_by_language(self, predicate, lang):
        for s, p, o in self._graph.triples((None, predicate, None)):
            if o.language == lang:
                self._graph.remove((s, p, o))

    def __str__(self):
        """
        Returns:
            The RDF metadata description for this Thing/Point
        """
        return self._graph.serialize(format=self.__fmt).decode('utf8')

    def set(self):
        """
        Pushes the RDF metadata description back to the infrastructure.  This will be searchable if you have called
        :doc:`IoticAgent.IOT.Thing` Thing.set_public at any time.

        **Example 1 - Recommended**

        Use of python `with` syntax and XXXXmeta class.

        ::

            # using with calls set() for you so you don't forget
            with thing_solar_panels.get_meta() as meta_thing_solar_panels:
                meta_thing_solar_panels.set_label("Mark's Solar Panels")
                meta_thing_solar_panels.set_description("Solar Array 3.3kW")
                meta_thing_solar_panels.set_location(52.1965071,0.6067687)

        **Example 2**

        Explicit use of set

        ::

            meta_thing_solar_panels = thing_solar_panels.get_meta()

            meta_thing_solar_panels.set_label("Mark's Solar Panels")
            meta_thing_solar_panels.set_description("Solar Array 3.3kW")
            meta_thing_solar_panels.set_location(52.1965071,0.6067687)

            meta_thing_solar_panels.set()


        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure
            rdflib.plugins.parsers.notation3.`BadSyntax`: if the RDF is badly formed `n3`
            xml.sax._exceptions.`SAXParseException`: if the RDF is badly formed `xml`
        """
        self.__parent.set_meta_rdf(self._graph.serialize(format=self.__fmt).decode('utf8'), fmt=self.__fmt)

    def update(self):
        """
        Gets the latest version of your metadata from the infrastructure and updates your local copy

        Returns:
            `True` if successful, `False` otherwise

        **OR**

        Raises:
            IOTException: Infrastructure problem detected
            LinkException: Communications problem between you and the infrastructure
        """
        graph = Graph()
        graph.parse(data=self.__parent.get_meta_rdf(fmt=self.__fmt), format=self.__fmt)
        self._graph = graph

    def set_label(self, label, lang=None):
        """
        Sets the `label` metadata property on your Thing/Point.  Only one label is allowed per language, so any
        other labels in this language are removed before adding this one

        Raises:
            ValueError: Contains an error message if the parameters fail validation

        Args:
            label (string): the new text of the label
            lang (string, optional): The two-character ISO 639-1 language code to use for your label. None means use
                the default language for your agent. See :doc:`IoticAgent.IOT.Config`.
        """
        label = Validation.label_check_convert(label)
        lang = Validation.lang_check_convert(lang, default=self._default_lang)
        # remove any other labels with this language before adding
        self.delete_label(lang)
        subj = self._get_uuid_uriref()
        self._graph.add((subj, self._labelPredicate, Literal(label, lang)))

    def get_labels(self):
        """
        Gets all the `label` metadata properties on your Thing/Point.  Only one label is allowed per language, so
        you'll get a list of labels in the `N3` syntax, e.g. `["fish"@en, "poisson"@fr]`

        Returns:
            List of labels in N3 format
        """
        return self._get_properties(self._labelPredicate)

    def get_labels_rdf(self):
        """
        Gets all the `label` metadata properties on your Thing/Point.  Only one label is allowed per language, so
        you'll get a list of labels as rdflib.term.Literal objects

        Returns:
            List of labels as rdflib.term.Literals
        """

        return self._get_properties_rdf(self._labelPredicate)

    def delete_label(self, lang=None):
        """
        Deletes all the `label` metadata properties on your Thing/Point for this language

        Raises:
            ValueError: Contains an error message if the parameters fail validation

        Args:
            lang (string, optional): The two-character ISO 639-1 language code to identify your label. None means use
                the default language for your agent. See :doc:`IoticAgent.IOT.Config`
        """
        self._remove_properties_by_language(self._labelPredicate,
                                            Validation.lang_check_convert(lang, default=self._default_lang))

    def set_description(self, description, lang=None):
        """
        Sets the `description` metadata property on your Thing/Point.  Only one description is allowed per language,
        so any other descriptions in this language are removed before adding this one

        Raises:
            ValueError: Contains an error message if the parameters fail validation

        Args:
            description (string): the new text of the description
            lang (string, optional): The two-character ISO 639-1 language code to identify your label. None means use
                the default language for your agent. See :doc:`IoticAgent.IOT.Config`
        """
        description = Validation.description_check_convert(description)
        lang = Validation.lang_check_convert(lang, default=self._default_lang)
        # remove any other descriptions with this language before adding
        self.delete_description(lang)
        subj = self._get_uuid_uriref()
        self._graph.add((subj, self._commentPredicate, Literal(description, lang)))

    def get_descriptions(self):
        """
        Gets all the `description` metadata properties on your Thing/Point.  Only one description is allowed per
        language, so you'll get a list of descriptions in the `N3` syntax, e.g. `["fish tank"@en, "aquarium"@fr]`

        Returns:
            List of descriptions in N3 format or empty list if none.
        """
        return self._get_properties(self._commentPredicate)

    def get_descriptions_rdf(self):
        """
        Gets all the `description` metadata properties on your Thing/Point.  Only one description is allowed per
        language, so you'll get a list of descriptions as rdflib.term.Literals

        Returns:
            List of descriptions as rdflib.term.Literals or empty list if none.
        """
        return self._get_properties_rdf(self._commentPredicate)

    def delete_description(self, lang=None):
        """
        Deletes all the `label` metadata properties on your Thing/Point for this language

        Raises:
            ValueError: Contains an error message if the parameters fail validation

        Args:
            lang (string, optional): The two-character ISO 639-1 language code to identify your label. None means use
                the default language for your agent. See :doc:`IoticAgent.IOT.Config`
        """
        self._remove_properties_by_language(self._commentPredicate,
                                            Validation.lang_check_convert(lang, default=self._default_lang))
