"""Simple parser that handles only what's allowed in attribute values."""
__version__ = '$Revision: 1.12 $'

import re

from .SGMLLexer import *
import string

_entref_exp = re.compile("&\(\(#\|\)[a-zA-Z0-9][-.a-zA-Z0-9]*\)\(;\|\)")

_named_chars = {'#re' : '\r',
                '#rs' : '\n',
                '#space' : ' '}

for i in range(256):
    _named_chars["#" + repr(i)] = chr(i)

#  build a table suitable for string.translate()
_chartable = map(chr, range(256))
for i in range(256):
    if chr(i) in string.whitespace:
        _chartable[i] = " "
_chartable = str.join(_chartable, '')


def replace(data, entities = None):
    """Perform general entity replacement on a string.
    """
    data = str.translate(data, _chartable)
    if '&' in data and entities:
        value = None
        pos = _entref_exp.search(data)
        while pos >= 0 and pos + 1 < len(data):
            ref, term = _entref_exp.group(1, 3)
            if entities.has_key(ref):
                value = entities[ref]
            elif _named_chars.has_key(str.lower(ref)):
                value = _named_chars[str.lower(ref)]
            if value is not None:
                data = data[:pos] + value + data[pos+len(ref)+len(term)+1:]
                pos = pos + len(value)
                value = None
            else:
                pos = pos + len(ref) + len(term) + 1
            pos = _entref_exp.search(data, pos)
    return data
