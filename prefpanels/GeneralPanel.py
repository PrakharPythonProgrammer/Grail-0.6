"""General Grail preferences panel."""

__version__ = "$Revision: 1.20 $"

# Base class for the panel:
import PrefsPanels

from Tkinter import *


class GeneralPanel(PrefsPanels.Framework):
    """Miscellaneous preferences relating to the browser, startup, and
    other behaviors that don't fit in specific preferences categories."""

    # Class var for help button - relative to grail-home-page.
    HELP_URL = "help/prefs/general.html"

    def CreateLayout(self, name, frame):

        # Home page: basic entry-based prefs can be as simple as this one:
        self.PrefsEntry(frame, 'Home page:', 'landmarks', 'home-page')

        self.PrefsCheckButton(frame, "Initial page:", "Load on Grail startup",
                              'browser', 'load-initial-page')

        # Geometry: more elaborate:
        f = Frame(frame)
        self.PrefsWidgetLabel(f, "Browser geometry:")
        # Pack some preferences entries together in a frame - we use the
        # PrefsEntry 'composite' feature here, to put them together on the
        # right-hand side of the label:
        tempfr = Frame(f, borderwidth=1)
        tempfr.pack(side=LEFT)
        entries_frame = Frame(tempfr, relief=SUNKEN, borderwidth=1)
        self.PrefsEntry(entries_frame,
                        "Width:", 'browser', 'default-width', 'int',
                        label_width=6, entry_width=4, composite=1)
        self.PrefsEntry(entries_frame,
                        "Height:", 'browser', 'default-height', 'int',
                        label_width=7, entry_width=4, composite=1)
        f.pack(fill=X, side=TOP, pady='1m')

        self.PrefsEntry(frame, 'Max. connections:', 'sockets', 'number', 'int',
                        entry_width=3) 

        self.PrefsCheckButton(frame, "Image loading:", "Load inline images",
                              'browser', 'load-images')

        self.PrefsCheckButton(frame,
                              "Link information:",
                              "Show title of link target, if known",
                              'presentation', 'show-link-titles')

        self.PrefsCheckButton(frame,
                              "HTML parsing:", "Advanced SGML recognition",
                              'parsing-html', 'strict')

        self.PrefsCheckButton(frame,
                              "Smooth scrolling:",
                              "Install smooth scrolling hack on new windows",
                              'browser', 'smooth-scroll-hack')

        self.PrefsCheckButton(frame,
                              "Distributed objects:", "Enable ILU main loop",
                              'security', 'enable-ilu')

        frame.pack()
 
        # History preference

        from History import VIEW_BY_TITLES, VIEW_BY_URLS

        viewby = StringVar(frame)
        viewbyframe = Frame(frame)
        viewbyframe.pack(fill=X, side=TOP, pady='1m')

        self.PrefsWidgetLabel(viewbyframe, 'View history items by:')

        byframe = Frame(viewbyframe, relief=SUNKEN, borderwidth=1)
        byframe.pack(side=LEFT)

        by_titles = Radiobutton(byframe, text='Titles',
                                variable=viewby,
                                value=VIEW_BY_TITLES)
        by_titles.pack(side=LEFT)

        by_urls = Radiobutton(byframe, text='URLs',
                              variable=viewby,
                              value=VIEW_BY_URLS)
        by_urls.pack(side=LEFT)

        self.RegisterUI('history', 'view-by', 'string',
                        viewby.get, viewby.set)
