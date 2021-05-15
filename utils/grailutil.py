"""Miscellaneous utilities for Grail."""

__version__ = "$Revision: 2.31 $"

import os

# Utility functions for handling attribute values used to be defined here;
# now get them from sgml.utils since Grail expects them to be here.  One is
# in the printing package.

from grailbase.utils import *
from sgml.utils import *
from printing.utils import conv_fontsize


# This is here for compatibility with pre-1.5.2 Python versions.
try:
    abspath = os.path.abspath
except AttributeError:
    # Copied from posixpath in Python 1.5.2.
    def abspath(path):
        if not os.path.isabs(path):
            path = join(os.getcwd(), path)
        return os.path.normpath(path)


def complete_url(url):
    import urlparse
    scheme, netloc = urlparse.urlparse(url)[:2]
    if not scheme:
        if not netloc:
            # XXX url2pathname/pathname2url???
            if os.path.exists(url):
                import urllib
                url = "file:" + urllib.quote(url)
            else:
                url = "http://" + url
        else:
            url = "http:" + url
    return url


def nicebytes(n):
    """Convert a bytecount to a string like '<number> bytes' or '<number>K'.

    This is intended for inclusion in status messages that display
    things like '<number>% read of <bytecount>' or '<bytecount> read'.
    When the byte count is large, it will be expressed as a small
    floating point number followed by K, M or G, e.g. '3.14K'.

    The word 'bytes' (or singular 'byte') is part of the returned
    string if the byte count is small; when the count is expressed in
    K, M or G, 'bytes' is implied.

    """
    if n < 1000:
        if n == 1: return "1 byte"
        return "%d bytes" % n
    n = n * 0.001
    if n < 1000.0:
        suffix = "K"
    else:
        n = n * 0.001
        if n < 1000.0:
            suffix = "M"
        else:
            n = n * 0.001
            suffix = "G"
    if n < 10.0: r = 2
    elif n < 100.0: r = 1
    else: r = 0
    return "%.*f" % (r, n) + suffix




def pref_or_getenv(name, group='proxies', type_name='string',
                   check_ok=None, user=0, factory=0):
    """Help for integrating environment variables with preferences.

    First check preferences, under 'group', for the component 'name'.
    If 'name' is defined as a 'string' and it's NULL, try to read
    'name' from the environment.  If 'name's defined in the
    environment, migrate the value to preferences.  Return the value
    associated with the name, None if it's not defined in either place
    (env or prefs... and it's a 'string').  If check_ok is not None,
    it is expected to be a tuple of valid names. e.g. ('name1',
    'name2').  If factory is TRUE then the value for name is retrieved
    only from factory defaults and not user preferences and not the
    environment. If it's not found there, return None.

    """
    if check_ok and  name not in check_ok:
            return None

    app = get_grailapp()

    if type_name == 'string':
        component = app.prefs.Get(group, name, factory=factory)
        if len(component) or factory:
            return component
    elif type_name == 'int':
        component = app.prefs.GetInt(group, name, factory=factory)
        return component
    elif type_name == 'Boolean':
        component = app.prefs.GetBoolean(group, name, factory=factory)
        return component
    elif type_name == 'float':
        component = app.prefs.GetFloat(group, name, factory=factory)
        return component
    else:
        raise ValueError, ('%s not supported - must be one of %s'
                      % (`type_name`, ['string', 'int', 'float', 'Boolean']))

    import os
    try:
        component = os.environ[name]
    except:
        return None

    app.prefs.Set(group, name, component)
    return component

