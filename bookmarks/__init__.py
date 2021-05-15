import os
import string
import sys
import urlparse


class Error:
    def __init__(self, filename):
        self.filename = filename
    def __repr__(self):
        C = self.__class__
        return "<%s.%s for file %s>" \
               % (C.__module__, C.__name__, self.filename)


class BookmarkFormatError(Error):
    def __init__(self, filename, problem, what="file"):
        Error.__init__(self, filename)
        self.problem = problem
        self.what = what

    def __repr__(self):
        C = self.__class__
        return "<%s.%s for %s %s>" \
               % (C.__module__, C.__name__, self.what, self.filename)

    def __str__(self):
        return "%s for %s %s" % (self.problem, self.what, self.filename)


class PoppedRootError(Error):
    pass


class BookmarkReader:
    def __init__(self, parser):
        self.__parser = parser

    def read_file(self, fp):
        self.__parser.feed(fp.read())
        self.__parser.close()
        return self.__parser.get_root()


class BookmarkWriter:
    # base class -- subclasses are required to set _filetype attribute
    def get_filetype(self):
        return self._filetype


__tr_map = {}
for c in map(chr, range(128)):
    __tr_map[c] = c
for i in range(128, 256):
    __tr_map[chr(i)] = "&#%d;" % i
for c in "<>&'\"":
    __tr_map[c] = "&#%d;" % ord(c)

def _prepstring(s):
    """Return HTML/XML safe copy of a string."""
    return string.join(map(__tr_map.get, s), '')



pubid_fmt = "+//IDN python.org//DTD XML Bookmark Exchange Language %s//EN"
sysid_fmt = "http://www.python.org/topics/xml/dtds/xbel-%s.dtd"

XBEL_1_0_PUBLIC_ID = pubid_fmt % "1.0"
XBEL_1_0_SYSTEM_ID = sysid_fmt % "1.0"
XBEL_1_0_ROOT_ELEMENTS = ("xbel", "folder", "bookmark", "alias", "separator")

# not yet released
XBEL_1_1_PUBLIC_ID = pubid_fmt % "1.1"
XBEL_1_1_SYSTEM_ID = sysid_fmt % "1.1"
XBEL_1_1_ROOT_ELEMENTS = XBEL_1_0_ROOT_ELEMENTS + ("link",)

del pubid_fmt
del sysid_fmt


def check_xml_format(buffer):
    import xmlinfo
    try:
        info = xmlinfo.get_xml_info(buffer)
    except xmlinfo.Error:
        return None
    if info.doc_elem in XBEL_1_0_ROOT_ELEMENTS:
        public_id = info.public_id
        system_id = info.system_id
        if public_id == XBEL_1_0_PUBLIC_ID:
            if system_id == XBEL_1_0_SYSTEM_ID or not system_id:
                return "xbel"
        elif public_id:
            pass
        elif system_id == XBEL_1_0_SYSTEM_ID:
            return "xbel"


# The canonical table of supported bookmark formats:
__formats = {
    # format-name     first-line-magic
    #                  short-name   extension
    "html":          ('<!DOCTYPE\s+(GRAIL|NETSCAPE)-Bookmark-file-1',
                      "html",      ".html",	"html"),
    "pickle":        ('#.*GRAIL-Bookmark-file-[234]',
                      "pickle",    ".pkl",	"xbel"),
    "xbel":          ('<(\?xml|!DOCTYPE)\s+xbel',
                      "xbel",      ".xml",	"xbel"),
    }

__format_inited = 0

def __init_format_table():
    global __format_inited
    global __format_table
    import re
    __format_table = table = []
    for result, (rx, sname, ext, outfmt) in __formats.items():
        if rx:
            rx = re.compile(rx)
            table.append((rx, result))
    __format_inited = 1

def get_format(fp):
    if not __format_inited:
        __init_format_table()
    format = None
    pos = fp.tell()
    try:
        line1 = fp.read(1024)
        for re, fmt in __format_table:
            if re.match(line1):
                format = fmt
                break
        else:
            format = check_xml_format(line1)
    finally:
        fp.seek(pos)
    return format


def get_short_name(format):
    return __formats[format][1]

def get_default_extension(format):
    return __formats[format][2]


def get_parser_class(format):
    exec "from formats.%s_parser import Parser" % get_short_name(format)
    return Parser

def get_writer_class(format):
    exec "from formats.%s_writer import Writer" % get_short_name(format)
    return Writer

def get_output_format(format):
    return __formats[format][3]
