"""Search menu extension for Grail."""

from Tkinter import *


class SearchMenu:
    """Installation of a searching subitems in a top-level window.

    You must pass a menu on which to add the searching subitems, and
    the root window on which to install the keybindings.  You also
    need to pass in a `searchable' object, which is simply one that
    conforms to the following interface:

    search_for_pattern(pattern, regex_flag, case_flag, backwards_flag)
        Searchs for the pattern, returning true if the search
        succeeded, false if it failed.  This search module will ring
        the bell if no hit was found.

    """
    def __init__(self, menu, rootwin, searchable):
        self._searchable = searchable
        self._root = rootwin
        menu.add('command', label='Find...',
                 command=self.find_command,
                 underline=0, accelerator="Alt-F")
        self._root.bind('<Alt-f>', self.find_command)
        self._root.bind('<Alt-F>', self.find_command)
        menu.add('command', label='Find again',
                 command=self.find_again_command,
                 underline=6, accelerator="Alt-G")
        self._root.bind('<Alt-g>', self.find_again_command)
        self._root.bind('<Alt-G>', self.find_again_command)
        self.sdialog = None

    def find_command(self, event=None):
        self.create_dialog(1)

    def find_again_command(self, event=None):
        self.create_dialog(0)
        self.sdialog.search_command()

    def create_dialog(self, force=0):
        if not self.sdialog:
            self.sdialog = SearchDialog(self._root, self._searchable)
        elif force:
            self.sdialog._root.deiconify()
            self.sdialog.pat_entry.focus_set()
            self.sdialog.pat_entry.select_range(0, END)


class SearchDialog:

    def __init__(self, rootwin, searchable):
        self._searchable = searchable
        import tktools
        self._root = tktools.make_toplevel(rootwin, title="Search Dialog",
                                           class_="Search")
        self.create_widgets()
        tktools.set_transient(self._root, rootwin, rely=0.0)
        self.__rootwin = rootwin

    def create_widgets(self):
        import tktools
        x, f, self.bot_frame = tktools.make_double_frame(self._root)
        self.pat_entry, self.pat_frame = \
                        tktools.make_form_entry(f, None, name="entry")
        self.pat_entry['exportselection'] = 0
        self.pat_entry.bind('<Return>', self.return_event)
        self.pat_entry.focus_set()

        self.mid_frame = Frame(f)
        self.mid_frame.pack(fill=X)

        self.regexp_var = BooleanVar(f)
        self.case_var = BooleanVar(f)
        self.backwards_var = BooleanVar(f)

        self.regexp_checkbutton = Checkbutton(self._root, name="regexp",
                                              variable=self.regexp_var)
        self.regexp_checkbutton.pack(side=LEFT, in_=self.mid_frame)
        self.case_checkbutton = Checkbutton(self._root, name="casesens",
                                            variable=self.case_var)
        self.case_checkbutton.pack(side=LEFT, expand=1, in_=self.mid_frame)
        self.backwards_checkbutton = Checkbutton(self._root, name="backwards",
                                                 variable=self.backwards_var)
        self.backwards_checkbutton.pack(side=RIGHT, in_=self.mid_frame)

        # buttons along the bottom
        self.search_button = Button(self._root, name="search", width=12,
                                    command=self.search_command)
        self.search_button.pack(side=LEFT, in_=self.bot_frame)
        self.search_close_button = Button(self._root, name="searchclose",
                                          command=self.search_close_command)
        self.search_close_button.pack(side=LEFT, expand=1, padx='1m',
                                      in_=self.bot_frame) # Center
        self.close_button = Button(self._root, name="close", width=12,
                                   command=self.close_command)
        self.close_button.pack(side=RIGHT, in_=self.bot_frame)

        self._root.protocol('WM_DELETE_WINDOW', self.close_command)
        self._root.bind("<Alt-w>", self.close_event)
        self._root.bind("<Alt-W>", self.close_event)

    def return_event(self, event):
        self.search_close_command()

    def search_command(self):
        self.search()

    def search_close_command(self):
        if not self.search():
            return
        self.close_command()

    def close_event(self, event):
        self.close_command()

    def close_command(self):
        self.__rootwin.focus_set()
        self._root.withdraw()

    def search(self):
        pat = self.pat_entry.get()
        if not pat:
            self._root.bell()
            return 0
        status = self._searchable.search_for_pattern(
            pat, self.regexp_var.get(), self.case_var.get(),
            self.backwards_var.get())
        if not status:
            # failure
            # TBD: it would be better to bring up a Not Found notice
            self._root.bell()
        return status
