"""Framework for implementing GUI panel dialogs for user preference editing.

Loads preference modules from GRAILROOT/prefpanels/*Panel.py and
~user/.grail/prefpanels/*Panel.py."""

__version__ = "$Revision: 2.37 $"

import sys, os
import imp

if __name__ == "__main__":
    # For operation outside of Grail:
    grail_root = '..'
    sys.path = [grail_root, '../utils', '../pythonlib'] + sys.path

import grailbase.GrailPrefs
typify = grailbase.GrailPrefs.typify

import urlparse
from Tkinter import *
import tktools
import grailutil
import string, regex, regsub
from types import StringType


PANEL_CLASS_NAME_SUFFIX = 'Panel'

grail_root = grailutil.get_grailroot()

# User's panels dir should come after sys, so user's takes precedence.
panels_dirs = [os.path.join(grail_root, 'prefpanels'),
               os.path.expanduser("~/.grail/prefpanels"),
               # These two for backwards compat with beta versions:
               os.path.join(grail_root, 'prefspanels'),
               os.path.expanduser("~/.grail/prefspanels")]

modname_matcher = regex.compile("^\(.*\)Panel.py[c]?$")

# Framework

class Framework:
    """Skeleton for building preference panels via inheritance.

    The framework provides general controls, like save/revert/resume, and a
    mechanism for associating the User Interface elements with preferences,
    so the preferences are systematically revised when the changes are
    committed.

    See 'htdocs/info/extending/prefs-panels.html' for most up-to-date
    instructions.

    To build a preferences panel:

     - Create a class inheriting from this one, named with the
       concatenation of the panel name and "Panel", eg "GeneralPanel".
     - Implement panel-specific layout by overriding the .CreateLayout()
       method.  This is mandatory.
       - Within .CreateLayout, use the self.RegisterUI() to couple the
         widget (or whatever user interface element) with the corresponding
         preference.  (.widget_set_func() is useful for producing the uiset
         func for many tkinter widgets.) 
       - There are also some convenient routines for making widgets, eg
         self.PrefsCheckButton().
     - Override .UpdateLayout() for actions, if any, that need to be done
       when settings are changed with the Revert or Factory Defaults
       buttons.
     - Override .Dismiss() for actions, if any, to be done when the panel
       is closed.

    Your panel will be included in the Preferences menu bar pulldown, and
    will be posted when its entry is selected."""

    # Override this with the URL for the panel-specific help (which you
    # must write, or your panel will have only the general help!)
    HELP_URL = "help/prefs/index.html"

    def __init__(self, name, app):
        """Invoke from category-specific __init__."""
        self.collection = {}
        self.app = app
        self.helpbrowser = None
        self.frame = app.root
        self.name = name
        self.title = self.name + ' Preferences'
        self.widget = None
        self.prev_settings = {}

    # Mandatory preferences-specific layout method.
    def CreateLayout(self, name, frame):
        """Override this method with specific layout."""
        raise SystemError, "Derived class should override .CreateLayout()"

    # Optional preferences-specific layout method.
    def UpdateLayout(self):
        """Called when Factory Defaults or Revert buttons are pushed.

        Override it if you have to do some layout update."""
        pass

    # Optional preferences-specific delete method.
    def Dismiss(self):
        """Override this method for cleanup on dismissal, if any."""
        pass

    # Use this routine in category layout to associate preference with the
    # user interface mechanism for setting them.
    def RegisterUI(self, group, component, type_nm, uiget, uiset):
        """Associate preference with User Interface setting mechanism.

        Preference is specified by group and component.  Type is used for
        choice of preference-get funcs.  uiget and uiset should be routines
        that obtain and impose values on the panel widget representing the
        preference.  (.widget_set_func() is useful for producing the uiset
        func for many tkinter widgets.)"""

        self.collection[(group, component)] = (type_nm, uiget, uiset)

    # Helpers

    def PrefsWidgetLabel(self, frame, text, label_width=25):
        """Convenience, create regular-width widget label on frame left side.

        The default width is 25.  (You can keep the width regular with text
        longer than 25 chars by embedding \n newlines at suitable points.)

        The label is returned, in the unlikely case more than the frame is
        needed. 

        Useful so your widgets line up."""

        label = Label(frame, text=text, width=label_width, anchor=E)
        label.pack(side=LEFT)
        return label

    def PrefsEntry(self, parent, label, group, component,
                   typename='string',
                   label_width=25, entry_height=1, entry_width=None,
                   composite=0, variable=None):
        """Convenience for creating preferences entry or text widget.

        A frame is built within the specified parent, and packed with a
        specified label and an entry widget, created for the purpose.  The
        value of the entry widget is coupled with the designated
        preference.

        The label is apportioned a specified number of characters, default
        25, on the left side of the frame, to enable lining up nicely with
        other, similarly constructed widgets.

        The entry widget may optionally have a height greater than 1, in
        which case a text widget of that height is used."""

        if not composite:
            use_expand = 1
            use_fill = X
            use_side = TOP
            if not entry_width:
                entry_width = 40
        else:
            use_expand = 0
            use_fill = NONE
            use_side = LEFT
        # Assemble the widget:
        frame = Frame(parent, borderwidth=1)
        self.PrefsWidgetLabel(frame, label, label_width=label_width)
        if entry_height == 1:
            entry = Entry(frame, relief=SUNKEN, border=1, width=entry_width,
                          textvariable=(variable and variable or None))
            # note that the variable setting is stripped if None, so this is ok
            entry.pack(side=use_side, expand=use_expand, fill=use_fill)
            if not variable:
                getter, setter = entry.get, self.widget_set_func(entry)
            else:
                getter, setter = variable.get, variable.set
        else:
            if variable:
                raise ValueError, \
                      "multi-line entry fields may not specify a variable"
            entry, garbage = tktools.make_text_box(frame,
                                                   width=entry_width,
                                                   height=entry_height,
                                                   vbar=1)
            def getter(entry=entry):
                return entry.get('1.0', entry.index("end-1char"))
            def setter(chars, entry=entry):
                entry.delete('1.0', entry.index(END))
                entry.insert('1.0', chars)

        frame.pack(fill=use_fill, side=use_side, expand=use_expand)
        parent.pack(fill=use_fill, side=use_side)
        # Couple the entry with the pref:
        self.RegisterUI(group, component, typename, getter, setter)
        return frame

    def PrefsRadioButtons(self, frame, title, button_labels,
                          group, component, typename='string',
                          composite=0, label_width=25, variable=None):
        """Convenience for creating radiobutton preferences widget.

        A label and a button are packed in 'frame' arg, using 'title'.

        Optional 'composite' specifies packing to allow inhabiting frames
        on the same line as other settings widgets.

        Optional 'label_width' specifies the left-side space alloted for the
        widget title."""

        f = Frame(frame)
        if not variable:
            variable = StringVar(f)
        self.PrefsWidgetLabel(f, title, label_width=label_width)
        inner = Frame(f, relief=SUNKEN, borderwidth=1)
        inner.pack(side=LEFT)
        for bl in button_labels:
            b = Radiobutton(inner, text=bl, variable=variable, value=bl)
            b.pack(side=LEFT)

        if composite:
            use_side=LEFT
            use_fill=NONE
            use_expand=1
        else:
            use_side=TOP
            use_fill=X
            use_expand=0
            
        f.pack(fill=use_fill, side=use_side, pady='1m', expand=use_expand)

        self.RegisterUI(group, component, typename, variable.get, variable.set)

    def PrefsCheckButton(self, frame, general, specific, group, component,
                         label_width=25, variable=None):
        """Convenience for creating checkbutton preferences widget.

        A label and a button are packed in 'frame' arg, using text of
        'general' arg for title and of 'specific' arg for button label.
        The preferences variable is specified by 'group' and 'component'
        args, and an optional 'label_width' arg specifies how much space
        should be assigned to the general-label side of the thing.

        If the general-lable is None, then the check button is taken as a
        composite."""

        f = Frame(frame)

        if not variable:
            variable = StringVar(f)

        if general:
            self.PrefsWidgetLabel(f, general, label_width=label_width)
        cb = Checkbutton(f, text=specific, variable=variable)
        cb.pack(side=LEFT)
        if not general:
            use_side, use_fill = LEFT, NONE
        else:
            use_side, use_fill = TOP, X
        f.pack(fill=use_fill, side=use_side, pady='1m')

        self.RegisterUI(group, component, 'Boolean',
                        variable.get, variable.set)

    def PrefsOptionMenu(self, parent, label, group, component, options,
                        label_width=25, menu_width=6, variable=None):
        fr = Frame(parent)
        fr.pack(expand=1, fill=X)
        self.PrefsWidgetLabel(fr, label, label_width=label_width)
        if not variable:
            variable = StringVar(fr)
        menu = apply(OptionMenu, (fr, variable) + tuple(options))
        width = reduce(max, map(len, options), menu_width)
        menu.config(width=width, anchor=W)
        menu.pack(expand=1, fill=NONE, anchor=W)
        self.RegisterUI(group, component, 'string',
                        variable.get, variable.set)
        # This is probably overkill, but gets things updated
        # when the value actually changes:
        menu.bind("<Visibility>", self.poll_modified)

    def widget_set_func(self, widget):
        """Return routine to be used to set widget.
            
            The returned routine takes a single argument, the new setting."""
        v = StringVar(widget)
        widget.config(textvariable=v)
        return v.set

    def post(self, browser):
        """Called from menu interface to engage panel."""

        if not self.widget:
            self.create_widget()
        else:
            self.widget.deiconify()
            self.widget.tkraise()
        # Stash the browser from which we were last posted, in case the
        # panel code needs to know...
        self.browser = browser

        self.poll_modified()

    def create_widget(self):
        widget = self.widget = tktools.make_toplevel(
            self.frame, class_='Preferences')
        widget.title(self.title)
        widget.iconname("Grail Prefs")
        tktools.install_keybindings(widget)
        widget.bind('<Return>', self.done_cmd)
        widget.bind('<Key>', self.poll_modified)
        widget.bind("<Alt-w>", self.cancel_cmd)
        widget.bind("<Alt-W>", self.cancel_cmd)
        widget.bind("<Alt-Control-r>", self.reload_panel_cmd)
        widget.bind("<Alt-Control-d>", self.toggle_debugging)
        widget.bind('<ButtonPress>', self.poll_modified) # same as <Button>
        widget.bind('<ButtonRelease>', self.poll_modified)
        widget.protocol('WM_DELETE_WINDOW', self.cancel_cmd)

        width=80                        # Of the settings frame.

        fr, container, self.dispose_bar = tktools.make_double_frame(widget)

        # Do this before the panel container, so the buttons are squoze last:
        self.create_disposition_bar(self.dispose_bar)

        # Frame for the user to build within:
        self.framework_widget = container
        container.pack(side=TOP, fill=BOTH, expand=1, padx='2m', pady='2m') 

        # Do the user's setup:
        self.CreateLayout(self.name, container)

        # And now initialize the widget values:
        self.set_widgets()

        if self.app.prefs.GetBoolean('preferences', 'panel-debugging'):
            self.toggle_debugging(enable=1)

    def create_disposition_bar(self, bar):
        bartop = Frame(bar)
        bartop.pack()
        Frame(bar, height='1m').pack()
        barbottom = Frame(bar)
        barbottom.pack()
        self.debug_bar = Frame(bar, relief=SUNKEN)

        done_btn = Button(bartop, text="OK", command=self.done_cmd)
        help_btn = Button(barbottom, text="Help",
                          command=self.help_cmd)
        cancel_btn = Button(bartop, text="Cancel",
                            command=self.cancel_cmd)
        self.apply_btn = Button(barbottom, text="Apply",
                                command=self.apply_cmd)
        self.revert_btn = Button(barbottom, text="Revert",
                                 command=self.revert_cmd)
        self.factory_defaults_btn = Button(barbottom,
                                           command=self.factory_defaults_cmd,
                                           text="Defaults")
        tktools.unify_button_widths(done_btn, help_btn, cancel_btn,
                                    self.apply_btn, self.revert_btn,
                                    self.factory_defaults_btn)
        done_btn.pack(side=LEFT)
        # Can't just use anchor=CENTER to get help button centered - it'll
        # go to the TOP, above OK and Cancel buttons.  Expanding without
        # filling does what we want.
        self.apply_btn.pack(side=LEFT)
        Frame(barbottom).pack(side=LEFT, expand=1)
        help_btn.pack(side=LEFT)
        Frame(barbottom).pack(side=LEFT, expand=1)
        self.factory_defaults_btn.pack(side=LEFT)
        Frame(barbottom).pack(side=LEFT, expand=1)
        cancel_btn.pack(side=RIGHT)
        self.revert_btn.pack(side=RIGHT)

        bartop.pack(fill=BOTH)
        barbottom.pack(fill=BOTH)
        bar.pack(fill=BOTH, side=BOTTOM)

        reload_panel_btn = Button(self.debug_bar, text="Reload Panel",
                                  command=self.reload_panel_cmd)
        reload_preferences_btn = Button(self.debug_bar,
                                        text="Reload Preferences",
                                        command=self.reload_preferences_cmd)
        reload_panel_btn.pack(side=LEFT, expand=1)
        reload_preferences_btn.pack(side=RIGHT, expand=1)
        self.debugging = 0

    # Operational commands:
    def set_widgets(self, factory=0):
        """Initialize panel widgets with preference db values.

        Optional FACTORY true means use system defaults for values."""
        prefsgetter = getattr(self.app.prefs, 'GetTyped')
        for (g, c), (type_nm, uiget, uiset) in self.collection.items():
            try:
                uiset(prefsgetter(g, c, type_nm, factory))
            except TypeError, ValueError:
                e, v, tb = sys.exc_type, sys.exc_value, sys.exc_traceback
                self.app.root.report_callback_exception(e, v, tb)
        self.poll_modified()

    def done_cmd(self, event=None):
        """Conclude panel: commit and withdraw it."""
        self.apply_cmd(close=1)

    def help_cmd(self, event=None):
        """Dispatch browser on self.help_url."""
        if not self.app.browsers:
            print "No browser left to dislay help."
            return
        browser = self.helpbrowser
        if not browser or not browser.valid():
            import Browser
            browser = Browser.Browser(self.app.root, self.app)
            self.helpbrowser = browser
        helproot = self.app.prefs.Get('landmarks', 'grail-help-root')
        browser.context.load(urlparse.urljoin(helproot, self.HELP_URL))
        browser.root.tkraise()

    def apply_cmd(self, event=None, close=0):
        """Apply settings from panel to preferences."""
        self.widget.update_idletasks()

        prefsset = self.app.prefs.Set
        # Snarf the settings from the widgets:
        try:
            for (g, c), (type_nm, uiget, uiset) in self.collection.items():
                val = uiget()
                if (type(val) == StringType) and (type_nm != 'string'):
                    val = typify(val, type_nm)
                prefsset(g, c, val)
        except TypeError, ValueError:
            # Reject the value registered in the UI, notify, and fail save:
            e, v, tb = sys.exc_type, sys.exc_value, sys.exc_traceback
            self.app.root.report_callback_exception(e, v, tb)
            return 0
        if close:
            self.hide()
        self.app.prefs.Save()
        self.set_widgets()
        return 1

    def factory_defaults_cmd(self):
        """Reinit panel widgets with system-defaults preference db values."""
        self.set_widgets(factory=1)
        self.poll_modified()
        self.UpdateLayout()

    def revert_cmd(self):
        """Return settings to currently saved ones."""
        self.set_widgets()
        self.poll_modified()
        self.UpdateLayout()
        
    def cancel_cmd(self, event=None):
        self.hide()
        self.revert_cmd()

    def hide(self):
        self.Dismiss()
        self.widget.withdraw()

    def toggle_debugging(self, event=None, enable=0):
        """Include debug buttons - for, eg, reloading panel and prefs."""
        if self.debugging and not enable:
            self.debug_bar.forget()
            self.debugging = 0
        else:
            self.debug_bar.pack(fill=X, side=BOTTOM)
            self.debugging = 1

    def reload_panel_cmd(self, event=None):
        """Unadvertised routine for reloading panel code during development."""
        # Zeroing the entry for the module will force an import, which
        # will force a reload if the code has been modified.
        self.hide()
        self.app.prefs_panels.load(self.name, reloading=1)

    def reload_preferences_cmd(self, event=None):
        """Unadvertised routine for reloading preferences db.

        Note that callbacks are *not* processed."""
        self.app.prefs.load()
        self.poll_modified()
        self.UpdateLayout()

    # State mechanisms.

    def poll_modified(self, event=None):
        """Check for changes and enable disposition buttons accordingly."""
        # First, post an update for prompt user feedback:
        self.widget.update_idletasks()

        # Rectify disposition buttons if changes since last check:
        if self.modified_p():
            self.apply_btn.config(state='normal')
            self.revert_btn.config(state='normal')
        else:
            self.apply_btn.config(state='disabled')
            self.revert_btn.config(state='disabled')
        # Factory Defaults w.r.t. factory settings:
        if self.modified_p(factory=1):
            self.factory_defaults_btn.config(state='normal')
        else:
            self.factory_defaults_btn.config(state='disabled')

    def modified_p(self, factory=0):
        """True if any UI setting is changed from saved.

        Optional 'factory' keyword means check wrt system default settings."""

        prefsgettyped = getattr(self.app.prefs, 'GetTyped')
        prefsgetstr = getattr(self.app.prefs, 'Get')
        try:
            for (g, c), (type_nm, uiget, uiset) in self.collection.items():
                uival = uiget()
                if type_nm != 'string':
                    if type(uival) == StringType:
                        uival = typify(uival, type_nm)
                    if uival != prefsgettyped(g, c, type_nm, factory):
                        return 1
                elif uival != prefsgetstr(g, c, factory):
                    return 1
            return 0
        except TypeError:
            return 1

