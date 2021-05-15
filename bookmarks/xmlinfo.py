#! /usr/bin/env python
#  -*- python -*-

"""Support for retrieving useful information about XML data, including the
public and system IDs and the document type name.

There are parts of this module which assume the native character encoding is
ASCII or a superset; this should be fixed.
"""

__version__ = "$Revision: 1.5 $"

import copy
import os
import re
import string
import struct
import sys

BOM_BE = "\xfe\xff"
BOM_LE = "\xff\xfe"

BIG_ENDIAN = "big-endian"
LITTLE_ENDIAN = "little-endian"

if struct.pack('h', 1) == struct.pack('>h', 1):
    NATIVE_ENDIANNESS = BIG_ENDIAN
else:
    NATIVE_ENDIANNESS = LITTLE_ENDIAN


class Error(Exception):
    """Base class for xmlinfo exceptions."""
    def __init__(self, *args, **kw):
        self.message = args[0]
        apply(Exception.__init__, (self,) + args, kw)

class ConversionError(Error):
    """Raised when an encoding conversion fails."""
    pass

class ParseError(Error):
    pass

class EncodingMismatchError(ParseError):
    """Raised when an extractor thinks it's reading from a stream of the
    wrong encoding.  The exception parameter is the name of a suggested
    encoding to try, or None.
    """
    def __init__(self, encoding=None):
        self.encoding = encoding
        ParseError.__init__(self, encoding)


class Record:
    public_id = None
    system_id = None
    doc_elem = None
    standalone = None
    xml_version = None
    encoding = None
    byte_order = None

    def __init__(self, **kw):
        self.__dict__.update(kw)


FieldLabels = Record(
    system_id="System ID",
    public_id="Public ID",
    doc_elem="Document Element",
    standalone="Standalone",
    xml_version="XML Version",
    encoding="Encoding",
    byte_order="Byte Order",
    )


FieldNames = dir(Record)
for _name in FieldNames[:]:
    if _name[:2] == "__":
        FieldNames.remove(_name)


def get_xml_info(buffer):
    values = Record()
    byte_order, encoding, bom = guess_byte_order_and_encoding(buffer)
    values.byte_order = byte_order
    values.encoding = encoding
    return extract(values.encoding, buffer[len(bom):], values)


def get_byte_order_mark(buffer):
    bom = buffer[:2]
    if bom in (BOM_BE, BOM_LE):
        return bom
    else:
        return ''


def guess_byte_order_and_encoding(buffer):
    """Guess the byte-order and encoding."""
    byte_order = None
    encoding = "utf-8"
    #
    bom = get_byte_order_mark(buffer)
    buffer = buffer[len(bom):]
    if bom == BOM_BE:
        return BIG_ENDIAN, "utf-16", BOM_BE
    elif bom == BOM_LE:
        return LITTLE_ENDIAN, "utf-16", BOM_LE
    elif bom == '':
        pass
    else:
        raise RuntimeError, \
              "unexpected internal condition: bad byte-order mark"
    #
    # no byte-order mark
    #
    prefix = buffer[:4]
    if prefix == "\0\0\0\x3c":
        byte_order = BIG_ENDIAN
        encoding = "ucs-4"
    elif prefix == "\x3c\0\0\0":
        byte_order = LITTLE_ENDIAN
        encoding = "ucs-4"
    elif prefix == "\0\x3c\0\x3f":
        byte_order = BIG_ENDIAN
        encoding = "utf-16"
    elif prefix == "\x3c\0\x3f\0":
        byte_order = LITTLE_ENDIAN
        encoding = "utf-16"
    elif prefix == "\x3c\x3f\x78\x6d":
        # good enough to parse the encoding declaration
        encoding = "utf-8"
    elif prefix == "\x4c\x6f\xa7\x94":
        encoding = "ebcdic"
    #
    return byte_order, encoding, ""


def extract(encoding, buffer, values, best_effort=0):
    tried = {}
    while not tried.has_key(encoding):
        tried[encoding] = 1
        v2 = copy.copy(values)
        extractor = new_extractor(encoding, buffer, v2)
        try:
            v2 = extractor.extract()
        except EncodingMismatchError, e:
            encoding = e.encoding
        except:
            if best_effort:
                # in case there's anything there
                return v2
            raise
        else:
            return v2
    raise ParseError("could not determine encoding")


