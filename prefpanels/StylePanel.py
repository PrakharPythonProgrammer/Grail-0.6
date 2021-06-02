"""Grail style preferences panel."""

__version__ = "$Revision: 1.18 $"

# Base class for the panel:
import PrefsPanels

from tkinter import *



class ColorButton(Button):
    def __init__(self, master, cnf={}, **kw):
        kw["text"] = "Set"              # don't allow these to be provided
        #kw["font"] = "tiny"
        kw["background"] = kw.get("foreground")
        kw["highlightthickness"] = 0
        kw["command"] = self.__ask_color
        kw["cnf"] = cnf
        self.__master = master
        apply(Button.__init__, (self, master), kw)

    def get(self):
        return self.cget("foreground")

    def set(self, color):
        self.configure(foreground=color, background=color)

    def __ask_color(self):
        from pynche.pyColorChooser import askcolor
        rgb, name = askcolor(self.get(), master=self.__master)
        if rgb:
            self.set("#%02x%02x%02x" % rgb)


class StylePanel(PrefsPanels.Framework):
    """Panel for selecting viewer presentation styles."""

    HELP_URL = "help/prefs/styles.html"

    def CreateLayout(self, name, frame):

        style_sizes = str.split(self.app.prefs.Get('styles',
                                                      'all-sizes'))
        style_families = str.split(self.app.prefs.Get('styles',
                                                         'all-families'))

        self.PrefsRadioButtons(frame, "Font size group:", style_sizes,
                               'styles', 'size', label_width=20)
        self.PrefsRadioButtons(frame, "Font Family:", style_families,
                               'styles', 'family', label_width=20)
        # Anchors:

        v = StringVar(frame)
        f = Frame(frame)
        l = self.PrefsWidgetLabel(f, "Anchors:", label_width=20)
        cb = Checkbutton(f, text="Underline", borderwidth=1,
                         variable=v)
        cb.pack(side=LEFT)
        f.pack(fill=NONE, pady='1m', anchor=W)
        self.RegisterUI('styles-common', 'history-ahist-underline',
                        'Boolean', v.get, v.set)
        self.RegisterUI('styles-common', 'history-a-underline',
                        'Boolean', v.get, v.set)

        # Anchor colors:

        f = Frame(frame)
        l = self.PrefsWidgetLabel(f, "", label_width=20)
        self.__add_color(f, 'styles-common', 'history-a-foreground',
                         "Anchor color")
        self.__add_color(f, 'styles-common', 'history-ahist-foreground',
                         "Visited anchor color")
        self.__add_color(f, 'styles-common', 'history-atemp-foreground',
                         "Active anchor color")
        f.pack(fill=X, pady='1m', anchor=W)

        # Hovering behavior:

        f = Frame(frame)
        l = self.PrefsWidgetLabel(f, "Hovering:", label_width=20)
        hovering = BooleanVar(frame)
        vhover = BooleanVar(frame)
        Checkbutton(f, text="Enable hovering", borderwidth=1,
                    variable=hovering).pack(side=LEFT)
        Checkbutton(f, text="Underline when hovering", borderwidth=1,
                    variable=vhover).pack(side=LEFT)
        f.pack(fill=X, pady='1m', anchor=W)
        self.RegisterUI('presentation', 'hover-on-links',
                        'Boolean', hovering.get, hovering.set)
        self.RegisterUI('presentation', 'hover-underline',
                        'Boolean', vhover.get, vhover.set)

        f = Frame(frame)
        l = self.PrefsWidgetLabel(f, "", label_width=20)
        self.__add_color(f, 'presentation', 'hover-foreground',
                         "Hover  color")
        f.pack(fill=X, pady='1m', anchor=W)

        frame.pack()

    def __add_color(self, frame, prefgroup, prefname, description):
        b = ColorButton(frame)
        b.pack(side=LEFT)
        self.RegisterUI(prefgroup, prefname, 'string', b.get, b.set)
        Label(frame, text=" %s " % description).pack(side=LEFT)
