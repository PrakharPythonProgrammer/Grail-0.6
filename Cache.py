"""Cache class.

XXX To do

- probably need an interface to get the raw SharedItem instead of the
  SharedAPI instance, for the history list (which wants stuff cached
  even if the cache decides against it)
"""

META, DATA, DONE = 'META', 'DATA', 'DONE' # Three stages

SharedItemExpired = 'SharedItem Expired'

from Assert import Assert
import os
import protocols
import time
import copy

class SharedItem:

    """A shareable cache item.

    The interface is subtly different from that of protocol objects:
    getdata() takes an offset argument, and the sequencing
    restrictions are lifted (i.e. you can call anything in any order).

    A SharedItem hides all protocol access from the rest of the
    system. The reset() method actually calls on the protocol to
    retrieve an object.

    The disk cache passes an disk_cache_access api which sets some
    basic headers and starts the object out in the DATA state.

    """

    def __init__(self, url, mode, params, cache, key, data=None,
                 api=None, reload=None, refresh=None):  
        self.refcnt = 0

        # store the arguments 
        self.url = url
        self.mode = mode
        self.params = params
        self.key = key
        self.postdata = data
        self.cache = cache

        # status
        self.reloading = 0
        self.data = []
        self.datalen = 0
        self.datamap = {}
        self.complete = 0

        # initialize in one of four states
        # some variables may be initialized in reset or refresh

        if reload:               ## forced reload
            self.api = None
            self.stage = DONE
            self.incache = 0
            self.reset(reload)

        elif refresh:            ## check freshness
            self.cache_api = api
            self.cache_meta = api.getmeta()
            self.cache_stage = api.state
            self.incache = 1
            self.refresh(refresh)

        elif api == None:        ## a POST
            self.incache = 0
            self.reset()

        else:                    ## read from cache
            # loading from the cache
            self.api = api
            self.meta = api.getmeta()
            self.stage = self.api.state

            # status
            self.incache = 1

    def reset(self, reload=0):
        # Should only be used inside constructor function.
        # For next release, make it __reset
        self.reloading = reload
        self.api = protocols.protocol_access(self.url,
                                             self.mode, self.params,
                                             data=self.postdata)
        self.stage = self.api.state
        self.init_new_load(META)

    def __repr__(self):
        return "SharedItem(%s)<%d>" % (`self.url`, self.refcnt)

    def iscached(self):
        return self.incache and not self.reloading

    def incref(self):
        self.refcnt = self.refcnt + 1

    def decref(self):
        Assert(self.refcnt > 0)
        self.refcnt = self.refcnt - 1
        self.cache_update()
        if self.refcnt == 0:
            if self.stage == DONE:
                self.finish()
            else:
                self.abort()

    def cache_update(self):
        if (self.incache == 0 or self.reloading == 1) \
           and not self.postdata and self.complete == 1 \
           and (self.meta and self.meta[0] == 200):
            self.cache.add(self,self.reloading)
            self.incache = 1

    def pollmeta(self):
        if self.stage == META:
            return self.api.pollmeta()
        elif self.stage == DATA:
            return self.api.polldata()[0], 1
        else:
            return "Reading cache", 1

    def getmeta(self):
        if self.stage == META:
            self.meta = self.api.getmeta()
            self.stage = DATA
        return self.meta

    def polldata(self):
        if self.stage == META:
            msg, ready = self.api.pollmeta()
            if ready:
                self.getmeta()
                msg, ready = self.api.polldata()
        elif self.stage == DATA:
            msg, ready = self.api.polldata()
        else:
            msg, ready = "Reading cache", 1
        return msg, ready

    def getdata(self, offset, maxbytes):
        Assert(offset >= 0)
        Assert(maxbytes > 0)

        while self.stage == DATA and offset >= self.datalen:
            buf = self.api.getdata(maxbytes)
            if not buf:
                self.finish()
                self.complete = 1
            else:
                l = len(buf)
                if l > maxbytes:
                    # we got more than we wanted,
                    # so split into two strings (avoid search next time)
                    self.data.append(buf[:maxbytes])
                    self.datamap[offset] = len(self.data) - 1
                    self.data.append(buf[maxbytes:])
                    self.datamap[offset+maxbytes] = len(self.data) - 1
                else:
                    self.data.append(buf)
                    self.datamap[offset] = len(self.data) - 1
                self.datalen = self.datalen + l

        try:
            # the common case
            chunk = self.data[self.datamap[offset]]
            if len(chunk) > maxbytes:
                return chunk[0:maxbytes]
            else:
                return chunk
        except KeyError:
            if self.stage == META:
                self.meta = self.api.getmeta()
                self.stage = DATA
            elif self.complete == 1 and offset >= self.datalen:
                return ''
            chunk_key, delta = self._getdata_search_string_list(offset)
            chunk = self.data[self.datamap[chunk_key]]
            return chunk[delta:]

    def fileno(self):
        if self.api:
            return self.api.fileno()
        else:
            return -1

    def abort(self):
        self.finish()

    def finish(self):
        if self.cache:
            self.cache.deactivate(self.key)
            if not (self.meta and self.meta[0] == 200):
                self.cache.delete(self.key)
        self.stage = DONE
        api = self.api
        self.api = None
        if api:
            api.close()

    def _getdata_search_string_list(self, offset):
        ### WARNING: this lookup is costly, please avoid
        ###          cost is O(k), where k is # of chunks
        ###          if you use this a lot, you'll get O(N^2) reads
        delta = offset
        chunk_key = None
        for chunk_offset in self.datamap.keys():
            if offset > chunk_offset:
                diff = offset - chunk_offset
                if diff <= delta:
                    delta = diff
                    chunk_key = chunk_offset
        return chunk_key, delta

    def init_new_load(self,stage):
        self.meta = None
        self.data = []
        self.datalen = 0
        self.datamap = {}
        self.stage = stage
        self.complete = 0

    def refresh(self,when):
        params = copy.copy(self.params)
        params['If-Modified-Since'] = when.get_str()
        self.api = protocols.protocol_access(self.url,
                                             self.mode, params,
                                             data=self.postdata)
        self.meta = None
        self.stage = self.api.state
        self.hidden_getmeta = self.getmeta
        self.getmeta = self.refresh_getmeta

    def refresh_getmeta(self):
        self.meta = self.api.getmeta()
        ### which errcode should I try to handle
        if self.meta[0] == 304:
            # we win! it hasn't been modified
            # but we probably need to delete the api object
            self.api.close()
            self.api = self.cache_api
            self.meta = self.api.getmeta()
        #elif errcode == 200:
            # there may be cases when we get an error response that
            # doesn't require us to delete the object (a server busy
            # response?). those are *not* handled.
        else:
            # forget about the cached stuff
            self.cache_api.close()
            self.reloading = 1

        self.getmeta = self.hidden_getmeta
        self.stage = DATA
        return self.meta

