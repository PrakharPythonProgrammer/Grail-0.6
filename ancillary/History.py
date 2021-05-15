"""Data structures for History manipulation"""

from Tkinter import *
import tktools
import string
import regex
import os
import sys
import time
from grailutil import *
from urlparse import urldefrag


class PageInfo:
    """This is the data structure used to represent a page in the
    History stack.  Each Browser object has it's own unique History
    stack which maintains volatile informatio about the page, to be
    restored when the page is re-visited via the history mechanism.
    For example, the state of any forms on the page, the entered and
    relocated URLs, or the scroll position are information that might
    be kept.

    A page can actually have 3 URL's associated with it.  First, the
    typed or clicked URL as it appears in the entry field or anchor,
    after relative URL resolution but before any server relocation
    errors.

    Second, the URL after relocation, possibly many steps of
    relocation.  Often this is to redirect a browser to the new
    location of a page, but more often it is to add a trailing slash
    on a page that lacks one.  In fact, there can be a relocation
    path, and you must watch for loops, but only the final resolved
    URL is of any significance.

    Third, if the pages contains a BASE tag, this URL is used in
    resolution of relative urls on this page.  Currently the base URL
    information is kept with the context object.
    """
    def __init__(self, url='', title='', scrollpos=1.0, formdata=None):
        self._url = url
        self._title = title
        self._scrollpos = scrollpos
        if formdata is None: formdata = []
        self._formdata = formdata

    def set_url(self, url): self._url = url
    def set_title(self, title): self._title = title
    def set_scrollpos(self, scrollpos): self._scrollpos = scrollpos
    def set_formdata(self, formdata): self._formdata = formdata

    def url(self): return self._url
    def title(self): return self._title
    def scrollpos(self): return self._scrollpos
    def formdata(self): return self._formdata

    def clone(self):
        return self.__class__(self._url, self._title,
                              self._scrollpos, self._formdata[:])



class DummyHistoryDialog:
    """Dummy so History can avoid testing for self._dialog != None."""
    def refresh(self): pass
    def select(self, index): pass

class History:
    def __init__(self):
        self._history = []
        self._dialog = DummyHistoryDialog()
        self._current = 0

    def clone(self):
        newhist = History()
        list = []
        for page in self._history:
            list.append(page.clone())
        newhist._history = list
        newhist._current = self._current
        return newhist

    def set_dialog(self, dialog):
        self._dialog = dialog

    def append_page(self, pageinfo):
        # Discard alternative futures.  Someday we might have `Cactus
        # History' or we might expose the Global History to the user.
        del self._history[self._current+1:]
        # We no longer check to see if the page has the same URL as
        # the previous page, because this introduced problems with
        # CGI scripts that produced different output for the same URL
        self._history.append(pageinfo)
        self._current = len(self._history)-1
        self._dialog.refresh()

    def page(self, index=None):
        if index is None: index = self._current
        if 0 <= index < len(self._history):
            self._current = index
            self._dialog.select(self._current)
            return self._history[self._current]
        else: return None

    def peek(self, offset=0, pos=None):
        if pos is None:
            pos = self._current
        i = pos + offset
        if 0 <= i < len(self._history):
            return i, self._history[i]
        else:
            return -1, None

    def current(self): return self._current
    def forward(self): return self.page(self._current+1)
    def back(self): return self.page(self._current-1)
    def pages(self): return self._history
    def refresh(self): self._dialog.refresh()



HISTORY_PREFGROUP = 'history'
VIEW_BY_PREF = 'view-by'
VIEW_BY_TITLES = 'titles'
VIEW_BY_URLS = 'urls'


