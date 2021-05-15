"""Context class."""

import History
import Reader
import string
import grailutil
import time
import math
import urllib
import regsub

from Cursors import *
from grailbase.uricontext import URIContext
from urlparse import urljoin, urlparse, urlunparse, urldefrag


VALID_TARGET_STARTS = string.letters + '_'

# TBD: horrible hack.  search down for reason. -bwarsaw
LAST_CONTEXT = None


class Context(URIContext):

    """Context for browsing operations.
    
    RATIONALE: After much thinking we uncovered the need for a
    separate object to hold the browsing context.  This contains items
    like the history stack (for the back/forward commands), the loaded
    URL (for the reload command), the base URL (for interpreting
    relative links), and probably more.  These used to be stored in
    the browser object, but when introducing frames, each frame will
    need its own context.  Storing the context in the viewer won't
    work either: table cells will be implemented as viewer objects,
    but share their browsing context with the containing frame.

    Resorting to viewer subclasses, some of which would maintain their
    own context and some of which wouldn't, would require overriding
    the anchor operations (which need the context) of the context-less
    viewers.  Having a pointer to a context object in all viewers
    makes this much simpler.

    """

    def __init__(self, viewer, browser):
        URIContext.__init__(self)
        self.viewer = viewer
        self.browser = browser
        self.history = History.History()
        self.history_dialog = None
        self.app = browser.app
        self.root = self.browser.root   # XXX Really a Toplevel instance
        self.readers = []
        self.page = None
        self.future = -1
        self.source = None
        self._target = None
        self.last_status_update = 0.0   # Time when last status update was done
        self.next_status_update = None  # ID of next scheduled status update
        self.show_source = 0
        self.applet_group = None
        self.notifications = []         # callbacks when no readers left
        self.image_maps = {}            # For ImageMap
        self.set_headers({})
        self.set_postdata(None)
        self.local_api_handlers = {}    # This pages local API handlers

    def register_notification(self, callback):
        if callback not in self.notifications:
            self.notifications.append(callback)

    def unregister_notification(self, callback):
        if callback in self.notifications:
            self.notifications.remove(callback)

    def notify(self):
        for callback in self.notifications:
            callback(self)

    def clear_reset(self):
        self.viewer.clear_reset()
        if self.on_top():
            self.browser.clear_reset()
        self.set_url("")

    def on_top(self):
        return self.browser.context is self

    def set_headers(self, headers):
        self.__headers = headers

    def get_headers(self):
        return self.__headers

    def set_postdata(self, data=None):
        self.__postdata = data

    def get_postdata(self):
        return self.__postdata

    # Load URL, base URL and target

    def set_url(self, url, baseurl=None, target=None, histify=1):
        """Set loaded URL, base URL and target for the current page.

        The loaded URL is what this page was loaded from; the base URL
        is used to calculate relative links, and defaults to the
        loaded URL.  The target is the default viewer name
        where followed links will appear, and defaults to this viewer.

        HISTIFY flag, if true, adds the URL to the history stack.

        """
        if url and histify:
            # don't lose title if we have one:
            title, when = self.app.global_history.lookup_url(url)
            self.app.global_history.remember_url(url, title or '')
            if not self.page:
                self.page = History.PageInfo(url)
                self.history.append_page(self.page)
            else:
                self.page.set_url(url)
                self.page.set_title("") # Will be reset from fresh HTML
                self.history.refresh()
        else:
            if self.future >= 0:
                self.page = self.history.page(self.future)
                self.future = -1
            else:
                self.page = None
        URIContext.set_url(self, url, baseurl=baseurl)
        self._target = target
        if self.on_top():
            self.browser.set_url(self.get_url())
        self.applet_group = None

    def set_baseurl(self, baseurl=None, target=None):
        """Set the base URL and target for the current page.

        The base URL is taken relative to the existing base URL.

        """
        URIContext.set_baseurl(self, baseurl)
        if target:
            self._target = target

    def get_target(self):
        """Return the default target for this page (which may be None)."""
        return self._target

    def follow(self, url, target="", histify=1, scrollpos=None):
        """Follow a link, given by a relative URL.

        If the relative URL is a fragment id (#name) on the current
        URL, scroll there; otherwise, do a full load of a new page.

        """

        newurl, frag = urldefrag(url)
        current, f = urldefrag(self.get_url())
        if newurl == current:
            # XXX This is not correct if we got here through a POST.
            context = self.find_window_target(target)
            if context is self:
                self.follow_local_fragment(url, newurl, frag, histify)
                return
        self.load(self.get_baseurl(url), target=(target or self._target),
                  scrollpos=scrollpos)

    def follow_local_fragment(self, url, newurl, frag, histify):
        if self.readers:
            self.readers[-1].fragment = frag
        if frag:
            self.viewer.scroll_to(frag)
        else:
            self.viewer.scroll_to_position(self.page.scrollpos())
            self.viewer.clear_selection()
        self.viewer.remove_temp_tag(histify=1)
        baseurl = self.get_baseurl(url)
        page = self.page
        self.page = None # triggers set_url() to update history
        self.set_url(baseurl, histify=histify)
        if self.future >= 0:
            self.page = self.history.page(self.future)
            self.future = -1
        self.page.set_title(page.title())
        self.history.refresh()
        self.browser.set_title(page.title())

    # Misc

    def get_formdata(self):
        return self.page and self.page.formdata()

    # Message interfaces

    def message(self, string=""):
        self.viewer.message(string)
    enter = message                     # XXX ImageMap backward compatibility

    def message_clear(self):
        self.new_reader_status()
    leave = message_clear               # XXX ImageMap backward compatibility

    def new_reader_status(self):
        if self.app.iostatuspanel:
            self.app.iostatuspanel.update()
        now = time.time()
        seconds = math.floor(now)
        if self.last_status_update == seconds:
            if self.next_status_update:
                return
            self.next_status_update = self.browser.root.after(
                1000 - int(1000*(now%1.0)),
                self.new_reader_status)
            return
        self.last_status_update = seconds
        self.next_status_update = None
        if self.readers:
            nr = len(self.readers)
            nw = 0
            if nr == 1:
                message = str(self.readers[0])
            else:
                nbytes = 0
                maxbytes = 0
                cached = 0
                for reader in self.readers:
                    nbytes = nbytes + reader.nbytes
                    if reader.message == "waiting for socket":
                        nw = nw + 1
                    if reader.maxbytes > 0 and maxbytes >= 0:
                        maxbytes = maxbytes + reader.maxbytes
                    else:
                        maxbytes = -1
                    if reader.api.iscached():
                        cached = cached + 1
                if maxbytes > 0:
                    percent = nbytes*100/maxbytes
                    message = "%d%% of %s read" % (
                        percent, grailutil.nicebytes(maxbytes))
                else:
                    message = "%s read" % grailutil.nicebytes(nbytes)
                if cached == nr:
                    message = message + " (all cached)"
                elif cached:
                    message = message + " (%d cached)" % cached
                message = "%d streams, %d active: %s" % (nr, nr - nw, message)
        elif self.on_top():
            message = ""
        elif self.get_url():
            message = "URL: %s" % self.get_url()
        else:
            message = "empty"
        self.message(message)

    def error_dialog(self, exception, msg):
        if self.app:
            self.app.error_dialog(exception, msg, root=self.root)
        else:
            print "ERROR:", msg

    def set_title(self, title):
        if not title:
            title, when = self.app.global_history.lookup_url(self.get_url())
            title = title or ''
        self.app.global_history.remember_url(self.get_url(), title)
        if self.on_top():
            self.browser.set_title(title)
        if self.page:
            self.page.set_title(title)
            self.history.refresh()

    # Handle (a)synchronous images

    def get_image(self, src):
        image = self.get_async_image(src)
        if image:
            if not image.load_synchronously(self):
                image = None
        return image

    def get_async_image(self, src, reload=0, width=0, height=0):
        # check out the request
        if not src: return None
        url = self.get_baseurl(src)
        if not url: return None
        if not self.app.load_images: return None

        # try loading from the cache
        image = self.app.get_cached_image((url, width, height))
        if image and (not reload or image.is_reloading()):
            if not image.loaded:
                image.start_loading(self)
            return image

        # it's not in the cache.
        from AsyncImage import AsyncImage
        try:
            image = AsyncImage(self, url, reload, width=width, height=height,
                               master=self.root)
        except IOError, msg:
            image = None
        if image:
            self.app.set_cached_image(
                image.get_cache_key(), image, self.viewer)
            if self.app.load_images:
                image.start_loading(self)
        return image

    # Navigation/history commands

    def go_back(self, event=None):
        if not self.load_from_history(self.history.peek(-1)):
            if self.viewer.parent:
                # Remove any local API handlers
                self.viewer.parent.context.remove_local_api_handlers()
                # go out one level:
                self.viewer.parent.context.go_back(event)
            else:
                self.root.bell()

    def go_forward(self, event=None):
        self.load_from_history(self.history.peek(+1))

    def reload_page(self):
        self.load_from_history(self.history.peek(0), reload=1)

    def load_from_history(self, (future, page), reload=0):
        if not page:
            return 0
        self.future = future
        if not reload:
            self.follow(page.url(), histify=0, scrollpos=page.scrollpos(),
                        target="_self")
        else:
            self.load(page.url(), reload=reload, scrollpos=page.scrollpos(),
                      target="_self")
        return 1

    def show_history_dialog(self):
        if not self.history_dialog:
            self.history_dialog = History.HistoryDialog(self, self.history)
            self.history.set_dialog(self.history_dialog)
        else:
            self.history_dialog.show()

    def clone_history_from(self, other):
        self.history = other.history.clone()
        self.future, page = self.history.peek()
        if page:
            self.load(page.url(), scrollpos=page.scrollpos())

    # Internals handle loading pages

    def save_page_state(self, reload=0):
        if not self.page: return
        # Save page scroll position
        self.page.set_scrollpos(self.viewer.scrollpos())
        # Save form contents even if reloading
        formdata = []
        if hasattr(self, 'forms'):
            for fi in self.forms:
                formdata.append(fi.get())
            # remove the attribute
            del self.forms
        self.page.set_formdata(formdata)

    def read_page(self, url, method, params, show_source=0, reload=0,
                  scrollpos=None, data=None):
        # TBD: this is a horrid hack used so that
        # mailtoAPI.mailto_access can get at the URL of the page that
        # the user has clicked off of. -baw
        self.set_postdata(data)
        global LAST_CONTEXT
        LAST_CONTEXT = self
        from Reader import Reader
        Reader(self, url, method, params, show_source, reload, data, scrollpos)

    # Applet Protocol Handler interface
    
    def set_local_api(self, name, klass):
        """Install a local protocol handler"""
        if name[-3:] <> "API":
            raise IOError, "Invalid name (%s) for protocol handler"
        self.local_api_handlers[name] = klass

    def get_local_api(self, url, method, params):
        """get a local handler instance"""
        scheme, resturl = urllib.splittype(url)
        if not scheme:
            raise IOError, ("protocol error",
                            "no scheme identifier in URL", url)
        scheme = string.lower(scheme)
        sanitized = regsub.gsub("[^a-zA-Z0-9]", "_", scheme)
        modname = sanitized + "API"
        try:
            klass  = self.local_api_handlers[modname]
        except KeyError:
            return None
        handler = klass(resturl, method, params)
        handler._url_ = url # To keep BaseReader happy
        return handler

    def remove_local_api_handlers(self):
        """Remove any local handlers from the current context"""
        if self.local_api_handlers:
            self.local_api_handlers = {}


    # External user commands

    def save_document(self, *relurls):
        """Save document to a file.

        Returns true if the x-fer was initiated; allows histification.
        """
        # File/Save As...
        url = apply(self.get_baseurl, relurls)
        if url == self.get_url() and self.busycheck(): return 0
        import FileDialog, os
        fd = FileDialog.SaveFileDialog(self.root)
        # give it a default filename on which save within the
        # current directory
        import urllib
        if urllib.splittype(url)[0] == "data":
            default = ""
        else:
            urlasfile = string.splitfields(url, '/')
            default = urlasfile[-1]
            # strip trailing query
            i = string.find(default, '?')
            if i > 0: default = default[:i]
            # strip trailing fragment
            i = string.rfind(default, '#')
            if i > 0: default = default[:i]
            # maybe bogus assumption?
            if not default: default = 'index.html'
        file = fd.go(default=default, key="save")
        if not file: return 0
        #
        SavingReader(self, url, 'GET', {}, 0, 0, filename=file)
        self.message_clear()
        return 1

    def print_document(self):
        # File/Print...
        if self.busycheck(): return
        import PrintDialog
        PrintDialog.PrintDialog(self,
                                self.get_url(),
                                self.get_title())

    def view_source(self):
        from Browser import Browser
        browser = Browser(self.app.root, self.app, height=24)
        browser.context.load(self.get_url(), show_source=1)

    # Externals for loading pages

    def load(self, url, method='GET', params={},
             show_source=0, reload=0, scrollpos=None,
             target="", source=None):
        # Update state of current page, in case we re-visit it via the
        # history mechanism.
        if not source:
            source = self.viewer
        if self.source and self.source is not source:
            self.source.remove_temp_tag()
        self.source = source
        context = self.find_window_target(target)
        if context is not self:
            context.load(url, method, params, show_source,
                         reload, scrollpos, "_self", source)
            return
        self.stop()
        self.save_page_state()
        # Start loading a new URL into the window
        self.message("Loading %s" % url)
        if reload:
            show_source = self.show_source
        else:
            self.show_source = show_source
        try:
            self.read_page(url, method, params,
                           show_source=show_source, reload=reload,
                           scrollpos=scrollpos)
            self.show_source = show_source
        except IOError, msg:
            self.error_dialog(IOError, msg)
            self.message_clear()
            if self.source:
                self.source.remove_temp_tag()
                self.source = None

    def find_window_target(self, target):
        """Return a context gotten from the target; by default self."""
        context = None
        if target and target[0] not in VALID_TARGET_STARTS:
            target = ""
        if target == self.viewer.name:
            target = ""
        if target:
            if target[0] == "_":
                if target == "_blank":
                    newbrowser = self.browser.new_command()
                    context = newbrowser.context
                elif target == "_self":
                    pass
                elif target == "_parent":
                    parentviewer = self.viewer.find_parentviewer()
                    context = parentviewer and parentviewer.context
                elif target == "_top":
                    context = self.browser.context
                target = ""
            else:
                # First try to find the target in the current browser
                viewer = self.browser.context.viewer.find_subviewer(target)
                if not viewer:
                    # Try to find another browser with this name
                    for browser in self.app.browsers:
                        if browser.viewer.name == target:
                            viewer = browser.viewer
                            break
                if not viewer:
                    # Try to find a frame inside other browsers
                    for browser in self.app.browsers:
                        if browser is self.browser: continue
                        viewer = browser.context.viewer.find_subviewer(target)
                        if viewer:
                            break
                if not viewer:
                    # Create a new browser with this name
                    newbrowser = self.browser.new_command()
                    viewer = newbrowser.context.viewer
                    viewer.name = target # XXX Naughty ;-)
                context = viewer.context
        if context and context is not self:
            context.source = self.source
            self.source = None
        return context or self

    def post(self, url, data="", params={}, target=""):
        # Post form data
        context = self.find_window_target(target)
        if context is not self:
            context.post(url, data, params, target)
            return
        self.stop()
        self.save_page_state()
        url = self.get_baseurl(url)
        method = 'POST'
        self.message("Posting to %s" % url)
        try:
            self.read_page(url, method, params, reload=1, data=data)
        except IOError, msg:
            self.error_dialog(IOError, msg)
            self.message_clear()

    # Externals for managing list of active readers

    def addreader(self, reader):
        self.readers.append(reader)
        if self.on_top():
            self.browser.allowstop()
        self.new_reader_status()

    def rmreader(self, reader):
        if reader in self.readers:
            self.readers.remove(reader)
        if not self.readers:
            if self.on_top():
                self.browser.clearstop()
            if self.source:
                self.source.remove_temp_tag(histify=1)
                self.source = None
            self.notify()
        self.new_reader_status()

    def busy(self):
        return not not self.readers

    def busycheck(self):
        if self.readers:
            self.error_dialog('Busy',
                "Please wait until the transfer is done (or stop it)")
            return 1
        return 0

    def stop(self):
        for reader in self.readers[:]:
            reader.kill()

    # Page interface

    def get_title(self):
        url = self.get_url()
        title, when = self.app.global_history.lookup_url(url)
        if not title:
            title = self.page and self.page.title() or url
        return title




class SimpleContext(Context):
    # this can be used when interactive updates are not desired
    def new_reader_status(self): pass
    def on_top(self): return 0



class SavingReader(Reader.Reader):
    def __init__(self, context, url, *args, **kw):
        self.__filename = kw['filename']
        del kw['filename']
        apply(Reader.Reader.__init__, (self, context, '') + args, kw)
        context.rmreader(self)
        self.url = url
        self.restart(url)

    def handle_meta(self, errcode, errmsg, headers):
        if not self.handle_meta_prelim(errcode, errmsg, headers):
            return
        # now save:
        self.stop()
        try:
            self.save_file = open(self.__filename, "wb")
        except IOError, msg:
            self.context.error_dialog(IOError, msg)
            return
        #
        # add to history without destroying any title already known:
        #
        history = grailutil.get_grailapp().global_history
        title, when = history.lookup_url(self.url)
        history.remember_url(self.url, title or '')
        #
        Reader.TransferDisplay(self.last_context, self.__filename, self)