class SharedAPI:

    """A thin interface to allow multiple threads to share a SharedItem.

    This has the same API as whatever protocol.protocol_access()
    returns.
    
    If the last SharedAPI is closed before the SharedItem has finished
    reading the data, the SharedItem removes itself from the Cache.

    """

    def __init__(self, item):
        self.item = item
        self.item.incref()
        self.offset = 0
        self.stage = META
        self.fno = -1

    def iscached(self):
        return self.item and self.item.iscached()

    def __repr__(self):
        return "SharedAPI(%s)" % self.item

    def __del__(self):
        self.close()

    def pollmeta(self):
        Assert(self.stage == META)
        return self.item.pollmeta()

    def getmeta(self):
        Assert(self.stage == META)
        meta = self.item.getmeta()
        self.stage = DATA
        return meta

    def polldata(self):
        Assert(self.stage == DATA)
        return self.item.polldata()

    def getdata(self, maxbytes):
        Assert(self.stage == DATA)
        data = self.item.getdata(self.offset, maxbytes)
        self.offset = self.offset + len(data)
        if not data:
            self.close()
        return data

    def fileno(self):
        if self.fno < 0:
            self.fno = self.item.fileno()
            if self.fno >= 0:
                try:
                    self.fno = os.dup(self.fno)
                except os.error:
                    self.fno = -1
        return self.fno

    def register_reader(self, reader_start, reader_callback):
        self.item.api.register_reader(reader_start, reader_callback)

    def tk_img_access(self):
        if hasattr(self.item.api, 'tk_img_access'):
            return self.item.api.tk_img_access()
        else:
            return None, None

    def close(self):
        self.stage = DONE
        fno = self.fno
        if fno >= 0:
            self.fno = -1
            os.close(fno)
        item = self.item
        if item:
            self.item = None
            item.decref()


def test():
    """Simple test program."""
    import sys
    url = "http://www.python.org/"
    if sys.argv[1:]: url = sys.argv[1]
    c = Cache()
    for i in range(3):
        api = c.open(url, 'GET', {})
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


if __name__ == '__main__':
    test()
