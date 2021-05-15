#! /usr/bin/env python

"""Grail -- the Extensible Internet Browser."""


# Version string in a form ready for the User-agent HTTP header
__version__ = "Grail/0.6"
GRAILVERSION = __version__

# Standard python imports (needed by path munging code)
import os
import sys

# Path munging
if __name__ == '__main__':
    script_name = sys.argv[0]
    while 1:
        script_dir = os.path.dirname(script_name)
        if not os.path.islink(script_name):
            break
        script_name = os.path.join(script_dir, os.readlink(script_name))
    script_dir = os.path.join(os.getcwd(), script_dir)
    script_dir = os.path.normpath(script_dir)
    grail_root = script_dir
else:
    script_dir = os.path.dirname(__file__)
    grail_root = script_dir
for path in 'utils', 'pythonlib', 'ancillary', 'applets', script_dir:
    sys.path.insert(0, os.path.join(grail_root, path))

import getopt
import string
import urllib
import tempfile
import posixpath

# More imports
import filetypes
import grailbase.utils
# TBD: hack!
grailbase.utils._grail_root = grail_root
import grailutil
from Tkinter import *
import tktools
import BaseApplication
import grailbase.GrailPrefs
import Stylesheet
from CacheMgr import CacheManager
from ImageCache import ImageCache
from Authenticate import AuthenticationManager
import GlobalHistory

# Milliseconds between interrupt checks
KEEPALIVE_TIMER = 500

# Command line usage message
USAGE = """Usage: %s [options] [url]
Options:
    -i, --noimages : inhibit loading of images
    -g <geom>, --geometry <geom> : initial window geometry
    -d <display>, --display <display> : override $DISPLAY
    -q : ignore user's grailrc module""" % sys.argv[0]

def main(args=None):
    prefs = grailbase.GrailPrefs.AllPreferences()
    # XXX Disable cache for NT
    if sys.platform == 'win32':
        prefs.Set('disk-cache', 'size', '0')
    global ilu_tk
    ilu_tk = 0
    if prefs.GetBoolean('security', 'enable-ilu'):
        try: import ilu_tk
        except ImportError: pass
    if args is not None:
        embedded = 1
    else:
        args = sys.argv[1:]
        embedded = 0
    try:
        opts, args = getopt.getopt(args, 'd:g:iq',
                                   ['display=', 'geometry=', 'noimages'])
        if len(args) > 1:
            raise getopt.error, "too many arguments"
    except getopt.error, msg:
        sys.stdout = sys.stderr
        print "Command line error:", msg
        print USAGE
        sys.exit(2)

    geometry = prefs.Get('browser', 'initial-geometry')
    display = None
    user_init = 1

    for o, a in opts:
        if o in ('-i', '--noimages'):
            load_images = 0
        if o in ('-g', '--geometry'):
            geometry = a
        if o in ('-d', '--display'):
            display = a
        if o == "-q":
            user_init = 0
    if args:
        url = grailutil.complete_url(args[0])
    else:
        url = None
    global app
    app = Application(prefs=prefs, display=display)
    app.embedded = embedded
    if __name__ != '__main__':
        import __main__
        __main__.app = app
        __main__.GRAILVERSION = GRAILVERSION

    def load_images_vis_prefs(app=app):
        app.load_images = app.prefs.GetBoolean('browser', 'load-images')
    try:
        app.load_images = load_images
    except NameError:
        load_images_vis_prefs()
    prefs.AddGroupCallback('browser', load_images_vis_prefs)

    import SafeTkinter
    SafeTkinter._castrate(app.root.tk)

    tktools.install_keybindings(app.root)

    # Make everybody who's still using urllib.urlopen go through the cache
    urllib.urlopen = app.open_url_simple

    # Add $GRAILDIR/user/ to sys.path
    subdir = os.path.join(app.graildir, 'user')
    if subdir not in sys.path:
        sys.path.insert(0, subdir)

    # Import user's grail startup file, defined as
    # $GRAILDIR/user/grailrc.py if it exists.
    if user_init:
        try: import grailrc
        except ImportError, e:
            # Only catch this is grailrc itself doesn't import,
            # otherwise propogate.
            if string.split(e.args[0])[-1] != "grailrc":
                raise
        except:
            app.exception_dialog('during import of startup file')

    # Load the initial page (command line argument or from preferences)
    if not embedded:
        from Browser import Browser
        browser = Browser(app.root, app, geometry=geometry)
        if url:
            browser.context.load(url)
        elif prefs.GetBoolean('browser', 'load-initial-page'):
            browser.home_command()

    if not embedded:
        # Give the user control
        app.go()


class URLReadWrapper:

    def __init__(self, api, meta):
        self.api = api
        self.meta = meta
        self.eof = 0

    def read(self, nbytes=-1):
        buf = ''
        BUFSIZ = 8*1024
        while nbytes != 0 and not self.eof:
            new = self.api.getdata(nbytes < 0 and BUFSIZ or nbytes)
            if not new:
                self.eof = 1
                break
            buf = buf + new
            if nbytes > 0:
                nbytes - nbytes - len(new)
                if nbytes <= 0:
                    break
        return buf

    def info(self):
        return self.meta

    def close(self):
        api = self.api
        self.api = None
        self.meta = None
        if api:
            api.close()

