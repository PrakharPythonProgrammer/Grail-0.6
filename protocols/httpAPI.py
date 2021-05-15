"""Provisional HTTP interface using the new protocol API.

XXX This was hacked together in an hour si I would have something to
test ProtocolAPI.py.  Especially the way it uses knowledge about the
internals of httplib.HTTP is disgusting (but then, so would editing
the source of httplib.py be :-).

XXX Main deficiencies:

- poll*() always returns ready
- should read the headers more carefully (no blocking)
- (could even *write* the headers more carefully)
- should poll the connection making part too

"""


import string
import httplib
from urllib import splithost
import mimetools
from Assert import Assert
import grailutil
import select
import Reader
import regex
import StringIO
import socket
import sys
from __main__ import GRAILVERSION


httplib.HTTP_VERSIONS_ACCEPTED = 'HTTP/1\.[0-9.]+'
replypat = httplib.HTTP_VERSIONS_ACCEPTED + '[ \t]+\([0-9][0-9][0-9]\)\(.*\)'
replyprog = regex.compile(replypat)

httplib.replypat = replypat
httplib.replyprog = replyprog


# Search for blank line following HTTP headers
endofheaders = regex.compile("\n[ \t]*\r?\n")


# Stages
# there are now five stages
WAIT = 'wait'  # waiting for a socket
META = 'meta'
DATA = 'data'
DONE = 'done'
CLOS = 'closed'

class MyHTTP(httplib.HTTP):

    def putrequest(self, request, selector):
        self.selector = selector
        httplib.HTTP.putrequest(self, request, selector)

    def getreply(self, file):
        self.file = file
        line = self.file.readline()
        if self.debuglevel > 0: print 'reply:', `line`
        if replyprog.match(line) < 0:
            # Not an HTTP/1.0 response.  Fall back to HTTP/0.9.
            # Push the data back into the file.
            self.file.seek(-len(line), 1)
            self.headers = {}
            app = grailutil.get_grailapp()
            c_type, c_encoding = app.guess_type(self.selector)
            if c_encoding:
                self.headers['content-encoding'] = c_encoding
            # HTTP/0.9 sends HTML by default
            self.headers['content-type'] = c_type or "text/html"
            return 200, "OK", self.headers
        errcode, errmsg = replyprog.group(1, 2)
        errcode = string.atoi(errcode)
        errmsg = string.strip(errmsg)
        self.headers = mimetools.Message(self.file, 0)
        return errcode, errmsg, self.headers

    def close(self):
        if self.file:
            self.file.close()
        if self.sock:
            try:
                self.sock.close()
            except socket.error:
                # What can you do? :-)
                pass
        self.file = None
        self.sock = None


class http_access:

    def __init__(self, resturl, method, params, data=None):
        self.app = grailutil.get_grailapp()
        self.args = (resturl, method, params, data)
        self.state = WAIT
        self.h = None
        self.reader_callback = None
        self.app.sq.request_socket(self, self.open)

    def register_reader(self, reader_callback, ignore):
        if self.state == WAIT:
            self.reader_callback = reader_callback
        else:
            # we've been waitin' fer ya
            reader_callback()

    def open(self):
        Assert(self.state == WAIT)
        resturl, method, params, data = self.args
        if data:
            Assert(method=="POST")
        else:
            Assert(method in ("GET", "POST"))
        if type(resturl) == type(()):
            host, selector = resturl    # For proxy interface
        else:
            host, selector = splithost(resturl)
        if not host:
            raise IOError, "no host specified in URL"
        i = string.find(host, '@')
        if i >= 0:
            user_passwd, host = host[:i], host[i+1:]
        else:
            user_passwd = None
        if user_passwd:
            import base64
            auth = string.strip(base64.encodestring(user_passwd))
        else:
            auth = None
        self.h = MyHTTP(host)
        self.h.putrequest(method, selector)
        self.h.putheader('User-agent', GRAILVERSION)
        if auth:
            self.h.putheader('Authorization', 'Basic %s' % auth)
        if not params.has_key('host'):
            self.h.putheader('Host', host)
        if not params.has_key('accept-encoding'):
            encodings = Reader.get_content_encodings()
            if encodings:
                encodings.sort()
                self.h.putheader(
                    'Accept-Encoding', string.join(encodings, ", "))
        for key, value in params.items():
            if key[:1] != '.':
                self.h.putheader(key, value)
        self.h.putheader('Accept', '*/*')
        self.h.endheaders()
        if data:
            self.h.send(data)
        self.readahead = ""
        self.state = META
        self.line1seen = 0
        if self.reader_callback:
            self.reader_callback()

    def close(self):
        if self.h:
            self.h.close()
        if self.state != CLOS:
            self.app.sq.return_socket(self)
            self.state = CLOS
        self.h = None

    def pollmeta(self, timeout=0):
        Assert(self.state == META)

        sock = self.h.sock
        try:
            if not select.select([sock], [], [], timeout)[0]:
                return "waiting for server response", 0
        except select.error, msg:
            raise IOError, msg, sys.exc_traceback
        try:
            new = sock.recv(1024)
        except socket.error, msg:
            raise IOError, msg, sys.exc_traceback
        if not new:
            return "EOF in server response", 1
        self.readahead = self.readahead + new
        if '\n' not in new:
            return "receiving server response", 0
        if not self.line1seen:
            i = string.find(self.readahead, '\n')
            if i < 0:
                return "receiving server response", 0
            self.line1seen = 1
            line = self.readahead[:i+1]
            if replyprog.match(line) < 0:
                return "received non-HTTP/1.0 server response", 1
        i = endofheaders.search(self.readahead)
        if i >= 0:
            return "received server response", 1
        return "receiving server response", 0

    def getmeta(self):
        Assert(self.state == META)
        if not self.readahead:
            x, y = self.pollmeta(None)
            while not y:
                x, y = self.pollmeta(None)
        file = StringIO.StringIO(self.readahead)
        errcode, errmsg, headers = self.h.getreply(file)
        self.state = DATA
        self.readahead = file.read()
        return errcode, errmsg, headers

    def polldata(self):
        Assert(self.state == DATA)
        if self.readahead:
            return "processing readahead data", 1
        return ("waiting for data",
                len(select.select([self], [], [], 0)[0]))

    def getdata(self, maxbytes):
        Assert(self.state == DATA)
        if self.readahead:
            data = self.readahead[:maxbytes]
            self.readahead = self.readahead[maxbytes:]
            return data
        try:
            data = self.h.sock.recv(maxbytes)
        except socket.error, msg:
            raise IOError, msg, sys.exc_traceback
        if not data:
            self.state = DONE
            # self.close()
        return data

    def fileno(self):
        return self.h.sock.fileno()


# To test this, use ProtocolAPI.test()
