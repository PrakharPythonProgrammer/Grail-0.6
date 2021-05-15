"""Discard the urn: prefix.  This is sufficient since there are no overlaps
between URN and URL spaces.  It also ensures that urn:xxx:yyy is bookmarked
as xxx:yyy, so the equivalence is evident."""

__version__ = '$Revision: 2.3 $'


import nullAPI
import ProtocolAPI


class urn_access(nullAPI.null_access):
    def __init__(self, resturl, method, params):
        self.__resturl = resturl
        nullAPI.null_access.__init__(self, resturl, method, params)

    def getmeta(self):
        nullAPI.null_access.getmeta(self)
        return 301, "urn: prefix not required", {"location": self.__resturl}