class HistoryDialog:
    def __init__(self, context, historyobj=None):
        if not historyobj:
            # XXX I guess this is here for testing?  (It's used nowhere.)
            self._history = History()
        else:
            self._history = historyobj
        #
        self._context = context
        self._history.set_dialog(self)
        self._frame = tktools.make_toplevel(self._context.viewer.frame,
                                            class_="History",
                                            title="History Dialog")
        self._frame.protocol("WM_DELETE_WINDOW", self._close)
        # get preferences
        self._viewby = StringVar(self._frame)
        self._prefs = prefs = get_grailapp().prefs
        prefs.AddGroupCallback(HISTORY_PREFGROUP, self._notify)
        try:
            viewby = prefs.Get(HISTORY_PREFGROUP, VIEW_BY_PREF)
            if viewby not in [VIEW_BY_TITLES, VIEW_BY_URLS]:
                raise TypeError
        except (KeyError, TypeError):
            viewby = VIEW_BY_TITLES
        self._viewby.set(viewby)
        # add a couple of buttons
        btnbar = Frame(self._frame)
        btnbar.pack(fill=BOTH, side=BOTTOM)
        gotobtn = Button(self._frame, name='goto', command=self._goto)
        gotobtn.pack(side=LEFT, padx='1m', pady='1m', in_=btnbar)
        closebtn = Button(self._frame, name='close', command=self._close)
        closebtn.pack(side=LEFT, in_=btnbar)
        tktools.unify_button_widths(gotobtn, closebtn)
        # radio button for view option
        rbframe = Frame(btnbar)
        rbframe.pack()
        rb1 = Radiobutton(self._frame, name='titles',
                          command=self._viewby_command,
                          variable=self._viewby,
                          value=VIEW_BY_TITLES)
        rb2 = Radiobutton(self._frame, name='uris',
                          command=self._viewby_command,
                          variable=self._viewby,
                          value=VIEW_BY_URLS)
        rb1.pack(anchor='w', in_=rbframe)
        rb2.pack(anchor='w', in_=rbframe)
        # create listbox
        self._listbox, frame = tktools.make_list_box(
            self._frame, 40, 24, 1, 1, name="list")
        self.refresh()
        self._listbox.config(takefocus=0, exportselection=0)
        self._listbox.bind('<Double-Button-1>', self._goto)
        self._listbox.bind('<Double-Button-2>', self._goto_new)
        self._listbox.bind('<ButtonPress-2>', self._highlight)
        # Yes, yes, the mapping seems inverted, but it has to do with
        # the way history elements are displayed in reverse order in
        # the listbox.  These mappings mirror those used in the Bookmarks
        # dialog.
        self._frame.bind("<Right>", self.next_cmd)
        self._frame.bind("<Alt-Right>", self.next_cmd)
        self._frame.bind("<Left>", self.previous_cmd)
        self._frame.bind("<Alt-Left>", self.previous_cmd)
        self._frame.bind("<Up>", self.up_cmd)
        self._frame.bind("p", self.up_cmd)
        self._frame.bind("P", self.up_cmd)
        self._frame.bind("<Down>", self.down_cmd)
        self._frame.bind("n", self.down_cmd)
        self._frame.bind("N", self.down_cmd)
        self._frame.bind("g", self._goto)
        self._frame.bind("G", self._goto)
        self._frame.bind("<Return>", self._goto)
        self._frame.bind('<Alt-W>', self._close)
        self._frame.bind('<Alt-w>', self._close)
        tktools.set_transient(self._frame, self._context.root)

    def history(self): return self._history

    def _notify(self):
        viewby = self._prefs.Get(HISTORY_PREFGROUP, VIEW_BY_PREF)
        self._viewby.set(viewby)
        self.refresh()

    def refresh(self):
        # populate listbox
        self._listbox.delete(0, END)
        viewby = self._viewby.get()
        # view in reverse order
        pages = self._history.pages()[:]
        pages.reverse()
        for page in pages:
            url = page.url()
            title = page.title() or url
            if viewby == VIEW_BY_TITLES:
                docurl, frag = urldefrag(url)
                if frag and title <> url:
                    title = title + ' [%s]' % frag
                self._listbox.insert(END, title)
            elif viewby == VIEW_BY_URLS:
                self._listbox.insert(END, url)
        self.select(self._history.current())

    def previous_cmd(self, event=None):
        if self._history.back(): self._goto()
        else: self._frame.bell()
    def next_cmd(self, event=None):
        if self._history.forward(): self._goto()
        else: self._frame.bell()

    def up_cmd(self, event=None):
        if not self._history.forward():
            self._frame.bell()
    def down_cmd(self, event=None):
        if not self._history.back():
            self._frame.bell()

    def _load_url(self, which, context):
        selection = string.atoi(which)
        last = self._listbox.index(END)
        pos = last - selection - 1
        context.load_from_history(self._history.peek(pos=pos))

    def _goto(self, event=None):
        list = self._listbox.curselection()
        if len(list) > 0:
            self._load_url(list[0], self._context)

    def _goto_new(self, event=None):
        list = self._listbox.curselection()
        if len(list) > 0:
            from Browser import Browser
            browser = Browser(self._context.app.root, self._context.app)
            self._load_url(list[0], browser.context)

    def _highlight(self, event):
        self._listbox.select_clear(0, END)
        self._listbox.select_set('@%d,%d' % (event.x, event.y))

    def _close(self, event=None):
        self._frame.withdraw()

    def _viewby_command(self, event=None):
        self.refresh()

    def select(self, index):
        last = self._listbox.index(END)
        self._listbox.select_clear(0, END)
        self._listbox.select_set(last-index-1)
        self._listbox.activate(last-index-1)

    def show(self):
        self._frame.deiconify()
        self._frame.tkraise()