class SocketQueue:

    def __init__(self, max_sockets):
        self.max = max_sockets
        self.blocked = []
        self.callbacks = {}
        self.open = 0

    def change_max(self, new_max):
        old_max = self.max
        self.max = new_max
        if old_max < new_max and len(self.blocked) > 0:
            for i in range(0,min(new_max-old_max, len(self.blocked))):
                # run wild free sockets
                self.open = self.open + 1
                self.callbacks[self.blocked[0]]()
                del self.callbacks[self.blocked[0]]
                del self.blocked[0]
            

    def request_socket(self, requestor, callback):
        if self.open >= self.max:
            self.blocked.append(requestor)
            self.callbacks[requestor] = callback
        else:
            self.open = self.open + 1
            callback()

    def return_socket(self, owner):
        if owner in self.blocked:
            # died before its time
            self.blocked.remove(owner)
            del self.callbacks[owner]
        elif len(self.blocked) > 0:
            self.callbacks[self.blocked[0]]()  # apply callback
            del self.callbacks[self.blocked[0]]
            del self.blocked[0]
        else:
            self.open = self.open - 1

class Application(BaseApplication.BaseApplication):

    """The application class represents a group of browser windows."""

    def __init__(self, prefs=None, display=None):
        self.root = Tk(className='Grail', screenName=display)
        self.root.withdraw()
        resources = os.path.join(script_dir, "data", "Grail.ad")
        if os.path.isfile(resources):
            self.root.option_readfile(resources, "startupFile")
        BaseApplication.BaseApplication.__init__(self, prefs)
        # The stylesheet must be initted before any Viewers, so it
        # registers its' prefs callbacks first, hence reloads before the
        # viewers reconfigure w.r.t. the new styles.
        self.stylesheet = Stylesheet.Stylesheet(self.prefs)
        self.load_images = 1            # Overridden by cmd line or pref.

        # socket management
        sockets = self.prefs.GetInt('sockets', 'number')
        self.sq = SocketQueue(sockets)
        self.prefs.AddGroupCallback('sockets',
                                    lambda self=self: \
                                    self.sq.change_max(
                                        self.prefs.GetInt('sockets',
                                                          'number')))

        # initialize on_exit_methods before global_history
        self.on_exit_methods = []
        self.global_history = GlobalHistory.GlobalHistory(self)
        self.login_cache = {}
        self.rexec_cache = {}
        self.url_cache = CacheManager(self)
        self.image_cache = ImageCache(self.url_cache)
        self.auth = AuthenticationManager(self)
        self.root.report_callback_exception = self.report_callback_exception
        if sys.stdin.isatty():
            # only useful if stdin might generate KeyboardInterrupt
            self.keep_alive()
        self.browsers = []
        self.iostatuspanel = None
        self.in_exception_dialog = None
        import Greek
        for k, v in Greek.entitydefs.items():
            Application.dingbatimages[k] = (v, '_sym')
        self.root.bind_class("Text", "<Alt-Left>", self.dummy_event)
        self.root.bind_class("Text", "<Alt-Right>", self.dummy_event)

    def dummy_event(self, event):
        pass

    def register_on_exit(self, method):
        self.on_exit_methods.append(method)
    def unregister_on_exit(self, method):
        try: self.on_exit_methods.remove(method)
        except ValueError: pass
    def exit_notification(self):
        for m in self.on_exit_methods[:]:
            try: m()
            except: pass

    def add_browser(self, browser):
        self.browsers.append(browser)

    def del_browser(self, browser):
        try: self.browsers.remove(browser)
        except ValueError: pass

    def quit(self):
        self.root.quit()

    def open_io_status_panel(self):
        if not self.iostatuspanel:
            import IOStatusPanel
            self.iostatuspanel = IOStatusPanel.IOStatusPanel(self)
        else:
            self.iostatuspanel.reopen()

    def maybe_quit(self):
        if not (self.embedded or self.browsers):
            self.quit()

    def go(self):
        try:
            try:
                if ilu_tk:
                    ilu_tk.RunMainLoop()
                else:
                    self.root.mainloop()
            except KeyboardInterrupt:
                pass
        finally:
            self.exit_notification()

    def keep_alive(self):
        # Exercise the Python interpreter regularly so keyboard
        # interrupts get through
        self.root.tk.createtimerhandler(KEEPALIVE_TIMER, self.keep_alive)

    def get_cached_image(self, url):
        return self.image_cache.get_image(url)

    def set_cached_image(self, url, image, owner=None):
        self.image_cache.set_image(url, image, owner)

    def open_url(self, url, method, params, reload=0, data=None):
        api = self.url_cache.open(url, method, params, reload, data=data)
        api._url_ = url
        return api

    def open_url_simple(self, url):
        api = self.open_url(url, 'GET', {})
        errcode, errmsg, meta = api.getmeta()
        if errcode != 200:
            raise IOError, ('url open error', errcode, errmsg, meta)
        return URLReadWrapper(api, meta)

    def get_cache_keys(self):
        """For applets."""
        return self.url_cache.items.keys()

    def decode_pipeline(self, fp, content_encoding, error=1):
        if self.decode_prog.has_key(content_encoding):
            prog = self.decode_prog[content_encoding]
            if not prog: return fp
            tfn = tempfile.mktemp()
            ok = 0
            try:
                temp = open(tfn, 'w')
                BUFSIZE = 8192
                while 1:
                        buf = fp.read(BUFSIZE)
                        if not buf: break
                        temp.write(buf)
                temp.close()
                ok = 1
            finally:
                if not ok:
                    try:
                        os.unlink(tfn)
                    except os.error:
                        pass
            pipeline = '%s <%s; rm -f %s' % (prog, tfn, tfn)
            # XXX What if prog fails?
            return os.popen(pipeline, 'r')
        if error:
            self.error_dialog(IOError,
                "Can't decode content-encoding: %s" % content_encoding)
        return None

    decode_prog = {
        'gzip': 'gzip -d',
        'x-gzip': 'gzip -d',
        'compress': 'compress -d',
        'x-compress': 'compress -d',
        }

    def exception_dialog(self, message="", root=None):
        exc, val, tb = sys.exc_type, sys.exc_value, sys.exc_traceback
        self.exc_dialog(message, exc, val, tb, root)

    def report_callback_exception(self, exc, val, tb, root=None):
        self.exc_dialog("in a callback function", exc, val, tb, root)

    def exc_dialog(self, message, exc, val, tb, root=None):
        if self.in_exception_dialog:
            print
            print "*** Recursive exception", message
            import traceback
            traceback.print_exception(exc, val, tb)
            return
        self.in_exception_dialog = 1
        def f(s=self, m=message, e=exc, v=val, t=tb, root=root):
            s._exc_dialog(m, e, v, t, root)
        if TkVersion >= 4.1:
            self.root.after_idle(f)
        else:
            self.root.after(0, f)

    def _exc_dialog(self, message, exc, val, tb, root=None):
        # XXX This needn't be a modal dialog --
        # XXX should SafeDialog be changed to support callbacks?
        import SafeDialog
        msg = "An exception occurred " + str(message) + " :\n"
        msg = msg + str(exc) + " : " + str(val)
        dlg = SafeDialog.Dialog(root or self.root,
                                text=msg,
                                title="Python Exception: " + str(exc),
                                bitmap='error',
                                default=0,
                                strings=("OK", "Show traceback"),
                                )
        self.in_exception_dialog = 0
        if dlg.num == 1:
            self.traceback_dialog(exc, val, tb)

    def traceback_dialog(self, exc, val, tb):
        # XXX This could actually just create a new Browser window...
        import TbDialog
        TbDialog.TracebackDialog(self.root, exc, val, tb)

    def error_dialog(self, exc, msg, root=None):
        # Display an error dialog.
        # Return when the user clicks OK
        # XXX This needn't be a modal dialog
        import SafeDialog
        if type(msg) in (ListType, TupleType):
            s = ''
            for item in msg:
                s = s + ':\n' + str(item)
            msg = s[2:]
        else:
            msg = str(msg)
        SafeDialog.Dialog(root or self.root,
                      text=msg,
                      title="Error: " + str(exc),
                      bitmap='error',
                      default=0,
                      strings=('OK',),
                      )

    dingbatimages = {'ldots': ('...', None),    # math stuff
                     'sp': (' ', None),
                     'hairsp': ('\240', None),
                     'thinsp': ('\240', None),
                     'emdash': ('--', None),
                     'endash': ('-', None),
                     'mdash': ('--', None),
                     'ndash': ('-', None),
                     'ensp': (' ', None)
                     }

    def clear_dingbat(self, entname):
        if self.dingbatimages.has_key(entname):
            del self.dingbatimages[entname]

    def set_dingbat(self, entname, entity):
        self.dingbatimages[entname] = entity

    def load_dingbat(self, entname):
        if self.dingbatimages.has_key(entname):
            return self.dingbatimages[entname]
        gifname = grailutil.which(entname + '.gif', self.iconpath)
        if gifname:
            img = PhotoImage(file=gifname, master=self.root)
            self.dingbatimages[entname] = img
            return img
        self.dingbatimages[entname] = None
        return None


if __name__ == "__main__":
    if sys.argv[1:] and sys.argv[1][:2] == '-p':
        p = sys.argv[1]
        del sys.argv[1]
        if p[2:]: n = eval(p[2:])
        else: n = 20
        KEEPALIVE_TIMER = 50000
        import profile
        profile.run('main()', '@grail.prof')
        import pstats
        p = pstats.Stats('@grail.prof')
        p.strip_dirs().sort_stats('time').print_stats(n)
        p.print_callers(n)
        p.strip_dirs().sort_stats('cum').print_stats(n)
    else:
        main()
