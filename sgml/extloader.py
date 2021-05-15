"""This extension loader can load TagInfo objects which provide implementations
of HTML/SGML element start/end events.
"""
__version__ = '$Revision: 1.4 $'

import string

import grailbase.extloader
import SGMLParser


class TagExtensionLoader(grailbase.extloader.ExtensionLoader):
    def find(self, name):
        mod = self.find_module(name)
        taginfo = None
        if mod is not None:
            self.load_tag_handlers(mod)
            return self.get_extension(name)
        else:
            return None

    def load_tag_handlers(self, mod):
        as_list = 1
        if hasattr(mod, "ATTRIBUTES_AS_KEYWORDS"):
            as_list = not mod.ATTRIBUTES_AS_KEYWORDS
        handlers = {}
        for name, function in mod.__dict__.items():
            parts = string.split(name, "_")
            if len(parts) != 2:
                continue
            if not (parts[0] and parts[1]):
                continue
            [action, tag] = parts
            start = do = end = None
            if handlers.has_key(tag):
                start, do, end = handlers[tag]
            if action == 'start':
                start = function
                if as_list:
                    start = ListAttributesCaller(start)
            elif action == 'end':
                end = function
            elif action == 'do':
                do = function
                if as_list:
                    do = ListAttributesCaller(do)
            handlers[tag] = (start, do, end)
        for tag, (start, do, end) in handlers.items():
            if start or do:
                taginfo = SGMLParser.TagInfo(tag, start, do, end)
                self.add_extension(tag, taginfo)


class ListAttributesCaller:
    """Call a tag handler function, translating the attributes dictionary to
    a list.

    This is useful for legacy HTML tag extensions.  The SGML & HTML support
    in Grail never has to see attributes as lists; simplifying and supporting
    a number of automatic value normalizations (esp. URI normalization and ID/
    IDREF support).
    """
    def __init__(self, func):
        self.__func = func

    def __call__(self, parser, attrs):
        return apply(self.__func, (parser, attrs.items()))
