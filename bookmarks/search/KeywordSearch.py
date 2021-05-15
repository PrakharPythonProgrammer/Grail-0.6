"""Basic keyword search for bookmarks."""

__version__ = '$Revision: 1.3 $'

import string


class KeywordEditor:
    def __init__(self, frame, options=None):
        if options is None:
            options = KeywordOptions()
        self.__options = options
        self.__frame = frame

    def get_options(self):
        return self.__options


class KeywordMatcher:
    def __init__(self, options):
        self.__keywords = options.keywords()
        self.__case_sensitive = options.case_sensitive()
        self.__and = options.and_keywords()

    def match_Bookmark(self, bookmark):
        return self.__match(bookmark)

    def match_Folder(self, folder):
        return self.__match(folder), 1

    __s = ".,-!@#$%^&*(){}[]|+=?'\""
    __tr = string.maketrans(__s, " " * len(__s))

    def __match(self, node):
        keywords = self.__keywords
        if not keywords:
            return 0
        text = "%s %s" % (node.description(), node.title())
        if not self.__case_sensitive:
            text = string.lower(text)
        words = string.split(string.translate(text, self.__tr))
        if not words:
            return 0
        d = {}
        for w in words:
            d[w] = 1
        has_word = d.has_key
        if self.__and:
            # require that all are present:
            for kw in keywords:
                if not has_word(kw):
                    return 0
            return 1
        else:
            # at least one keyword must be present:
            for kw in keywords:
                if has_word(kw):
                    return 1


class KeywordOptions:
    __keywords = ()
    __keywords_text = ""
    __and_keywords = 0
    __case_sensitive = 0

    def __init__(self):
        # defined in case we need additional stuff later;
        # require subclasses to call it.
        pass

    def set_case_sensitive(self, case_sensitive):
        case_sensitive = case_sensitive and 1 or 0
        if case_sensitive != self.__case_sensitive:
            self.__case_sensitive = case_sensitive
            self.set_keywords(self.__keywords_text)

    def set_keywords(self, keywords=""):
        if keywords != self.__keywords_text:
            self.__keywords_text = keywords
            kwlist = string.split(keywords)
            if not self.__case_sensitive:
                kwlist = map(string.lower, kwlist)
            self.__keywords = tuple(kwlist)

    def case_sensitive(self):
        return self.__case_sensitive

    def keywords(self):
        return self.__keywords

    def and_keywords(self):
        return self.__and_keywords