_extractor_map = {}
def new_extractor(encoding, buffer, values):
    encoding = string.lower(encoding)
    klass = _extractor_map.get(encoding, Extractor)
    return klass(buffer, values)

def add_extractor_class(klass):
    for enc in klass.Encodings:
        _extractor_map[enc] = klass


class Extractor:
    VERSION_CHARS = string.letters + string.digits + "_.:-"

    Encodings = ()

    def __init__(self, buffer, values):
        self.buffer = buffer
        self.values = values

    def extract(self):
        self.parse_declaration()
        if self.values.encoding not in self.Encodings:
            raise EncodingMismatchError(self.values.encoding)
        self.skip_to_doctype()
        self.parse_doctype()
        return self.values

    def parse_declaration(self):
        try:
            self.require_ascii("<?xml", "XML declation")
        except ParseError:
            # OK to drop this for UTF-8
            return
        self.parse_VersionInfo()
        attrname, encoding = self.get_opt_pseudo_attr()
        if attrname == "encoding":
            self.values.encoding = string.lower(encoding)
            attrname, standalone = self.get_opt_pseudo_attr()
            if attrname == "standalone":
                if standalone not in ("yes", "no"):
                    raise ParseError(
                        "illegal standalone value in XML declaration: "
                         + value)
                self.values.standalone = standalone
                attrname = None
        if attrname is not None:
            raise ParseError(
                "unknown or out-of-order XML declaration attribute: "
                + attrname)
        self.skip_whitespace()
        self.require_ascii("?>", "XML declaration")

    def parse_VersionInfo(self):
        attr, verno = self.get_pseudo_attr()
        if attr != 'version':
            raise ParseError(
               "first pseudo-attribute in XML declaration must be version")
        if not verno:
            raise ParseError("version number cannot be empty")
        version_chars = self.VERSION_CHARS
        for c in verno:
            if not c in version_chars:
                raise ParseError(
                    "illegal character in XML version declaration: " + `c`)
        self.values.xml_version = verno

    def get_pseudo_attr(self):
        """Return attr/value pair using the XML declaration's idea of a
        pseudo-attribute."""
        attrname = ''
        value = ''
        self.require_whitespace("pseudo-attribute")
        while 1:
            c = self.get_ascii(1)
            if c in string.letters:
                attrname = attrname + c
                self.discard_chars(1)
            else:
                break
        if not attrname:
            raise ParseError("could not extract pseudo-attribute name")
        self.skip_whitespace()
        self.require_ascii("=", "pseudo-attribute")
        self.skip_whitespace()
        open_quote = self.get_ascii(1)
        if open_quote not in ('"', "'"):
            raise ParseError("pseudo-attribute values must be quoted")
        self.discard_chars(1)
        while 1:
            c = self.get_ascii(1)
            if not c:
                raise ParseError("could not complete pseudo-attribute value")
            self.discard_chars(1)
            if c == open_quote:
                break
            value = value + c
        return attrname, value

    def get_opt_pseudo_attr(self):
        buffer = self.buffer
        try:
            return self.get_pseudo_attr()
        except ParseError:
            self.buffer = buffer
            return None, None

    def parse_doctype(self):
        self.require_ascii("<!DOCTYPE", "doctype declaration")
        self.require_whitespace("doctype declaration")
        self.values.doc_elem = self.parse_Name("doctype declaration")
        wscount = self.skip_whitespace()
        c = self.get_ascii(1)
        if c in "]>":
            return
        self.parse_ExternalID()


    def _make_set_predicate(L):
        d = {}
        for o in L:
            d[o] = o
        return d.has_key

    BASE_CHARS = tuple(
        range(0x41, 0x5A+1) + range(0x61, 0x7A+1)
        + range(0xC0, 0xD6+1) + range(0xD8, 0xF6+1)
        + range(0xF8, 0xFF+1) + range(0x100, 0x131+1)
        + range(0x134, 0x13E+1) + range(0x141, 0x148+1)
        + range(0x14A, 0x17E+1) + range(0x180, 0x1C3+1)
        + range(0x1CD, 0x1F0+1) + range(0x1F4, 0x1F5+1)
        + range(0x1FA, 0x217+1) + range(0x250, 0x2A8+1)
        + range(0x2BB, 0x2C1+1) + [0x386]
        + range(0x388, 0x38A+1) + [0x38C]
        + range(0x38E, 0x3A1+1) + range(0x3A3, 0x3CE+1)
        + range(0x3D0, 0x3D6+1) + [0x3DA, 0x3DC, 0x3DE, 0x3E0]
        + range(0x3E2, 0x3F3+1) + range(0x401, 0x40C+1)
        + range(0x40E, 0x44F+1) + range(0x451, 0x45C+1)
        + range(0x45E, 0x481+1) + range(0x490, 0x4C4+1)
        + range(0x4C7, 0x4C8+1) + range(0x4CB, 0x4CC+1)
        + range(0x4D0, 0x4EB+1) + range(0x4EE, 0x4F5+1)
        + range(0x4F8, 0x4F9+1) + range(0x531, 0x556+1) + [0x559]
        + range(0x561, 0x586+1) + range(0x5D0, 0x5EA+1)
        + range(0x5F0, 0x5F2+1) + range(0x621, 0x63A+1)
        + range(0x641, 0x64A+1) + range(0x905, 0x939+1) + [0x93D]
        + range(0x9AA, 0x9B0+1) + [0x9B2]
        + range(0xA05, 0xA0A+1) + range(0xA35, 0xA36+1)
        + range(0xA8F, 0xA91+1) + [0xAE0]
        + range(0xB05, 0xB0C+1) + range(0xB36, 0xB39+1) + [0xB3D]
        + range(0xB5F, 0xB61+1) + range(0xB85, 0xB8A+1)
        + range(0xB8E, 0xB90+1) + range(0xB92, 0xB95+1)
        + range(0xB99, 0xB9A+1) + [0xB9C]
        + range(0xB9E, 0xB9F+1) + range(0xBA3, 0xBA4+1)
        + range(0xBA8, 0xBAA+1) + range(0xBAE, 0xBB5+1)
        + range(0xBB7, 0xBB9+1) + range(0xC05, 0xC0C+1)
        + range(0xC0E, 0xC10+1) + range(0x10A0, 0x10C5+1)
        + range(0x10D0, 0x10F6+1) + [0x1100]
        + range(0x1102, 0x1103+1) + range(0x1105, 0x1107+1) + [0x1109]
        + range(0x110B, 0x110C+1) + range(0x110E, 0x1112+1)
        + [0x113C, 0x113E, 0x1140, 0x114C, 0x114E, 0x1150]
        + range(0x1154, 0x1155+1) + [0x1159]
        + range(0x115F, 0x1161+1) + [0x1163, 0x1165, 0x1167, 0x1169]
        + range(0x116D, 0x116E+1) + range(0x1172, 0x1173+1)
        + [0x1175, 0x119E, 0x11A8, 0x11AB]
        + range(0x1F5F, 0x1F7D+1) + range(0x1F80, 0x1FB4+1)
        + range(0x1FB6, 0x1FBC+1) + [0x1FBE]
        + range(0x1FC2, 0x1FC4+1) + range(0x1FC6, 0x1FCC+1)
        + range(0x1FD0, 0x1FD3+1))

    COMBINING_CHARS = tuple(
        range(0x300, 0x345+1) + range(0x360, 0x361+1)
        + range(0x483, 0x486+1) + range(0x591, 0x5A1+1)
        + range(0x5A3, 0x5B9+1) + range(0x5BB, 0x5BD+1) + [0x5BF]
        + range(0x5C1, 0x5C2+1) + [0x5C4]
        + range(0x64B, 0x652+1) + [0x670]
        + range(0x6D6, 0x6DC+1) + range(0x6DD, 0x6DF+1)
        + range(0x6E0, 0x6E4+1) + range(0x6E7, 0x6E8+1)
        + range(0x6EA, 0x6ED+1) + range(0x901, 0x903+1) + [0x93C]
        + range(0x93E, 0x94C+1) + [0x94D]
        + range(0x951, 0x954+1) + range(0x962, 0x963+1)
        + range(0x981, 0x983+1) + [0x9BC, 0x9BE, 0x9BF]
        + range(0x9C0, 0x9C4+1) + range(0x9C7, 0x9C8+1)
        + range(0x9CB, 0x9CD+1) + [0x9D7]
        + range(0x9E2, 0x9E3+1) + [0xA02, 0xA3C, 0xA3E, 0xA3F]
        + range(0xA40, 0xA42+1) + range(0xA47, 0xA48+1)
        + range(0xA4B, 0xA4D+1) + range(0xA70, 0xA71+1)
        + range(0xA81, 0xA83+1) + [0xABC]
        + range(0xABE, 0xAC5+1) + range(0xAC7, 0xAC9+1)
        + range(0xACB, 0xACD+1) + range(0xB01, 0xB03+1) + [0xB3C]
        + range(0xB3E, 0xB43+1) + range(0xB47, 0xB48+1)
        + range(0xB4B, 0xB4D+1) + range(0xB56, 0xB57+1)
        + range(0xB82, 0xB83+1) + range(0xBBE, 0xBC2+1)
        + range(0xBC6, 0xBC8+1) + range(0xBCA, 0xBCD+1) + [0xBD7]
        + range(0xC01, 0xC03+1) + range(0xC3E, 0xC44+1)
        + range(0xC46, 0xC48+1) + range(0xC4A, 0xC4D+1)
        + range(0xC55, 0xC56+1) + range(0xC82, 0xC83+1)
        + range(0xCBE, 0xCC4+1) + range(0xCC6, 0xCC8+1)
        + range(0xCCA, 0xCCD+1) + range(0xCD5, 0xCD6+1)
        + range(0xD02, 0xD03+1) + range(0xD3E, 0xD43+1)
        + range(0xD46, 0xD48+1) + range(0xD4A, 0xD4D+1) + [0xD57, 0xE31]
        + range(0xE34, 0xE3A+1) + range(0xE47, 0xE4E+1) + [0xEB1]
        + range(0xEB4, 0xEB9+1) + range(0xEBB, 0xEBC+1)
        + range(0xEC8, 0xECD+1) + range(0xF18, 0xF19+1)
        + [0xF35, 0xF37, 0xF39, 0xF3E, 0xF3F]
        + range(0xF71, 0xF84+1) + range(0xF86, 0xF8B+1)
        + range(0xF90, 0xF95+1) + [0xF97]
        + range(0xF99, 0xFAD+1) + range(0xFB1, 0xFB7+1) + [0xFB9]
        + range(0x20D0, 0x20DC+1) + [0x20E1]
        + range(0x302A, 0x302F+1) + [0x3099, 0x309A])

    DIGIT_CHARS = tuple(
        range(0x30, 0x3A+1) + range(0x660, 0x669+1)
        + range(0x6F0, 0x6F9+1) + range(0x966, 0x96F+1)
        + range(0x9E6, 0x9EF+1) + range(0xA66, 0xA6F+1)
        + range(0xAE6, 0xAEF+1) + range(0xB66, 0xB6F+1)
        + range(0xBE7, 0xBEF+1) + range(0xC66, 0xC6F+1)
        + range(0xCE6, 0xCEF+1) + range(0xD66, 0xD6F+1)
        + range(0xE50, 0xE59+1) + range(0xED0, 0xED9+1)
        + range(0xF20, 0xF29+1))
    is_digit_char = _make_set_predicate(DIGIT_CHARS)

    EXTENDING_CHARS = tuple(
        [0xB7, 0x2D0, 0x2D1, 0x387, 0x640, 0xE46, 0xEC6, 0x3005]
        + range(0x3031, 0x3035+1) + range(0x309D, 0x309E+1)
        + range(0x30FC, 0x30FE+1))
    is_extending_char = _make_set_predicate(EXTENDING_CHARS)

    IDEOGRAPHIC_CHARS = tuple(
        range(0x4E00, 0x9FA5+1) + range(0x3021, 0x3029+1))
    is_ideographic_char = _make_set_predicate(IDEOGRAPHIC_CHARS)

    LETTER_CHARS = BASE_CHARS + IDEOGRAPHIC_CHARS
    is_letter_char = _make_set_predicate(LETTER_CHARS)

    NAME_CHARS = LETTER_CHARS + DIGIT_CHARS + (46, 45, 95, 58) \
                 + COMBINING_CHARS + EXTENDING_CHARS
    is_name_char = _make_set_predicate(NAME_CHARS)

    del _make_set_predicate

    def parse_Name(self, where):
        s, u = self.get_char_and_unicode()
        if not self.is_name_char(u):
            raise ParseError("illegal character in name: %s (%d)" % (`s`, u))
        i = 1
        while 1:
            c, u = self.get_char_and_unicode(i)
            if u not in self.NAME_CHARS:
                break
            i = i + 1
            s = s + c
        self.discard_chars(i)
        return s

    def parse_ExternalID(self):
        str = self.get_ascii(6)
        if str == "PUBLIC":
            # public system id w/ optional system id
            self.discard_chars(len(str))
            self.require_whitespace("ExternalID")
            id = self.get_quoted_string()
            if not id:
                raise ParseError("could not parse doctype declaration:"
                                 " bad public id")
            self.values.public_id = id
            self.require_whitespace("ExternalID")
            self.values.system_id = self.get_quoted_string()
        elif str == "SYSTEM":
            #  system id
            self.discard_chars(len(str))
            self.require_whitespace("ExternalID")
            id = self.get_quoted_string()
            if not id:
                raise ParseError("could not parse doctype declaration:"
                                 " bad system id")
            self.values.system_id = id
        else:
            raise ParseError("illegal external ID")

    def get_quoted_string(self):
        c, u = self.get_char_and_unicode()
        if u not in (34, 39):
            raise ParseError("illegal quoted string")
        self.discard_chars(1)
        quote_mark = u
        s = ''
        while 1:
            c, u = self.get_char_and_unicode()
            if not c:
                raise ParseError("could not find end of quoted string")
            self.discard_chars(1)
            if u == quote_mark:
                break
            s = s + c
        return s

    def skip_comment(self):
        self.require_ascii("<!--", "comment")
        self.skip_past_ascii("-->", "comment")

    def skip_pi(self):
        self.require_ascii("<?", "processing instruction")
        self.skip_past_ascii("?>", "processing instruction")

    def skip_to_doctype(self):
        # This should probably be implemented by any extractor for which we
        # care about performance.
        while 1:
            self.skip_whitespace()
            try:
                c = self.get_ascii(1)
            except ConversionError:
                self.discard_chars(1)
            else:
                if not c:
                    break
                if c == "<":
                    # might be something interesting
                    try:
                        prefix = self.get_ascii(4)
                    except ConversionError:
                        # If this fails, assume there's something non-white in
                        # there; allow the exception to be raised since there's
                        # probably illegal data before the document element.
                        prefix = self.get_ascii(2)
                    if prefix == "<!--":
                        self.skip_comment()
                    elif prefix[:2] == "<?":
                        self.skip_pi()
                    else:
                        break
                else:
                    # way bad!
                    raise ParseError("could not locate doctype declaration"
                                     " or start of document element")

    def skip_whitespace(self):
        """Trim leading whitespace, returning the number of characters
        stripped.

        The default implementation is slow; subclasses should override it.
        """
        count = 0
        try:
            while 1:
                c, u = self.get_char_and_unicode(count)
                if not c:
                    break
                if u not in (0x9, 0xA, 0xD, 0x20):
                    break
                count = count + 1
        except ConversionError:
            pass
        if count:
            self.discard_chars(count)
        return count

    def require_whitespace(self, where):
        """Trim leading whitespace, returning the number of characters
        stripped or raising ParseError is no whitespace was present."""
        numchars = self.skip_whitespace()
        if not numchars:
            raise ParseError("required whitespace in " + where)

    def get_ascii(self, count):
        raise NotImplementedError

    def get_char_and_unicode(self, index=0):
        raise NotImplementedError

    def require_ascii(self, str, where):
        width = len(str)
        data = self.get_ascii(width)
        if data != str:
            raise ParseError("required text '%s' missing in %s" % (str, where))
        self.discard_chars(width)

    def skip_past_ascii(self, str, what):
        width = len(str)
        initchar = str[0]
        subs = range(1, width)
        while 1:
            try:
                data = self.get_ascii(width)
            except ConversionError:
                self.discard_chars(1)
            else:
                if len(data) < width:
                    raise ParseError("could not locate end of " + what)
                if data == str:
                    self.discard_chars(width)
                    return
                for i in subs:
                    if data[i] == initchar:
                        self.discard_chars(i)
                else:
                    self.discard_chars(width)

    def discard_chars(self, count):
        raise NotImplementedError


