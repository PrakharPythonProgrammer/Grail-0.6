"""Browser class."""


import os
import string
import sys
import grailutil

from Tkinter import *
import tktools

from Viewer import Viewer


LOGO_IMAGES = "logo:"
FIRST_LOGO_IMAGE = LOGO_IMAGES + "T1.gif"


# Window title prefix
TITLE_PREFIX = "Grail: "


# If we have an icon file, replace tktools.make_toplevel so that it gets
# set up as the icon, otherwise don't do anything magic.
#
_mydir = os.path.dirname(grailutil.abspath(__file__))
_iconxbm_file = grailutil.which(
    'icon.xbm', (_mydir, os.path.join(_mydir, "data")))
if _iconxbm_file:
    _iconmask_file = os.path.join(os.path.dirname(_iconxbm_file),
                                  "iconmask.xbm")
    if not os.path.isfile(_iconmask_file):
        _iconmask_file = None
    def make_toplevel(*args, **kw):
        w = apply(tktools_make_toplevel, args, kw)
        # icon set up
        try: w.iconbitmap('@' + _iconxbm_file)
        except TclError: pass
        if _iconmask_file:
            try: w.iconmask('@' + _iconmask_file)
            except TclError: pass
        return w
    #
    tktools_make_toplevel = tktools.make_toplevel
    tktools.make_toplevel = make_toplevel


