"""Bookmarks and History preferences panel."""

__version__ = '$Revision: 1.11 $'

import PrefsPanels
from Tkinter import *
import tktools

from BookmarksGUI import \
     NEW_AT_BEG, \
     NEW_AT_END, \
     NEW_AS_CHILD, \
     BMPREFGROUP, \
     COLLAPSE_PREF, \
     INCLUDE_PREF, \
     ADDLOC_PREF, \
     AUTO_DETAILS_PREF, \
     BUTTONS_PREF


class BookmarksPanel(PrefsPanels.Framework):
    """Preferences for Bookmarks and History"""

    # class var for help button -- relative to the grail home page
    HELP_URL = 'help/prefs/bookmarks.html'

    def CreateLayout(self, name, frame):
        bmframe = frame

        self.PrefsCheckButton(bmframe, 'Bookmark Headers:',
                              'Collapse Aggressively',
                              BMPREFGROUP, COLLAPSE_PREF)

        addcurloc = StringVar(bmframe)
        addcur_frame = Frame(bmframe)
        addcur_frame.pack()
        label = Label(addcur_frame, text='Add Current Page:', width=25,
                      anchor=E)
        label.pack(side=LEFT, anchor=NE)
        f = Frame(addcur_frame, borderwidth=1)
        f.pack(side=LEFT)
        choices_frame = Frame(f, relief=SUNKEN, borderwidth=1)
        choices_frame.pack()

        prepends = Radiobutton(choices_frame, text='Prepends to File',
                               variable=addcurloc,
                               value=NEW_AT_BEG, anchor=W)
        prepends.pack(fill=X)

        appends = Radiobutton(choices_frame, text='Appends to File',
                              variable=addcurloc,
                              value=NEW_AT_END, anchor=W)
        appends.pack(fill=X)

        childsib = Radiobutton(choices_frame,
                               text="As Selection's Child or Sibling",
                               variable=addcurloc,
                               value=NEW_AS_CHILD, anchor=W)
        childsib.pack(fill=X)

        self.RegisterUI(BMPREFGROUP, ADDLOC_PREF, 'string',
                        addcurloc.get, addcurloc.set)

        autodetails = BooleanVar(bmframe)
        w = Checkbutton(f, text="Open Details Dialog", anchor=W,
                        variable=autodetails)
        w.pack(fill=X)
        self.RegisterUI(BMPREFGROUP, AUTO_DETAILS_PREF, 'Boolean',
                        autodetails.get, autodetails.set)

        self.PrefsCheckButton(bmframe, 'Bookmarks Dialog:',
                              'Show Optional Buttons',
                              BMPREFGROUP, BUTTONS_PREF)

        self.PrefsCheckButton(bmframe, "Browser's Pulldown Menu:",
                              'Includes Bookmark Entries',
                              BMPREFGROUP, INCLUDE_PREF)