class ISO8859Extractor(Extractor):
    __declattr_rx = re.compile(
        "([a-z]*)=\"((?:[^?\"]|\?[^?>\"]|\?(?=\?))*)\"", re.MULTILINE)

    __gi_rx = re.compile("[a-zA-Z_:][-a-zA-Z_:0-9.]*")
    __id_rx = re.compile(r"""(?:'[^']*'|\"[^\"]*\")""",
                         re.MULTILINE | re.VERBOSE)

    def yank_id(self):
        self.require_whitespace("doctype declaration: ExternalID")
        m = self.__id_rx.match(self.buffer)
        if not m:
            return None
        self.buffer = self.buffer[m.end():]
        return string.lstrip(m.group())[1:-1]

    def parse_doctype(self):
        self.require_ascii("<!DOCTYPE", "doctype declaration")
        self.require_whitespace("doctype declaration")
        m = self.__gi_rx.match(self.buffer)
        if not m:
            raise ParseError("could not parse doctype declaration: no name")
        self.values.doc_elem = m.group()
        self.discard_chars(len(self.values.doc_elem))
        whitechars = self.skip_whitespace()
        if not self.buffer:
            raise ParseError("could not parse doctype declaration:"
                             " insufficient data")
        if self.get_ascii(1) in ">[":
            # reached internal subset or end of declaration; we're done
            return
        if not whitechars:
            raise ParseError("whitespace required between document type and"
                             " document type declaration")
        self.parse_ExternalID()
    
    def skip_to_doctype(self):
        while self.buffer:
            self.buffer = string.lstrip(self.buffer)
            if self.buffer[:4] == "<!--":
                self.skip_comment()
            elif self.buffer[:2] == "<?":
                self.skip_pi()
            else:
                break

    def skip_pi(self):
        pos = string.find(self.buffer, "?>", 2)
        if pos < 0:
            raise ParseError("could not scan over processing instruction")
        self.buffer = self.buffer[pos + 2:]

    def skip_comment(self):
        pos = string.find(self.buffer, "-->", 4)
        if pos < 0:
            raise ParseError("could not scan over comment")
        self.buffer = self.buffer[pos + 4:]

    def skip_whitespace(self):
        old_buffer = self.buffer
        self.buffer = string.lstrip(old_buffer)
        return len(old_buffer) - len(self.buffer)

    def get_ascii(self, count):
        # not quite right, but good enough for now
        return self.buffer[:count]

    def get_char_and_unicode(self, index=0):
        # really only good for iso-8859-1
        c = self.buffer[index:index + 1]
        if c:
            return c, ord(c)
        else:
            return c, None

    def discard_chars(self, count):
        self.buffer = self.buffer[count:]

    def lower(self, str):
        return string.lower(str)


