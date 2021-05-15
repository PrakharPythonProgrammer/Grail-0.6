"""Implement applet loading, possibly asynchronous."""

import os
import regex
import string
import urllib
import urlparse
from Tkinter import *
from BaseReader import BaseReader
from Bastion import Bastion


# Pattern for valid CODE attribute; group(2) extracts module name
codeprog = regex.compile('^\(.*/\)?\([_a-zA-Z][_a-zA-Z0-9]*\)\.py$')

CLEANUP_HANDLER_NAME = "__cleanup__"


class AppletLoader:

    """Stores semantic information about an applet-to-be.

    This class stores the information gathered from parsing an <APP>
    <APPLET> or <INSERT> tag for an applet, and from the <PARAM> tags
    present within the body of <APPLET> or <INSERT>.  It doesn't do
    any of the parsing itself, but it stores the information gathered
    by the parser.  When the time is ready to instantiate the applet,
    it will do so, either immediately (if its module has laready been
    loaded), or after loading the module asynchronously.

    """

    def __init__(self, parser, name=None, classid=None,
                 code=None, codebase=None,
                 width=None, height=None, vspace=0, hspace=0,
                 align=None,
                 menu=None, reload=0):
        """Store the essential data (from the app or applet tag)"""
        self.parser = parser
        self.viewer = self.parser.viewer
        self.context = self.viewer.context
        self.app = self.parser.app

        self.name = name
        self.classid = classid
        self.code = code
        self.codebase = codebase
        self.width = width
        self.height = height
        self.vspace = vspace
        self.hspace = hspace
        self.align = align
        self.menu = menu
        self.reload = reload
        
        self.params = {}

        self.modname = None
        self.classname = None
        self.codeurl = None

        self.parent = None
        self.module = None
        self.klass = None
        self.instance = None

        self.rexec = None

        if self.reload:
            self.reload.attach(self)

    def __del__(self):
        """Attempt to close() once more."""
        self.close()

    def close(self):
        """Delete all references to external objects."""
        self.parser = self.viewer = self.context = self.app = None
        self.params = {}
        self.modname = self.codeurl = None
        self.parent = self.module = self.klass = self.instance = None
        self.rexec = None
        if self.reload:
            self.reload.detach(self)
        self.reload = None

    def get_rexec(self):
        """Get or create the rexec object for this applet's group."""
        if not self.rexec:
            key = get_key(self.context)
            cache = self.app.rexec_cache
            if not cache.has_key(key) or not cache[key]:
                from AppletRExec import AppletRExec
                rexec = AppletRExec(hooks=None, verbose=2, app=self.app,
                                    group=key)
                cache[key] = rexec
            self.rexec = cache[key]
        return self.rexec

    def feasible(self):
        """Test whether we should try load the applet."""
        prefs = self.app.prefs
        mode = prefs.Get("applets", "load")
        if mode == "none":
            return 0
        if mode == "some":
            key = get_key(self.context)
            rawgroups = prefs.Get("applets", "groups")
            groups = map(string.lower, string.split(rawgroups))
            if key not in groups:
                return 0
        if self.code:                   # <APP> or <APPLET>
            return codeprog.match(self.code) == len(self.code)
        else:                           # <OBJECT>
            if self.classid:
                if codeprog.match(self.classid) == len(self.classid):
                    return 1
            if self.codebase:
                if codeprog.match(self.codebase) == len(self.codebase):
                    return 1
            return 0

    def set_param(self, name, value):
        """Set the value for a named parameter for the widget."""
        try:
            value = string.atoi(value, 0)
        except string.atoi_error:
            try:
                value = string.atol(value, 0)
            except string.atol_error:
                try:
                    value = string.atof(value)
                except string.atof_error:
                    pass
        self.params[name] = value

    def go_for_it(self):
        """Import the module and instantiate the class, maybe async.

        This is synchronous if the module has already been loaded or
        if it will be loaded from a local file; it is asynchronous if
        the module has to be loaded from a remote site.  Errors in
        this stage are reported via the standard error dialog.

        """
        try:
            self._go_for_it()
        except:
            self.show_tb()
            self.close()

    def _go_for_it(self):
        self.get_defaults()
        self.module = self.get_easy_module(self.modname)
        if self.module:
            # Synchronous loading
            self.klass = getattr(self.module, self.classname)
            self.parent = self.make_parent()
            self.instance = apply(self.klass, (self.parent,),
                                  self.params)
            try: cleanup = getattr(self.instance, CLEANUP_HANDLER_NAME)
            except AttributeError: pass
            else: CleanupHandler(self.parser.viewer, cleanup)
        else:
            # Asynchronous loading
            self.parent = self.make_parent()
            api = self.app.open_url(self.codeurl, 'GET', {}, self.reload)
            ModuleReader(self.context, api, self)

    def make_parent(self):
        """Return a widget that will be the applet's parent.

        This is either a menu or a frame subwindow of the text widget.
        """
        if self.menu:
            browser = self.context.browser
            menu = AppletMenu(browser.mbar, self)
            browser.mbar.add_cascade(label=self.menu, menu=menu)
            browser.user_menus.append(menu)
            parent = menu
        else:
            text = self.viewer.text
            bg = text['background']
            frame = AppletFrame(text, self, background=bg)
            if self.width: frame.config(width=self.width)
            if self.height: frame.config(height=self.height)
            self.parser.add_subwindow(frame,
                                      hspace=self.hspace, vspace=self.vspace)
            parent = frame
        return parent                   #  FLD:  made to work in either case

    def load_it_now(self):
        """Invoked by ModuleReader when it is done, to create the applet."""
        try:
            self._load_it_now()
        except:
            self.show_tb()
        self.close()

    def _load_it_now(self):
        """Internal -- load_it_now(), without the try/except clause."""
        mod = self.modname
        rexec = self.get_rexec()
        rexec.reset_urlpath()
        rexec.set_urlpath(self.codeurl)
        rexec.loader.load_module = self.load_module
        try:
            self.module = rexec.r_import(mod)
        finally:
            del rexec.loader.load_module
        self.parser.loaded.append(mod)
        self.klass = getattr(self.module, self.classname)
        self.instance = apply(self.klass, (self.parent,), self.params)
        try: cleanup = getattr(self.instance, CLEANUP_HANDLER_NAME)
        except AttributeError: pass
        else: CleanupHandler(self.parser.viewer, cleanup)

    def get_defaults(self):
        """Internal -- calculate defaults for applet parameters."""
        if self.code:                   # <APP> or <APPLET>
            if codeprog.match(self.code) >= 0:
                self.modname = codeprog.group(2)
            else:
                self.modname = "?" # Shouldn't happen
            if self.name:
                self.classname = self.name
            else:
                self.classname = self.modname
            self.codeurl = self.context.get_baseurl(
                self.codebase, self.code)
        elif self.classid or self.codebase: # <OBJECT>
            if self.classid and codeprog.match(self.classid) >= 0:
                self.codeurl = self.classid
                self.modname = codeprog.group(2)
                self.classname = self.modname
            elif self.classid:
                self.classname = self.classid
                self.modname = self.classid
                self.codeurl = self.modname + ".py"
            if self.codebase and codeprog.match(self.codebase) >= 0:
                self.modname = codeprog.group(2)
                if not self.classname:
                    self.classname = self.modname
                self.codeurl = self.context.get_baseurl(self.codebase)
            else:
                self.codeurl = self.context.get_baseurl(self.codebase,
                                                        self.codeurl)
            

    def get_easy_module(self, mod):
        """Internal -- import a module if it can be done locally."""
        m = self.mod_is_loaded(mod)
        if not m:
            stuff = self.mod_is_local(mod)
            if stuff:
                m = self.load_module(mod, stuff)
        return m

    def mod_is_loaded(self, mod):
        """Internal -- check whether a module has already been loaded."""
        rexec = self.get_rexec()
        try:
            return rexec.modules[mod]
        except KeyError:
            return None

    def mod_is_local(self, mod):
        """Internal -- check whether a module can be found locally."""
        rexec = self.get_rexec()
        path = rexec.get_url_free_path()
        return rexec.loader.find_module(mod, path)

    def load_module(self, mod, stuff):
        """Internal -- load a module given the imp.find_module() stuff."""
        rexec = self.get_rexec()
        rexec.reset_urlpath()
        rexec.set_urlpath(self.codeurl)
        # XXX Duplicate stuff from rexec.RModuleLoader.load_module()
        # and even from ihooks.FancyModuleLoader.load_module().
        # This is needed to pass a copy of the source to linecace.
        file, filename, info = stuff
        (suff, mode, type) = info
        import imp
        import ihooks
        if type == imp.PKG_DIRECTORY:
            loader = self.get_rexec().loader
            return ihooks.FancyModuleLoader.load_module(loader, mod, stuff)
        if type == imp.PY_SOURCE:
            import linecache
            lines = file.readlines()
            data = string.joinfields(lines, '')
            linecache.cache[filename] = (len(data), 0, lines, filename)
            code = compile(data, filename, 'exec')
            m = rexec.hooks.add_module(mod)
            m.__file__ = filename
            m.__filename__ = filename
            exec code in m.__dict__
        elif type == imp.C_BUILTIN:
            m = imp.init_builtin(mod)
        elif type == ihooks.C_EXTENSION:
            m = rexec.load_dynamic(mod, filename, file)
        else:
            raise ImportError, "Unsupported module type: %s" % `filename`
        return m

    def show_tb(self):
        """Internal -- post an exception dialog (via the app)."""
        self.app.exception_dialog("during applet loading",
                                  root=self.context.root)


