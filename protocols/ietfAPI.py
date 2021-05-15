"""Handler for ietf: URNs.  These are defined in the Internet draft
draft-ietf-urn-ietf-07.txt (work in progress).
"""
__version__ = '$Revision: 2.5 $'

import grailutil
import nullAPI
import os
import ProtocolAPI
import string


PREF_GROUP = "ietf-resolver"


def ietf_access(resturl, method, params):
    urn = convert_to_url(resturl)
    return ProtocolAPI.protocol_access(urn, "GET", {})


def convert_to_url(urn):
    prefs = grailutil.get_grailapp().prefs
    urn = string.lower(urn)
    m = _reference_rx.match(urn)
    if m:
        type, number = m.group(1, 2)
        vars = {"type": type, "number": int(number)}
        which = "document-template"
    else:
        m = _draft_rx.match(urn)
        if m:
            draft = m.group(1)
            draft, format = os.path.splitext(draft)
            if format and format[0] == ".":
                format = format[1:]
            format = format or "txt"
            which = "internet-draft-template"
            vars = {"draft": draft, "format": format}
        else:
            m = _meeting_rx.match(urn)
            if not m:
                raise ValueError, "not a valid ietf URN"
            wgbofname = m.group(2)
            try:
                date = _number_to_date[int(m.group(1))]
            except KeyError:
                raise ValueError, "unknown IETF meeting number: " + m.group(1)
            which = "meeting-template"
            vars = {"date": date, "wg": wgbofname}
    return prefs.Get(PREF_GROUP, which) % vars


# support data for convert_to_url()
#
import re
_reference_rx = re.compile("([^:]+):(\d+)$")
_draft_rx = re.compile("id:(.+)$")
_meeting_rx = re.compile("mtg-(\d+)-(.*)$")
del re

_number_to_date = {
    # this is based on the list of confirmed meeting dates;
    # we need a way to discover when meetings occurred if not in the table
    43: "98dec", 42: "98aug", 41: "98apr",
    40: "97dec", 39: "97aug", 38: "97apr",
    37: "96dec", 36: "96jun", 35: "96mar",
    34: "95dec", 33: "95jul", 32: "95apr",
    31: "94dec", 30: "94jul", 29: "94mar",
    28: "93nov", 27: "93jul", 26: "93mar",
    25: "92nov", 24: "92jul", 23: "92mar",
    22: "91nov", 21: "91jul", 20: "91mar",
    19: "90dec", 18: "90jul", 17: "90may", 16: "90feb",
    15: "89oct", 14: "89jul", 13: "89apr", 12: "89jan",
    11: "88oct", 10: "88jun",  9: "88mar",
     8: "87nov",  7: "87jul",  6: "87apr",  5: "87feb",
     4: "86oct",  3: "86jul",  2: "86apr",  1: "86jan"
    }