class ISO8859_1_Extractor(ISO8859Extractor):
    Encodings = ("iso-8859-1", "iso-latin-1", "latin-1")

    def get_ascii(self, count):
        return self.buffer[:count]

    def get_char_and_unicode(self, index=0):
        c = self.buffer[index:index + 1]
        if c:
            return c, ord(c)
        else:
            return c, None

add_extractor_class(ISO8859_1_Extractor)


for c in "23456789":
    class _Extractor(ISO8859Extractor):
        Encodings = ("iso-8859-" + c,)
    try:
        _Extractor.__name__ = "ISO8859_%s_Extractor" % c
    except TypeError:
        # older Python versions wouldn't allow __name__ to be set on a class
        pass
    exec "ISO8859_%s_Extractor = _Extractor" % c
    add_extractor_class(_Extractor)
del _Extractor


class UTF8Extractor(ISO8859Extractor):
    Encodings = ("utf-8",)

    def get_char_and_unicode(self, index=0):
        raise NotImplementedError

add_extractor_class(UTF8Extractor)


class EBCDICExtractor(Extractor):
    Encodings = ("ebcdic",)

    # This table was taken from the source code of GNU recode 3.4.
    __ASCII_TO_EBCDIC = [
          0,   1,   2,   3,  55,  45,  46,  47,   #   0 -   7
         22,   5,  37,  11,  12,  13,  14,  15,   #   8 -  15
         16,  17,  18,  19,  60,  61,  50,  38,   #  16 -  23
         24,  25,  63,  39,  28,  29,  30,  31,   #  24 -  31
         64,  79, 127, 123,  91, 108,  80, 125,   #  32 -  39
         77,  93,  92,  78, 107,  96,  75,  97,   #  40 -  47
        240, 241, 242, 243, 244, 245, 246, 247,   #  48 -  55
        248, 249, 122,  94,  76, 126, 110, 111,   #  56 -  63
        124, 193, 194, 195, 196, 197, 198, 199,   #  64 -  71
        200, 201, 209, 210, 211, 212, 213, 214,   #  72 -  79
        215, 216, 217, 226, 227, 228, 229, 230,   #  80 -  87
        231, 232, 233,  74, 224,  90,  95, 109,   #  88 -  95
        121, 129, 130, 131, 132, 133, 134, 135,   #  96 - 103
        136, 137, 145, 146, 147, 148, 149, 150,   # 104 - 111
        151, 152, 153, 162, 163, 164, 165, 166,   # 112 - 119
        167, 168, 169, 192, 106, 208, 161,   7,   # 120 - 127
         32,  33,  34,  35,  36,  21,   6,  23,   # 128 - 135
         40,  41,  42,  43,  44,   9,  10,  27,   # 136 - 143
         48,  49,  26,  51,  52,  53,  54,   8,   # 144 - 151
         56,  57,  58,  59,   4,  20,  62, 225,   # 152 - 159
         65,  66,  67,  68,  69,  70,  71,  72,   # 160 - 167
         73,  81,  82,  83,  84,  85,  86,  87,   # 168 - 175
         88,  89,  98,  99, 100, 101, 102, 103,   # 176 - 183
        104, 105, 112, 113, 114, 115, 116, 117,   # 184 - 191
        118, 119, 120, 128, 138, 139, 140, 141,   # 192 - 199
        142, 143, 144, 154, 155, 156, 157, 158,   # 200 - 207
        159, 160, 170, 171, 172, 173, 174, 175,   # 208 - 215
        176, 177, 178, 179, 180, 181, 182, 183,   # 216 - 223
        184, 185, 186, 187, 188, 189, 190, 191,   # 224 - 231
        202, 203, 204, 205, 206, 207, 218, 219,   # 232 - 239
        220, 221, 222, 223, 234, 235, 236, 237,   # 240 - 247
        238, 239, 250, 251, 252, 253, 254, 255,   # 248 - 255
        ]

    _m = [None] * 256
    for _i in range(len(__ASCII_TO_EBCDIC)):
        _e = __ASCII_TO_EBCDIC[_i]
        __ASCII_TO_EBCDIC[_i] = chr(_e)
        _m[_e] = chr(_i)
    for i in range(len(_m)):
        if _m[_i] is None:
            print "No EBCDIC character for ASCII", `chr(i)`

    __EBCDIC_TO_ASCII = tuple(_m)

    __translation = string.maketrans(string.join(__ASCII_TO_EBCDIC, ''),
                                     string.join(__EBCDIC_TO_ASCII, ''))

    def get_ascii(self, count):
        buffer = self.buffer[:count]
        return string.translate(buffer, self.__translation)