class ModuleReader(BaseReader):

    """Load an applet, asynchronously.

    First load an applet's source module into the cache.  Once it's
    done, invoke the standard mechanism to actually load the module.
    This will find the source ready for it in the cache.

    """

    def __init__(self, context, api, apploader):
        self.apploader = apploader
        BaseReader.__init__(self, context, api)

    def handle_error(self, errno, errmsg, headers):
        self.apploader.context.error_dialog(
            ImportError,
            "Applet code at URL %s not loaded (%s: %s)" %
            (self.apploader.codeurl, errno, errmsg))
        self.apploader.close()
        self.apploader = None
        BaseReader.handle_error(self, errno, errmsg, headers)

    def handle_eof(self):
        apploader = self.apploader
        self.apploader = None
        apploader.load_it_now()



class Dummy:
    """Base for dummy classes that wrap around Grail objects.

    Ordinary bastions are not enough because there are some methods
    that return existing or new objects that need to be bastionized.

    Thus there are now two layers around each object before it is
    passed to the applet: Bastion -> Dummy -> RealObject.

    In order to make the overhead palatable, the bastions are shared
    within an applet group, but in order to keep applet groups
    compartmentalized, there is a bastion per applet group.

    """

    ok_names = []

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        if name in self.ok_names:
            attr = getattr(self.real, name)
            setattr(self, name, attr)
            return attr
        else:
            raise AttributeError, name  # Attribute not allowed

