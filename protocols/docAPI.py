"""doc: URI scheme handler."""

from nullAPI import null_access

class doc_access(null_access):

    def __init__(self, url, method, params):
        null_access.__init__(self, url, method, params)
        if url[:1] != '/': url = '/' + url
        self.url = "http://monty.cnri.reston.va.us/grail-0.3" + url

    def getmeta(self):
        null_access.getmeta(self)       # assert, state change
        return 301, "Redirected", {'location': self.url}