add_extractor_class(EBCDICExtractor)


def ascii_to_ucs2be(s):
    L = map(None, s)
    L.insert(0, '')
    return string.join(L, '\0')


def ascii_to_ucs2le(s):
    L = map(None, s)
    L.append('')
    return string.join(L, '\0')


def ascii_to_ucs4be(s):
    L = map(None, s)
    L.insert(0, '')
    return string.join(L, '\0\0\0')


def ascii_to_ucs4le(s):
    L = map(None, s)
    L.append('')
    return string.join(L, '\0\0\0')


class UCS2Extractor(Extractor):
    Encodings = ("ucs-2", "utf-16", "iso-10646-ucs-2")

    __WHITESPACE_BE = map(ascii_to_ucs2be, string.whitespace)
    __WHITESPACE_LE = map(ascii_to_ucs2le, string.whitespace)

    def __init__(self, buffer, values):
        Extractor.__init__(self, buffer, values)
        if values.byte_order not in (BIG_ENDIAN, LITTLE_ENDIAN):
            raise ValueError, \
                  "UCS-2 encoded strings must have determinable byte order"
        self.__byte_order = values.byte_order
        if values.byte_order == BIG_ENDIAN:
            self.__whitespace = self.__WHITESPACE_BE
            self.__from_ascii = ascii_to_ucs2be
        else:
            self.__whitespace = self.__WHITESPACE_LE
            self.__from_ascii = ascii_to_ucs2le

    def skip_whitespace(self):
        buffer = self.buffer
        pos = 0
        whitespace = self.__whitespace
        while buffer[pos:pos+2] in whitespace:
            pos = pos + 2
        self.buffer = buffer[pos:]
        return pos / 2

    def get_ascii(self, count):
        data = self.buffer[:count*2]
        if self.__byte_order == BIG_ENDIAN:
            zero_offset = 0
            char_offset = 1
        else:
            zero_offset = 1
            char_offset = 0
        s = ''
        try:
            for i in range(0, count*2, 2):
                if data[i+zero_offset] != '\0':
                    raise ConversionError("cannot convert %s to ASCII"
                                          % `data[i:i+2]`)
                s = s + data[i+char_offset]
        except IndexError:
            # just didn't have enough; somebody else's problem
            pass
        return s

    def get_char_and_unicode(self, index=0):
        if len(self.buffer) >= 2:
            offset = index * 2
            c = self.buffer[offset:offset + 2]
            return c, ordwc(c, self.__byte_order)
        else:
            return None, None

    def discard_chars(self, count):
        self.buffer = self.buffer[count*2:]