class Browser:
    """The Browser class provides the top-level GUI.

    It is a blatant rip-off of Mosaic's look and feel, with menus, a
    stop button, a URL display/entry area, and (last but not least) a
    viewer area.  But then, so are all other web browsers. :-)

    """
    def __init__(self, master, app=None,
                 width=None, height=None,
                 geometry=None):
        self.master = master
        if not app:
            app = grailutil.get_grailapp()
        prefs = app.prefs
        self.app = app

        if not width: width = prefs.GetInt('browser', 'default-width')
        if not height: height = prefs.GetInt('browser', 'default-height')

        self.create_widgets(width=width, height=height, geometry=geometry)
        self.root.iconname('Grail')
        app.add_browser(self)

    def create_widgets(self, width, height, geometry):
        # I'd like to be able to set the widget name here, but I'm not
        # sure what the correct thing to do is.  Setting it to `grail'
        # is definitely *not* the right thing to do since this causes
        # all sorts of problems.
        self.root = tktools.make_toplevel(self.master, class_='Grail')
        self._window_title("Grail: New Browser")
        if geometry:
            self.root.geometry(geometry)
        self.root.protocol("WM_DELETE_WINDOW", self.on_delete)
        self.topframe = Frame(self.root)
        self.topframe.pack(fill=X)
        self.create_logo()
        self.create_menubar()
        self.create_urlbar()
        self.create_statusbar()
        self.viewer = Viewer(self.root, browser=self,
                             width=width, height=height)
        self.context = self.viewer.context
        if self.app.prefs.GetBoolean('browser', 'show-logo'):
            self.logo_init()

    def create_logo(self):
        self.logo = Button(self.root, name="logo",
                           command=self.stop_command,
                           state=DISABLED)
        self.logo.pack(side=LEFT, fill=BOTH, padx=10, pady=10,
                       in_=self.topframe)
        self.root.bind("<Alt-period>", self.stop_command)
        self.logo_animate = 0

    def create_menubar(self):
        # Create menu bar, menus, and menu entries

        # Create menu bar
        self.mbar = Menu(self.root, name="menubar", tearoff=0)
        self.root.config(menu=self.mbar)

        # Create the menus
        self.create_menu("file")
        self.create_menu("go")
        self.histmenu = self.gomenu     # backward compatibility for Ping
        self.create_menu("search")
        self.create_menu("bookmarks")
        self.create_menu("preferences")

        # List of user menus (reset on page load)
        self.user_menus = []

        if self.get_helpspec():
            self.create_menu("help")

    def create_menu(self, name):
        menu = Menu(self.mbar, name=name)
        self.mbar.add_cascade(label=string.capitalize(name), menu=menu)
        setattr(self, name + "menu", menu)
        getattr(self, "create_menu_" + name)(menu)

    def _menucmd(self, menu, label, accelerator, command):
        if not accelerator:
            menu.add_command(label=label, command=command)
            return
        underline = None
        if len(accelerator) == 1:
            # do a lot to determine the underline position
            underline = string.find(label, accelerator)
            if underline == -1:
                accelerator = string.lower(accelerator)
                underline = string.find(label, accelerator)
                if underline == -1:
                    underline = None
                accelerator = string.upper(accelerator)
        menu.add_command(label=label, command=command, underline=underline,
                         accelerator="Alt-" + accelerator)
        self.root.bind("<Alt-%s>" % accelerator, command)
        if len(accelerator) == 1:
            self.root.bind("<Alt-%s>" % string.lower(accelerator), command)

    def create_menu_file(self, menu):
        self._menucmd(menu, "New Window", "N", self.new_command)
        self._menucmd(menu, "Clone Current Window", "K", self.clone_command)
        self._menucmd(menu, "View Source", "V", self.view_source_command)
        self._menucmd(menu, 'Open Location...', "L", self.open_uri_command)
        self._menucmd(menu, 'Open File...', "O", self.open_file_command)
        self._menucmd(menu, 'Open Selection', "E",
                      self.open_selection_command)
        menu.add_separator()
        self._menucmd(menu, "Save As...", "S", self.save_as_command)
        self._menucmd(menu, "Print...", "P", self.print_command)
        import DocumentInfo
        self._menucmd(menu, "Document Info...", "D",
                      DocumentInfo.DocumentInfoCommand(self))
        menu.add_separator()
        self._menucmd(menu, "I/O Status Panel...", "I", self.iostatus_command)
        menu.add_separator()
        self._menucmd(menu, "Close", "W", self.close_command),
        if not self.app.embedded:
            self._menucmd(menu, "Quit", "Q", self.quit_command)

    def create_menu_go(self, menu):
        self._menucmd(menu, "Back", "Left", self.back_command)
        self._menucmd(menu, "Forward", "Right", self.forward_command)
        self._menucmd(menu, "Reload", "R", self.reload_command)
        menu.add_separator()
        self._menucmd(menu, 'History...', "H", self.show_history_command)
        self._menucmd(menu, "Home", None, self.home_command)

    def create_menu_search(self, menu):
        menu.grail_browser = self       # Applet compatibility
        import SearchMenu
        SearchMenu.SearchMenu(menu, self.root, self)

    def create_menu_bookmarks(self, menu):
        menu.grail_browser = self # Applet compatibility
        import BookmarksGUI
        self.bookmarksmenu_menu = BookmarksGUI.BookmarksMenu(menu)

    def create_menu_preferences(self, menu):
        from PrefsPanels import PrefsPanelsMenu
        PrefsPanelsMenu(menu, self)

    def create_menu_help(self, menu):
        lines = self.get_helpspec()
        i = 0
        n = len(lines) - 1
        while i < n:
            label = lines[i]
            i = i+1
            if label == '-':
                menu.add_separator()
            else:
                url = lines[i]
                i = i+1
                self._menucmd(menu, label, None, HelpMenuCommand(self, url))

    __helpspec = None
    def get_helpspec(self):
        if self.__helpspec is not None:
            return self.__helpspec
        raw = self.app.prefs.Get('browser', 'help-menu')
        lines = filter(None, map(string.strip, string.split(raw, '\n')))
        lines = map(string.split, lines)
        self.__helpspec = tuple(map(string.join, lines))
        return self.__helpspec

    def create_urlbar(self):
        f = Frame(self.topframe)
        f.pack(fill=X)
        l = Label(self.root, name="uriLabel")
        l.pack(side=LEFT, in_=f)
        self.entry = Entry(self.root, name="uriEntry")
        self.entry.pack(side=LEFT, fill=X, expand=1, in_=f)
        self.entry.bind('<Return>', self.load_from_entry)

    def create_statusbar(self):
        msg_frame = Frame(self.root, name="statusbar")
        msg_frame.pack(fill=X, side=BOTTOM, in_=self.topframe)
        msg_frame.propagate(OFF)
        fontspec = self.app.prefs.Get('presentation', 'message-font')
        fontspec = string.strip(fontspec) or None
        self.msg = Label(self.root, font=fontspec, name="status")
        self.msg.pack(fill=X, in_=msg_frame)

    # --- External interfaces ---

    def get_async_image(self, src):
        # XXX This is here for the 0.2 ImageLoopItem applet only
        return self.context.get_async_image(src)

    def allowstop(self):
        self.logo_start()

    def clearstop(self):
        self.logo_stop()

    def clear_reset(self):
        num = len(self.user_menus)
        if num:
            last = self.mbar.index(END)
            if num > 1:
                self.mbar.delete(last-num+1, last)
            else:
                self.mbar.delete(last)
        for b in self.user_menus:
            b.destroy()
        self.user_menus[:] = []

    def set_url(self, url):
        self.set_entry(url)
        title, when = self.app.global_history.lookup_url(url)
        self.set_title(title or url)

    def set_title(self, title):
        self._window_title(TITLE_PREFIX + title)

    def message(self, string = ""):
        self.msg['text'] = string

    def messagevariable(self, variable=None):
        if variable:
            self.msg['textvariable'] = variable
        else:
            self.msg['textvariable'] = ""
            self.msg['text'] = ""
    message_clear = messagevariable

    def error_dialog(self, exception, msg):
        if self.app:
            self.app.error_dialog(exception, msg, root=self.root)
        else:
            print "ERROR:", msg

    def load(self, *args, **kw):
        """Interface for applets."""
        return apply(self.context.load, args, kw)

    def valid(self):
        return self.app and self in self.app.browsers

    # --- Internals ---

    def _window_title(self, title):
        self.root.title(title)
        self.root.iconname(title)

    def set_entry(self, url):
        self.entry.delete('0', END)
        self.entry.insert(END, url)

    def close(self):
        self.context.stop()
        self.viewer.close()
        self.root.destroy()
        self.bookmarksmenu_menu.close()
        self.bookmarksmenu_menu = None
        if self.app:
            self.app.del_browser(self)
            self.app.maybe_quit()

    # --- Callbacks ---

    # WM_DELETE_WINDOW on toplevel

    def on_delete(self):
        self.close()

    # <Return> in URL entry field

    def load_from_entry(self, event):
        url = string.strip(self.entry.get())
        if url:
            self.context.load(grailutil.complete_url(url))
        else:
            self.root.bell()

    # Stop command

    def stop_command(self, event=None):
        if self.context.busy():
            self.context.stop()
            self.message("Stopped.")

    # File menu commands

    def new_command(self, event=None):
        b = Browser(self.master, self.app)
        return b

    def clone_command(self, event=None):
        b = Browser(self.master, self.app)
        b.context.clone_history_from(self.context)
        return b

    def open_uri_command(self, event=None):
        import OpenURIDialog
        dialog = OpenURIDialog.OpenURIDialog(self.root)
        uri, new = dialog.go()
        if uri:
            if new:
                browser = Browser(self.master, self.app)
            else:
                browser = self
            browser.context.load(grailutil.complete_url(uri))

    def open_file_command(self, event=None):
        import FileDialog
        dialog = FileDialog.LoadFileDialog(self.master)
        filename = dialog.go(key="load")
        if filename:
            import urllib
            self.context.load('file:' + urllib.pathname2url(filename))

    def open_selection_command(self, event=None):
        try:
            selection = self.root.selection_get()
        except TclError:
            self.root.bell()
            return
        uri = string.joinfields(string.split(selection), '')
        self.context.load(grailutil.complete_url(uri))

    def view_source_command(self, event=None):
        self.context.view_source()

    def save_as_command(self, event=None):
        self.context.save_document()

    def print_command(self, event=None):
        self.context.print_document()

    def iostatus_command(self, event=None):
        self.app.open_io_status_panel()

    def close_command(self, event=None):
        # File/Close
        self.close()

    def quit_command(self, event=None):
        # File/Quit
        if self.app: self.app.quit()
        else: self.close()

    # History menu commands

    def home_command(self, event=None):
        home = self.app.prefs.Get('landmarks', 'home-page')
        if not home:
            home = self.app.prefs.Get('landmarks', 'default-home-page')
        self.context.load(home)

    def reload_command(self, event=None):
        self.context.reload_page()

    def forward_command(self, event=None):
        self.context.go_forward()

    def back_command(self, event=None):
        self.context.go_back()

    def show_history_command(self, event=None):
        self.context.show_history_dialog()

    # --- Animated logo ---

    def logo_init(self):
        """Initialize animated logo and display the first image.

        This doesn't start the animation sequence -- use logo_start()
        for that.

        """
        self.logo_index = 0             # Currently displayed image
        self.logo_last = -1             # Last image; -1 if unknown
        self.logo_id = None             # Tk id of timer callback
        self.logo_animate = 1           # True if animating
        self.logo_next()

    def logo_next(self):
        """Display the next image in the logo animation sequence.

        If the first image can't be found, disable animation.

        """
        self.logo_index = self.logo_index + 1
        if self.logo_last > 0 and self.logo_index > self.logo_last:
            self.logo_index = 1
        entytyname = "grail.logo.%d" % self.logo_index
        image = self.app.load_dingbat(entytyname)
        if not image:
            if self.logo_index == 1:
                self.logo_animate = 0
                return
            self.logo_index = 1
            entytyname = "grail.logo.%d" % self.logo_index
            image = self.app.load_dingbat(entytyname)
            if not image:
                self.logo_animate = 0
                return
        self.logo.config(image=image, state=NORMAL)

    def logo_start(self):
        """Start logo animation.

        If we can't/don't animate the logo, enable the stop button instead.

        """
        self.logo.config(state=NORMAL)
        if not self.logo_animate:
            return
        if not self.logo_id:
            self.logo_index = 0
            self.logo_next()
            self.logo_id = self.root.after(200, self.logo_update)

    def logo_stop(self):
        """Stop logo animation.

        If we can't/don't animate the logo, disable the stop button instead.

        """
        if not self.logo_animate:
            self.logo.config(state=DISABLED)
            return
        if self.logo_id:
            self.root.after_cancel(self.logo_id)
            self.logo_id = None
        self.logo_index = 0
        self.logo_next()

    def logo_update(self):
        """Keep logo animation going."""
        self.logo_id = None
        if self.logo_animate:
            self.logo_next()
            if self.logo_animate:
                self.logo_id = self.root.after(200, self.logo_update)

    # --- API for searching ---

    def search_for_pattern(self, pattern,
                           regex_flag, case_flag, backwards_flag):
        textwidget = self.viewer.text
        try:
            index = textwidget.index(SEL_FIRST)
            index = '%s + %s chars' % (str(index),
                                       backwards_flag and '0' or '1')
        except TclError:
            index = '1.0'
        length = IntVar(textwidget)
        hitlength = None
        hit = textwidget.search(pattern, index, count=length,
                                nocase=not case_flag,
                                regexp=regex_flag,
                                backwards=backwards_flag)
        if hit:
            try:
                textwidget.tag_remove(SEL, SEL_FIRST, SEL_LAST)
            except TclError:
                pass
            hitlength = length.get()
            textwidget.tag_add(SEL, hit, "%s + %s chars" % (hit, hitlength))
            textwidget.yview_pickplace(SEL_FIRST)
        return hit


class HelpMenuCommand:
    """Encapsulate a menu item into a callable object to load the resource.
    """
    def __init__(self, browser, url):
        self.__browser = browser
        self.__url = url

    def __call__(self, event=None):
        self.__browser.context.load(self.__url)


def test():
    """Test Browser class."""
    import sys
    url = None
    if sys.argv[1:]: url = sys.argv[1]
    root = Tk()
    b = Browser(root)
    if url: b.load(url)
    root.mainloop()


if __name__ == '__main__':
    test()