# Setup

class PrefsPanelsMenu:
    """Setup prefs panels and populate the browser menu."""

    def __init__(self, menu, browser):
        self.browser = browser
        self.app = browser.app
        self.menu = menu
        if hasattr(self.app, 'prefs_panels'):
            self.panels = self.app.prefs_panels.panels
        else:
            self.panels = {}
            self.app.prefs_panels = self
            for (nm, clnm, modnm, moddir) in self.discover_panel_modules():
                if not self.panels.has_key(nm):
                    # [module name, class name, directory, instance]
                    self.panels[nm] = [modnm, clnm, moddir, None]
        raworder = self.app.prefs.Get('preferences', 'panel-order')
        order = string.split(raworder)
        keys = self.panels.keys()
        ordered = []
        for name in order:
            if name in keys:
                ordered.append(name)
                keys.remove(name)
        keys.sort()
        for name in ordered + keys:
            # Enclose self and the name in a teeny leetle func:
            def poster(self=self, name=name):
                self.do_post(name)
            # ... which will be used to call the real posting routine:
            menu.add_command(label=name, command=poster)

    def discover_panel_modules(self):
        """Identify candidate panels.

        Return list of tuples describing found panel modules: (name,
        modname, moddir).

        Candidate modules must end in 'prefs.py' or 'prefs.pyc'.  The name
        is formed by extracting the prefix and substituting spaces for
        underscores (with leading and trailing spaces stripped).

        For multiple panels with the same name, the last one found is used."""
        got = {}
        for dir in panels_dirs:
            entries = []
            try:
                entries = os.listdir(dir)
            except os.error:
                # Optional dir not there.
                pass
            for entry in entries:
                if modname_matcher.match(entry) != -1:
                    name = regsub.gsub("_", " ", modname_matcher.group(1))
                    class_name = regsub.gsub("_", "",
                                             modname_matcher.group(1))
                    got[name] = ((string.strip(name), class_name, entry, dir))
        return got.values()
                    
    def do_post(self, name):
        """Expose the panel, creating it if necessary."""
        entry = self.panels[name]
        if entry[3]:
            # Already loaded:
            entry[3].post(self.browser)
        else:
            # Needs to be loaded:
            if self.load(name):
                self.do_post(name)

    def load(self, name, reloading=0):
        """Import the panel module and init the instance.

        Returns 1 if successful, None otherwise."""
        entry = self.panels[name]
        try:
            sys.path.insert(0, entry[2])
            try:
                modnm = entry[0][:string.index(entry[0], '.')]
                mod = __import__(modnm)
                if reload:
                    reload(mod)
                class_name = (regsub.gsub(" ", "", name)
                              + PANEL_CLASS_NAME_SUFFIX)
                # Instantiate it:
                entry[3] = getattr(mod, class_name)(name, self.app)
                return 1
            except:
                # Whatever may go wrong in import or panel post
                e, v, tb = sys.exc_type, sys.exc_value, sys.exc_traceback
                self.app.root.report_callback_exception(e, v, tb)
                return None
        finally:
            try:
                sys.path.remove(entry[1])
            except ValueError:
                pass

# Testing.

def standalone():
    """Provide standins for Grail objs so we can run outside of Grail."""
    class fake_browser:
        def __init__(self, root):
            self.app = self
            self.app.browsers = []
            self.prefs = grailbase.GrailPrefs.AllPreferences()
            self.root = root
            root.report_callback_exception = self.report_callback_exception
        def report_callback_exception(self, e, v, tb):
            print "Callback error: %s, %s" % (e, v)
            import traceback
            traceback.print_exception(e, v, tb)
        def register_on_exit(self, func): pass
        def unregister_on_exit(self, func): pass

    root = Frame()

    quitbutton = Button(root, text='quit')
    quitbutton.pack(side=LEFT)
    def quit(root=root): root.destroy(); sys.exit(0)
    quitbutton.config(command=quit)

    prefsbut = Menubutton(root, text="Preferences")
    prefsbut.pack(side=LEFT)
    prefsmenu = Menu(prefsbut)
    prefsbut['menu'] = prefsmenu
    root.pack(side=LEFT)

    browser = fake_browser(root)
    pdm = PrefsPanelsMenu(prefsmenu, browser)
    prefsmenu.mainloop()

if __name__ == "__main__":
    standalone()