class AppDummy(Dummy):

    ok_names = ['get_cache_keys']

class BrowserDummy(Dummy):

    ok_names = ['load', 'message', 'valid', 'get_async_image',
                'reload_command']

    def __init__(self, real, key):
        self.real = real
        self.key = key

    def new_command(self):
        return BrowserBastion(self.real.new_command(), self.key)

    def clone_command(self):
        return BrowserBastion(self.real.clone_command(), self.key)

    # 0.2 compatibility:
    
    def follow(self, url):
        self.real.context.follow(url)

##    def get_async_image(self, src):
##      # For 0.2 ImageLoopItem only
##      return Bastion(self.real.get_async_image(src))

class ContextDummy(Dummy):

    ok_names = ['get_baseurl', 'load', 'follow', 'message',
                'get_async_image', 'set_local_api']

##    def get_async_image(self, src):
##      return Bastion(self.real.get_async_image(src))

class GlobalHistoryDummy(Dummy):

    ok_names = ['remember_url', 'lookup_url', 'inhistory_p', 'urls']

class ParserDummy(Dummy):

    ok_names = []

class ViewerDummy(Dummy):

    ok_names = [
        'add_subwindow',
        'bind_anchors',
        # Writer methods:
        'new_alignment',
        'new_font',
        'new_margin',
        'new_spacing',
        'new_styles',
        'send_paragraph',
        'send_line_break',
        'send_hor_rule',
        'send_label_data',
        'send_flowing_data',
        'send_literal_data',
        ]

def AppBastion(real, key):
    try:
        return real._bastions[key]
    except KeyError:
        pass
    except AttributeError:
        real._bastions = {}
    real._bastions[key] = bastion = Bastion(AppDummy(real))
    bastion.global_history = GlobalHistoryBastion(real.global_history, key)
    return bastion

def BrowserBastion(real, key):
    try:
        return real._bastions[key]
    except KeyError:
        pass
    except AttributeError:
        real._bastions = {}
    # Add .context instance variable to help certain applets
    real._bastions[key] = bastion = Bastion(BrowserDummy(real, key))
    bastion.context = ContextBastion(real.context, key)
    bastion.app = AppBastion(real.app, key)
    # 0.2 compatibility:
    bastion.viewer = ViewerBastion(real.context.viewer, key)
    return bastion

def ContextBastion(real, key):
    try:
        return real._bastions[key]
    except KeyError:
        pass
    except AttributeError:
        real._bastions = {}
    real._bastions[key] = bastion = Bastion(ContextDummy(real))
    return bastion

def GlobalHistoryBastion(real, key):
    try:
        return real._bastions[key]
    except KeyError:
        pass
    except AttributeError:
        real._bastions = {}
    real._bastions[key] = bastion = Bastion(GlobalHistoryDummy(real))
    return bastion

def ParserBastion(real, key):
    try:
        return real._bastions[key]
    except KeyError:
        pass
    except AttributeError:
        real._bastions = {}
    real._bastions[key] = bastion = Bastion(ParserDummy(real))
    return bastion

