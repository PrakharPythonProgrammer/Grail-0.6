"""CNRI handle protocol extension.

This module glues the backend CNRI handle client resolution module in
hdllib.py to the Grail URI protocol API.  Currently we are only
interested in URL type handles, so we can get away semantically with
returning an HTTP-style relocation error to the browser for the
resolved handle (if the handle resolves to a single URL), or to
generating a piece of HTML which lets the user choose one (if it
resolves to multiple URLs).

XXX Remaining problems:

           Issuing a 302 relocate isn't the proper thing to do in the
           long term, because it forces the user back into URL space.
           So, for example, the user will naturally keep the resolved
           URL on her bookmarks, instead of the original handle.
           However, for backward compatibility with relative links, we
           need to define relative-handle semantics.  We're working
           with the CNRI handle group to define this and we'll be
           experimenting with solutions in the future.  This should be
           good enough for now.

           Handle resolution is done synchronously, thereby defeating
           the intended asynchronous API.  This should be fixed by
           adding an asynchronous interface to hdllib.py.

"""

import sys
import string
import urllib
import hdllib
import nullAPI
import grailutil


# We are currently only concerned with URL type handles.
HANDLE_TYPES = [hdllib.HDL_TYPE_URL]


# HTML boilerplate for response on handle with multiple URLs
HTML_HEADER = """<HTML>

<HEAD>
<TITLE>%(title)s</TITLE>
</HEAD>

<BODY>

<H1>%(title)s</H1>

%(error)s

The handle you have selected resolves to multiple data items or to an
unknown data type.<P>

Please select one from the following list:

<UL>
"""

HTML_TRAILER = """
</UL>

</BODY>

</HTML>
"""



def parse_handle(hdl):
    """Parse off options from handle.

    E.g. 'auth.subauth/path;type=url' will return
    ('auth.subauth.path', {'type': 'url'}).

    This also interprets % quoting in the non-option part.

    """
    hdl, attrs = urllib.splitattr(hdl)
    d = {}
    if attrs:
        for attr in attrs:
            i = string.find(attr, '=')
            if i < 0:
                key, value = attr, None
            else:
                key, value = attr[:i], urllib.unquote(attr[i+1:])
            d[string.lower(key)] = value
    return urllib.unquote(hdl), d

def escape(s):
    """Replace special characters '&', '<' and '>' by SGML entities."""
    # From cgi.py
    import regsub
    s = regsub.gsub("&", "&amp;", s)    # Must be done first!
    s = regsub.gsub("<", "&lt;", s)
    s = regsub.gsub(">", "&gt;", s)
    return s

class hdl_access(nullAPI.null_access):

    _types = HANDLE_TYPES

    try:
        #print "Fetching global hash table"
        _global_hashtable = hdllib.fetch_global_hash_table()
    except hdllib.Error, inst:
        raise IOError, inst, sys.exc_traceback

    _hashtable = _global_hashtable

    _local_hashtables = {}

    def get_local_hash_table(self, hdl):
        key = hdllib.get_authority(hdl)
        if not self._local_hashtables.has_key(key):
            #print "Fetching local hash table for", key
            self._local_hashtables[key] = hdllib.fetch_local_hash_table(
                key, self._global_hashtable)
        return self._local_hashtables[key]

    def __init__(self, hdl, method, params):
        self._msgattrs = {"title": "Ambiguous handle resolution",
                          "error": ""}
        nullAPI.null_access.__init__(self, hdl, method, params)

        self._hdl, self._attrs = parse_handle(hdl)
        self.app = grailutil.get_grailapp()

        if self._attrs.has_key('type'):
            t = string.lower(self._attrs['type'])
            mname = "hdl_type_" + t
            tname = string.upper(mname)
            try:
                m = self.app.get_loader('protocols').find_module(mname)
                if not m:
                    self._msgattrs["title"] = (
                        "hdlAPI: Could not load %s data type handler" % mname)
                    self._msgattrs["error"] = sys.exc_value + "<p>"
                    raise ImportError, mname
                types = m.handle_types
                formatter = m.data_formatter
            except (ImportError, AttributeError), msg:
                if hdllib.data_map.has_key(tname):
                    self._types = [hdllib.data_map[tname]]
                else:
                    try:
                        n = string.atoi(t)
                    except ValueError:
                        self._types = [] # Request all types
                    else:
                        self._types = [n]
            else:
                self._types = types
                if formatter:
                    self._formatter = formatter

        if self._attrs.has_key('server'):
            self._hashtable = hdllib.HashTable(server=self._attrs['server'])

    def pollmeta(self):
        nullAPI.null_access.pollmeta(self)
        try:
            replyflags, self._items = self._hashtable.get_data(
                self._hdl, self._types)
        except hdllib.Error, inst:
            if inst.err == hdllib.HP_HANDLE_NOT_FOUND:
                #print "Retry using a local handle server"
                try:
                    self._hashtable = self.get_local_hash_table(
                        self._hdl)
                    replyflags, self._items = self._hashtable.get_data(
                        self._hdl, self._types)
                except hdllib.Error, inst:
                    # (Same comment as below)
                    raise IOError, inst, sys.exc_traceback
                else:
                    return 'Ready', 1
            # Catch all errors and raise an IOError.  The Grail
            # protocol extension defines this as the only error we're
            # allowed to raise.
            # Because the hdllib.Error instance is passed, no
            # information is lost.
            raise IOError, inst, sys.exc_traceback
        else:
            return 'Ready', 1

    def getmeta(self):
        nullAPI.null_access.getmeta(self)
        self._data = ""
        self._pos = 0
        return self._formatter(self)

    def formatter(self, alterego=None):
        if len(self._items) == 1 and self._items[0][0] == hdllib.HDL_TYPE_URL:
            return 302, 'Moved', {'location': self._items[0][1]}
        if len(self._items) == 0:
            self._data = "Handle not resolved to anything\n"
            return 404, 'Handle not resolved to anything', {}
        data = HTML_HEADER % self._msgattrs
        for type, uri in self._items:
            if type == hdllib.HDL_TYPE_URL:
                uri = escape(uri)
                text = '<LI><A HREF="%s">%s</A>\n' % (uri, uri)
            else:
                if type in (hdllib.HDL_TYPE_SERVICE_POINTER,
                            hdllib.HDL_TYPE_SERVICE_HANDLE):
                    uri = hdllib.hexstr(uri)
                else:
                    uri = escape(`uri`)
                if hdllib.data_map.has_key(type):
                    type = hdllib.data_map[type][9:]
                else:
                    type = str(type)
                text = '<LI>type=%s, value=%s\n' % (type, uri)
            data = data + text
        data = data + HTML_TRAILER
        self._data = data
        return 200, 'OK', {'content-type': 'text/html'}

    _formatter = formatter

    # polldata() is inherited from nullAPI

    def getdata(self, maxbytes):
        end = self._pos + maxbytes
        data = self._data[self._pos:end]
        if not data:
            return nullAPI.null_access.getdata(self, maxbytes)
        self._pos = end
        return data


# Here are some test handles:
#
# hdl:CNRI/19970131120001
# hdl:nlm.hdl_test/96053804
# hdl:cnri.dlib/december95
# hdl:cnri.dlib/november95
# hdl:nonreg.guido/python-home-page
# hdl:nonreg.guido/python-ftp-dir
