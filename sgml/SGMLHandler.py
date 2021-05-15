"""Document handler classes for use in handling SGML documents.
"""
__version__ = "$Revision: 1.1 $"
# $Source: /projects/cvsroot/grail/dist/src/sgml/SGMLHandler.py,v $

import SGMLLexer
import SGMLParser


class ElementHandler:
    def close(self):
        pass

    def get_taginfo(self, tag):
        start = do = end = None
        klass = self.__class__
        if hasattr(klass, "start_" + tag):
            start = getattr(klass, "start_" + tag)
            if hasattr(klass, "end_" + tag):
                end = getattr(klass, "end_" + tag)
        elif hasattr(klass, "do_" + tag):
            do = getattr(klass, "do_" + tag)
        if start or do:
            return SGMLParser.TagInfo(tag, start, do, end)

    def handle_endtag(self, tag, method):
        """
        """
        method(self)

    def handle_starttag(self, tag, method, attributes):
        """
        """
        method(self, attributes)


class BaseSGMLHandler(ElementHandler):
    #  The following methods are the interface subclasses need to
    #  override to support any special handling of tags, data, or
    #  anomalous conditions.

    # Example -- handle entity reference, no need to override for most
    # applications.
    entitydefs = \
               {'lt': '<', 'gt': '>', 'amp': '&', 'quot': '"'}

    def handle_entityref(self, name, terminator):
        """
        """
        table = self.entitydefs
        if table.has_key(name):
            self.handle_data(table[name])
        else:
            self.unknown_entityref(name, terminator)


    def handle_data(self, data):
        """
        """
        pass

    def handle_sdata(self, data):
        """
        """
        self.handle_data(data)

    def handle_pi(self, pi_data):
        pass

    def unknown_charref(self, ordinal, terminator):
        """
        """
        self.handle_data("%s%d%s" % (SGMLLexer.CRO, ordinal, terminator))

    def unknown_endtag(self, tag):
        """
        """
        pass

    def unknown_entityref(self, ref, terminator):
        """
        """
        self.handle_data("%s%s%s" % (SGMLLexer.ERO, ref, terminator))

    def unknown_namedcharref(self, ref, terminator):
        """
        """
        self.handle_data("%s%d%s" % (SGMLLexer.CRO, ordinal, terminator))

    def unknown_starttag(self, tag, attrs):
        """
        """
        pass

    def report_unbalanced(self, tag):
        """
        """
        pass


class CompositeHandler:
    """Compose two Handler-like classes into a composite form.

    This is intended to allow a simple class to extend the element set
    accepted by an instantiated gatherer without duplicating all the
    fundamental operations of the primary gatherer.  Both objects being
    composed need to implement the get_taginfo() method; this may be
    inherited from the ElementHandler class.

    """
    def __init__(self, primary, secondary):
        """Compose two gatherers into a single gatherer.

        primary
            The 'base' gatherer; it is expected to provide most of the
            implementation of the composite.

        secondary
            An extension to the base; it is expected to provide new tag
            handlers or extend/replace handlers already on the primary
            gatherer.
        """
        self.doctype = primary.doctype
        self.__primary = primary
        self.__secondary = secondary
        for attr in ("handle_data", "handle_sdata", "handle_entityref",
                     "unknown_entityref", "unknown_endtag",
                     "unknown_starttag", "unknown_namedcharref",
                     "report_unbalanced"):
            if hasattr(secondary, attr):
                setattr(self, attr, getattr(secondary, attr))
            else:
                setattr(self, attr, getattr(primary, attr))
        self.__tagmap = {}

    def close(self):
        self.__secondary.close()

    def get_taginfo(self, tag):
        taginfo = self.__secondary.get_taginfo(tag)
        if taginfo:
            self.__tagmap[tag] = self.__secondary
        else:
            self.__tagmap[tag] = self.__primary
            taginfo = self.__primary.get_taginfo(tag)
        return taginfo

    def handle_starttag(self, tag, method, attrs):
        self.__tagmap[tag].handle_starttag(tag, method, attrs)

    def handle_endtag(self, tag, method):
        self.__tagmap[tag].handle_endtag(tag, method)