add_extractor_class(UCS2Extractor)


def ordwc(wc, byte_order=None):
    """Return the ord() for a wide character."""
    if byte_order is None:
        byte_order = NATIVE_ENDIANNESS
    width = len(wc)
    if width == 2:
        o1, o2 = map(ord, wc)
        if byte_order == BIG_ENDIAN:
            o = (o1 << 8) | o2
        else:
            o = (o2 << 8) | o1
    elif width == 4:
        o1, o2, o3, o4 = map(ord, wc)
        if byte_order == BIG_ENDIAN:
            o = (((((o1 << 8) | o2) << 8) | o3) << 8) | o4
        else:
            o = (((((o4 << 8) | o3) << 8) | o2) << 8) | o1
    else:
        raise ValueError, "wide-character string has bad length"
    return o


def ordwstr(wstr, byte_order=None, charsize=2):
    assert charsize in (2, 4), "wide character size must be 2 or 4"
    ords = []
    for i in range(0, len(wstr), charsize):
        ords.append(ordwc(wstr[i:i+charsize], byte_order))
    return ords


def dump_info(values, labels=None):
    if labels is None:
        labels = FieldLabels
    format = "%%%ds: %%s" % max(map(len, FieldLabels.__dict__.values()))
    for field_name in FieldNames:
        value = getattr(values, field_name)
        label = getattr(FieldLabels, field_name)
        if value is not None:
            print format % (label, value)


