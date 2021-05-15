"""grail: URI scheme handler."""

import grailutil
import urllib
from nullAPI import null_access

class grail_access(null_access):

    def __init__(self, url, method, params):
        null_access.__init__(self, url, method, params)
        file = grailutil.which(url)
        if not file: raise IOError, "Grail file %s not found" % `url`
        self.url = "file:" + urllib.pathname2url(file)

    def getmeta(self):
        null_access.getmeta(self)       # assert, state change
        return 301, "Redirected", {'location': self.url}
