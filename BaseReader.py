"""Base reader class -- read from a URL in the background."""

import sys
import string
from Tkinter import *
import urlparse
import grailutil


# Default tuning parameters
# BUFSIZE = 8*1024                      # Buffer size for api.getdata()
BUFSIZE = 512                           # Smaller size for better response
SLEEPTIME = 100                         # Milliseconds between regular checks

class BaseReader:

    """Base reader class -- read from a URL in the background.

    Given an API object, poll it until it completes or an
    unrecoverable error occurs.

    Derived classes are supposed to override the handle_*() methods to
    do something meaningful.

    The sequence of calls made to the stop and handle_* functions can
    be expressed by a regular expression:

    (meta data* stop (eof | error) | stop handle_error)

    """

    # Tuning parameters
    sleeptime = SLEEPTIME

    def __init__(self, context, api):
        self.context = context
        self.api = api
        self.callback = self.checkmeta
        self.poller = self.api.pollmeta
        self.bufsize = BUFSIZE
        
        # Stuff for status reporting
        self.nbytes = 0
        self.maxbytes = 0
        self.shorturl = ""
        self.message = "waiting for socket"

        self.context.addreader(self)

        self.fno = None   # will be assigned by start
        self.killed = None

        # Only http_access has delayed startup property.
        # Second argument would allow implementation of persistent
        # connections.
        try:
            self.api.register_reader(self.start, self.checkapi)
        except AttributeError:
            # if the protocol doesn't do that
            ok = 0
            try:
                self.start()
                ok = 1
            finally:
                if not ok:
                    if self.context:
                        self.context.rmreader(self)

    def start(self):
        # when the protocol API is ready to go, it tells the reader
        # to get busy
        self.message = "awaiting server response"
        if self.killed:
            print "start() called after a kill"
            return
        self.fno = self.api.fileno()
        if TkVersion == 4.0 and sys.platform == 'irix5':
            if self.fno >= 20: self.fno = -1 # XXX for SGI Tk OPEN_MAX bug

        if self.fno >= 0:
            tkinter.createfilehandler(
                self.fno, tkinter.READABLE, self.checkapi)
        else:
            # No fileno() -- check every 100 ms
            self.checkapi_regularly()

        # Delete pervious context local protocol handlers
        # We've gotten far enough into the next page without errors
        if self.context:
            self.context.remove_local_api_handlers()

    def __str__(self):
        if self.maxbytes:
            percent = self.nbytes*100/self.maxbytes
            status = "%d%% of %s read" % (percent,
                                          grailutil.nicebytes(self.maxbytes))
        elif not self.nbytes:
            status = self.message
        else:
            status = "%s read" % grailutil.nicebytes(self.nbytes)
        if self.api and self.api.iscached():
            status = status + " (cached)"
        if self.api and not self.shorturl:
            tuple = urlparse.urlparse(self.api._url_)
            path = tuple[2]
            i = string.rfind(path[:-1], '/')
            if i >= 0:
                path = path[i+1:]
            self.shorturl = path or self.api._url_
        return "%s: %s" % (self.shorturl, status)

    def __repr__(self):
        return "%s(...%s)" % (self.__class__.__name__, self.api)

    def update_status(self):
        self.context.new_reader_status() # Will call our __str__() method

    def update_maxbytes(self, headers):
        self.maxbytes = 0
        if headers.has_key('content-length'):
            try:
                self.maxbytes = string.atoi(headers['content-length'])
            except string.atoi_error:
                pass
        self.update_status()

    def update_nbytes(self, data):
        self.nbytes = self.nbytes + len(data)
        self.update_status()

    def kill(self):
        self.killed = 1
        self.stop()
        self.handle_error(-1, "Killed", {})

    def stop(self):
        if self.fno >= 0:
            fno = self.fno
            self.fno = -1
            tkinter.deletefilehandler(fno)

        self.callback = None
        self.poller = None

        if self.api:
            self.api.close()
            self.api = None

        if self.context:
            self.context.rmreader(self)
            self.context = None

    def checkapi_regularly(self):
        if not self.callback:
##          print "*** checkapi_regularly -- too late ***"
            return
        self.callback()
        if self.callback:
            sleeptime = self.sleeptime
            if self.poller and self.poller()[1]: sleeptime = 0
            self.context.root.after(sleeptime, self.checkapi_regularly)

    def checkapi(self, *args):
        if not self.callback:
            print "*** checkapi -- too late ***"
            if self.fno >= 0:
                fno = self.fno
                self.fno = -1
                tkinter.deletefilehandler(fno)
            return
        try:
            self.callback()                     # Call via function pointer
        except:
            if self.context and self.context.app:
                app = self.context.app
            else:
                app = grailutil.get_grailapp()
            app.exception_dialog("in BaseReader")
            self.kill()

    def checkmeta(self):
        self.message, ready = self.api.pollmeta()
        if ready:
            self.getapimeta()

    def checkdata(self):
        self.message, ready = self.api.polldata()
        if ready:
            self.getapidata()

    def getapimeta(self):
        errcode, errmsg, headers = self.api.getmeta()
        self.callback = self.checkdata
        self.poller = self.api.polldata
        if headers.has_key('content-type'):
            content_type = headers['content-type']
        else:
            content_type = None
        if headers.has_key('content-encoding'):
            content_encoding = headers['content-encoding']
        else:
            content_encoding = None
        self.content_type = content_type
        self.content_encoding = content_encoding
        self.update_maxbytes(headers)
        self.handle_meta(errcode, errmsg, headers)
        if self.callback:
            self.callback()             # XXX Handle httpAPI readahead

    def getapidata(self):
        data = self.api.getdata(self.bufsize)
        if not data:
            self.handle_eof()
            self.stop()
            return
        self.update_nbytes(data)
        self.handle_data(data)

    def geteverything(self):
        if self.api:
            if self.callback == self.checkmeta:
                self.getapimeta()
            while self.api:
                self.getapidata()

    # Derived classes are expected to override the following methods

    def handle_meta(self, errcode, errmsg, headers):
        # May call self.stop()
        self.update_maxbytes(headers)
        if errcode != 200:
            self.stop()
            self.handle_error(errcode, errmsg, headers)

    def handle_data(self, data):
        # May call self.stop()
        pass

    def handle_error(self, errcode, errmsg, headers):
        # Called after self.stop() has been called
        pass

    def handle_eof(self):
        # Called after self.stop() has been called
        pass
