"""Grail cache preferences panel."""

__version__ = "$Revision: 1.14 $"

# Base class for the panel:
import PrefsPanels

from Tkinter import *
import tktools


class CachePanel(PrefsPanels.Framework):
    """Miscellaneous preferences relating to the browser, startup, and
    other behaviors that don't fit in specific preferences categories."""

    HELP_URL = "help/prefs/cache.html"

    def CreateRadioButtons(self, frame):
        verify_frame = Frame(frame)
        periodic_frame = Frame(verify_frame)
        l = Label(verify_frame, text="Verify document:")

        radio = StringVar(frame)
        always = Radiobutton(verify_frame,
                             text="Always",
                             variable=radio,
                             value='always')
        once = Radiobutton(verify_frame,
                           text="Once per session",
                           variable=radio,
                           value='once')
        never = Radiobutton(verify_frame,
                            text="Never",
                            variable=radio,
                            value='Never')

        period = Radiobutton(periodic_frame,
                             text="Every",
                             variable=radio,
                             value='periodic')
        e = Entry(periodic_frame, relief=SUNKEN, width=4)
        t = Label(periodic_frame, text="hours")

        period.pack(side=LEFT)
        t.pack(side=RIGHT)
        e.pack(side=RIGHT)
        periodic_frame.pack(side=BOTTOM)

        l.pack(side=LEFT)
        always.pack(side=LEFT)
        once.pack(side=LEFT)
        never.pack(side=LEFT)

        verify_frame.pack()

        self.RegisterUI('disk-cache', 'freshness-test-type', 'string',
                        radio.get, radio.set)

        self.RegisterUI('disk-cache', 'freshness-test-period', 'float',
                        e.get, self.widget_set_func(e))

    def CreateLayout(self, name, frame):

        # size plus clear buttons
        top_frame = Frame(frame)
        f = Frame(top_frame)
        l = Label(f, text="Size:")
        e = Entry(f, relief=SUNKEN, width=8)
        l2 = Label(f, text="KB")

        l.pack(side=LEFT)
        l2.pack(side=RIGHT)
        e.pack(side=RIGHT)
        f.pack(side=LEFT)

        clear = Button(top_frame,
                       text="Erase cache now",
                       command=self.app.url_cache.disk.erase_cache)
        repair = Button(top_frame,
                        text="Repair cache",
                        command=self.app.url_cache.disk.erase_unlogged_files)

        repair.pack(side=RIGHT)
        clear.pack(side=RIGHT)
        top_frame.pack()

        # Couple the widgets with the preferences:
        self.RegisterUI('disk-cache', 'size', 'int',
                        e.get, self.widget_set_func(e))

        # cache directory
        e, l, f = tktools.make_labeled_form_entry(frame, "Directory:")
        self.RegisterUI('disk-cache', 'directory', 'string',
                        e.get, self.widget_set_func(e))

        self.CreateRadioButtons(frame)

        frame.pack()
