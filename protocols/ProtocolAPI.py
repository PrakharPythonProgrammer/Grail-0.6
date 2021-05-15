"""Protocol API -- with proxy support.

Proxy support is controlled by a set of environment variables: for
each protocol, there's

        <scheme>_proxy=<url>

e.g.

        ftp_proxy=http://proxysvr.local.com:8080

The protocol API module that is used to communicate to the proxy
server (in the example, module httpAPI) must accept a url parameter
that is a tuple of the form (hostport, selector) where hostport is the
host and port of the proxy server (in the example,
"proxysvr.local.com:8080") and selector is the full URL to be sent to
the proxy.  Currently, only the httpAPI module supports this.  (With
non-proxy usage, the url parameter is a string.)

"""

import regsub
import string
import socket
from urllib import splittype, splithost, splitport
import grailutil

#
# list of valid scheme environment variables for proxies
VALID_PROXIES = ('http_proxy', 'ftp_proxy')

def protocol_joiner(scheme):
    scheme = string.lower(scheme)
    sanitized = regsub.gsub("[^a-zA-Z0-9]", "_", scheme)
    modname = sanitized + "API"
    app = grailutil.get_grailapp()
    m = app.find_extension('protocols', modname)
    if m:
        return m.join
    return None

def protocol_access(url, mode, params, data=None):
    scheme, resturl = splittype(url)
    if not scheme:
        raise IOError, ("protocol error", "no scheme identifier in URL", url)
    scheme = string.lower(scheme)
    sanitized = regsub.gsub("[^a-zA-Z0-9]", "_", scheme)
    #
    # Check first to see if proxies are enabled
    manual_proxy_enabled = grailutil.pref_or_getenv('manual_proxy_enabled',
                                                    type_name='int')

    app = grailutil.get_grailapp()
    if manual_proxy_enabled:
        proxy_name = sanitized + "_proxy"
        if manual_proxy_enabled == -1:
            #
            # We should only get here when there are no user preferences
            # for proxies, which should only happen once... so check the
            # environment for the rest of the known scheme proxy env vars
            # and load them into prefs if they exist.
            app.prefs.Set('proxies', 'manual_proxy_enabled', 0)
            proxy = None
            for next_proxy_name in VALID_PROXIES:
                next_proxy = grailutil.pref_or_getenv(next_proxy_name,
                                              check_ok=VALID_PROXIES)
                if next_proxy:
                    app.prefs.Set('proxies', 'manual_proxy_enabled', 1)
                    
                if next_proxy_name == proxy_name:
                    proxy = next_proxy
                    
            no_proxy_enabled = grailutil.pref_or_getenv('no_proxy_enabled',
                                                        type_name='int')
            if no_proxy_enabled == -1:
                no_proxy = grailutil.pref_or_getenv('no_proxy')
            if no_proxy:
                app.prefs.Set('proxies', 'no_proxy_enabled', 1)
            else:
                app.prefs.Set('proxies', 'no_proxy_enabled', 0)
        else:   
            proxy = grailutil.pref_or_getenv(proxy_name,
                                             check_ok=VALID_PROXIES)
    else:
        proxy = None
        
    if proxy:
        if not valid_proxy(proxy):
            error = 'Invalid proxy: ' + proxy
            raise IOError, error
        no_proxy_enabled = grailutil.pref_or_getenv('no_proxy_enabled',
                                                    type_name='int')
        if no_proxy_enabled:
            no_proxy = grailutil.pref_or_getenv('no_proxy')
        else:
            no_proxy = None
            
        do_proxy = 1
        if no_proxy:
            list = map(string.strip, string.split(no_proxy, ","))
            url_host, url_remains = splithost(resturl)
            url_host = string.lower(url_host or '')
            if proxy_exception(url_host, list):
                do_proxy = 0
            else:
                url_host, url_port = splitport(url_host)
                if proxy_exception(url_host, list):
                    do_proxy = 0
        if do_proxy:
            proxy_scheme, proxy_resturl = splittype(proxy)
            proxy_host, proxy_remains = splithost(proxy_resturl)
            resturl = (proxy_host, url)
            scheme = string.lower(proxy_scheme)
            sanitized = regsub.gsub("[^a-zA-Z0-9]", "_", scheme)
##          print "Sending", url
##          print "     to", scheme, "proxy", proxy_host
    modname = sanitized + "API"
    app = grailutil.get_grailapp()
    access = app.find_extension('protocols', sanitized).access
    if not access:
        raise IOError, ("protocol error", "no class for %s" % scheme)
    try:
        if data:
            return access(resturl, mode, params, data)
        else:
            return access(resturl, mode, params)
    except socket.error, msg:
        raise IOError, ("socket error", msg)


import grailbase.extloader

class ProtocolLoader(grailbase.extloader.ExtensionLoader):
    class ProtocolInfo:
        def __init__(self, scheme, access, join):
            self.scheme = scheme
            self.access = access
            self.join = join

    def find(self, name):
        ext = None
        mod = self.find_module(name + "API")
        if mod:
            classname = name + "_access"
            joinername = name + "_join"
            if hasattr(mod, classname):
                access = getattr(mod, classname)
            else:
                access = None
            if hasattr(mod, joinername):
                join = getattr(mod, joinername)
            else:
                import urlparse
                join = urlparse.urljoin
            ext = self.ProtocolInfo(name, access, join)
        return ext


def test(url = "http://www.python.org/"):
    import sys
    if sys.argv[1:]: url = sys.argv[1]
    api = protocol_access(url, 'GET', {})
    while 1:
        message, ready = api.pollmeta()
        print message
        if ready:
            meta = api.getmeta()
            print `meta`
            break
    while 1:
        message, ready = api.polldata()
        print message
        if ready:
            data = api.getdata(512)
            print `data`
            if not data:
                break
    api.close()

def proxy_exception(host, list):
    """Return 1 if host is contained in list or host's suffix matches
    an entry in list that begins with a leading dot."""
    for exception in list:
        if host == exception:
            return 1
        try:
            if exception[0] == '.' and host[-len(exception):] == exception:
                return 1
        except IndexError:
            pass
    return 0

def valid_proxy(proxy):
    """Return 1 if the proxy string looks like a valid url, for an
    proxy URL else return 0."""
    import urlparse
    scheme, netloc, url, params, query, fragment = urlparse.urlparse(proxy)
    if scheme != 'http' or params or query or fragment:
        return 0
    return 1
    
if __name__ == '__main__':
    test()