def main():
    import getopt
    #
    reqs = Record()                     # required values (for output)
    #
    get_defaults = 1
    full_report = 0
    debugging = 0
    program = os.path.basename(sys.argv[0])
    opts, args = getopt.getopt(sys.argv[1:], "ad",
                               ["all", "docelem", "encoding", "public-id",
                                "standalone", "system-id", "version"])
    if opts:
        get_defaults = 0
    for opt, arg in opts:
        if opt in ("-a", "--all"):
            full_report = 1
        elif opt == "-d":
            debugging = debugging + 1
        elif opt == "--docelem":
            reqs.doc_elem = 1
        elif opt == "--encoding":
            reqs.encoding = 1
        elif opt == "--public-id":
            reqs.publib_id = 1
        elif opt == "--standalone":
            reqs.standalone = 1
        elif opt == "--system-id":
            reqs.system_id = 1
        elif opt == "--version":
            reqs.xml_version = 1
    if get_defaults:
        full_report = 1
    #
    if len(args) > 1:
        sys.stderr.write(program + ": too many input sources specified")
        sys.exit(2)
    if args:
        if os.path.exists(args[0]):
            fp = open(args[0])
        else:
            import urllib
            fp = urllib.urlopen(args[0])
    else:
        fp = sys.stdin
    #
    buffer = fp.read(10240)
    fp.close()
    try:
        values = get_xml_info(buffer)
    except Error, e:
        sys.stderr.write("parse failed: %s\n" % e.args[0])
        if debugging:
            raise
        sys.exit(1)
    #
    # Make the report:
    #
    if full_report:
        dump_info(values)
    else:
        for field_name in FieldNames:
            if getattr(reqs, field_name):
                value = getattr(values, field_name)
                if value is None:
                    print
                else:
                    print value


if __name__ == "__main__":
    main()
