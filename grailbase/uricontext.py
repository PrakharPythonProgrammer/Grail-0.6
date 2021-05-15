"""URI resolution context.

The use of 'url' in the method names is a historical accident.

"""
__version__ = '$Revision: 1.5 $'

import urlparse
__default_joiner = urlparse.urljoin
del urlparse

import re
__typematch = re.compile('^([^/:]+):').match
del re

def __splittype(url):
    match = __typematch(url)
    if match:
        return match.group(1)


def _urljoin(a, b):
    sa = __splittype(a)
    sb = __splittype(b)
    if sa and (sa == sb or not sb):
        import protocols
        joiner = protocols.protocol_joiner(sa)
        if joiner: return joiner(a, b)
    return __default_joiner(a, b)


class URIContext:
    """URI resolution context."""

    def __init__(self, url="", baseurl=""):
        self.__url = url or ""
        baseurl = baseurl or ""
        if url and baseurl:
            self.__baseurl = _urljoin(url, baseurl)
        else:
            self.__baseurl = baseurl

    def get_url(self):
        return self.__url

    def set_url(self, url, baseurl=None):
        """Set source URI and base URI for the current resource.

        The loaded URI is what this page was loaded from; the base URI
        is used to calculate relative links, and defaults to the
        loaded URI.

        """
        self.__url = url
        if baseurl:
            self.__baseurl = _urljoin(url, baseurl)
        else:
            self.__baseurl = url

    def get_baseurl(self, *relurls):
        """Return the base URI for the current page, joined with relative URIs.

        Without arguments, return the base URI.
        
        With arguments, return the base URI joined with all of the
        arguments.  Empty arguments don't contribute.

        """
        
        url = self.__baseurl or self.__url
        for rel in relurls:
            if rel:
                url = _urljoin(url, rel)
        return url

    def set_baseurl(self, baseurl):
        """Set the base URI for the current page.

        The base URI is taken relative to the existing base URI.

        """
        if baseurl:
            self.__baseurl = _urljoin(self.__baseurl or self.__url, baseurl)
        else:
            self.__baseurl = self.__baseurl or self.__url