def ViewerBastion(real, key):
    try:
        return real._bastions[key]
    except KeyError:
        pass
    except AttributeError:
        real._bastions = {}
    real._bastions[key] = bastion = Bastion(ViewerDummy(real))
    # Add the text instance variable since it is referenced by some demos.
    # Need a special filter, too!
    def filter(name):
        return name[0] != '_' or name in ('__getitem__',
                                          '__setitem__',
                                          '__str__')
    rtext = real.text
    bastion.text = btext = Bastion(real.text, filter=filter)
    btext._w = rtext._w                 # XXX This defeats the purpose :-(
    btext.tk = rtext.tk                 # XXX This too :-(
    btext.children = rtext.children     # XXX And this :-(
    btext.master = rtext.master         # XXX And so on :-(
    return bastion


class AppletMagic:

    def __init__(self, loader):
        self.grail_parser = self.grail_viewer = self.grail_context = \
                            self.grail_browser = self.grail_app = None
        if loader:
            context = loader.context
            if context:
                key = context.applet_group
                if loader.parser:
                    self.grail_parser = ParserBastion(loader.parser, key)
                if loader.viewer:
                    self.grail_viewer = ViewerBastion(loader.viewer, key)
                self.grail_context = ContextBastion(context, key)
                if context.browser:
                    self.grail_browser = BrowserBastion(context.browser, key)
                if context.app:
                    self.grail_app = AppBastion(context.app, key)


class AppletFrame(Frame, AppletMagic):

    def __init__(self, master, loader=None, cnf={}, **kw):
        apply(Frame.__init__, (self, master, cnf), kw)
        AppletMagic.__init__(self, loader)

    def table_geometry(self):
        w = self.winfo_width()
        h = self.winfo_height()
        return w, w, h


class AppletMenu(Menu, AppletMagic):

    def __init__(self, master, loader=None, cnf={}, **kw):
        apply(Menu.__init__, (self, master, cnf), kw)
        AppletMagic.__init__(self, loader)


# Utilities

def get_key(context):
    key = _get_key(context)
    context.applet_group = key
    return key

def _get_key(context):
    """Get the key to be used in the rexec cache for this context.
    
    For now, we have a separate rexec environment per page.
    In the future, the user will be able to specify the granularity.

    """
    if context.applet_group:
        return context.applet_group
    url = context.get_url()
    app = context.app
    prefs = app.prefs
    rawgroups = prefs.Get("applets", "groups")
    groups = map(string.lower, string.split(rawgroups))
    list = []
    for group in groups:
        list.append((-len(group), string.lower(group)))
    list.sort()
    groups = []
    for length, group in list:
        groups.append(group)
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    if scheme and netloc and scheme in urlparse.uses_netloc:
        netloc = string.lower(netloc)
        user, host = urllib.splituser(netloc)
        if user: return netloc          # User:passwd present -- don't mess
        netloc, port = urllib.splitport(netloc) # Port is ignored
        if netloc in groups:
            return netloc               # Exact match
        for group in groups:            # Look for longest match
            if group[:1] == '.':
                n = len(group)
                if netloc[-n:] == group:
                    return group
            if netloc == group[1:]:     # Exact match on domain name
                return group
        return netloc                   # No match, return full netloc
    return url

def get_rexec(context):
    """Get the rexec object for this context, if one already exists."""
    app = context.app
    key = get_key(context)
    cache = app.rexec_cache
    if cache.has_key(key):
        return cache[key]

def set_reload(context):
    """If there's a rexec object for this context, prepare it for reloading."""
    return ReloadHelper(context)


class ReloadHelper:

    """Helper class to clear reload status when all applets are loaded."""

    # XXX I tried keying off reference counts but it didn't work

    def __init__(self, context):
        self.count = 0
        self.rexec = get_rexec(context)
        if self.rexec:
            self.rexec.set_reload()

    def __del__(self):
        if self.rexec:
            self.rexec.clear_reload()
        self.rexec = None

    def attach(self, who=None):
        self.count = self.count + 1

    def detach(self, who=None):
        self.count = self.count - 1
        if self.count <= 0:
            if self.rexec:
                self.rexec.clear_reload()
                self.rexec = None

class CleanupHandler:
    """Helper to run an applet's __cleanup__ discipline.
    """
    def __init__(self, viewer, handler):
        self._viewer = viewer
        self._handler = handler
        viewer.register_reset_interest(self)

    def __call__(self, *args):
        import sys
        try: self._handler()
        except: sys.exc_traceback = None ## Pulling in show_tb from the loader
        del self._handler                ## doesn't work; not sure why.
        self._viewer.unregister_reset_interest(self)
        del self._viewer
