import bookmarks
import bookmarks.collection
import bookmarks.nodes

import FileDialog
import os
import stat
import string
import sys
import time
import tktools

from Tkinter import *
from grailutil import *
from Outliner import OutlinerViewer, OutlinerController


DEFAULT_NETSCAPE_BM_FILE = os.path.join(gethome(), '.netscape-bookmarks.html')
base = os.path.join(getgraildir(), 'grail-bookmarks.')
DEFAULT_GRAIL_BM_FILE_HTML = base + "html"
DEFAULT_GRAIL_BM_FILE_XBEL = base + "xml"
DEFAULT_GRAIL_BM_FILE = DEFAULT_GRAIL_BM_FILE_XBEL
del base

# Don't change this; this is the only one that makes sense here!
CACHE_FORMAT = "pickle"

BOOKMARKS_FILES = [
#    os.path.splitext(DEFAULT_GRAIL_BM_FILE)[0], # "native" pickled format
    DEFAULT_GRAIL_BM_FILE_XBEL,
    DEFAULT_GRAIL_BM_FILE_HTML,
    DEFAULT_NETSCAPE_BM_FILE,
    os.path.join(gethome(), '.netscape', 'bookmarks.html'), # Netscape 2.0
    ]

# allow for a separate environment variable GRAIL_BOOKMARKS_FILE, and
# search it first
try:
    file = os.environ['GRAIL_BOOKMARKS_FILE']
    file = os.path.expanduser(file)
    if file:
        BOOKMARKS_FILES.insert(0, file)
        if file <> DEFAULT_NETSCAPE_BM_FILE:
            DEFAULT_GRAIL_BM_FILE = file
except KeyError:
    pass


BMPREFGROUP = 'bookmarks'
ADDLOC_PREF = 'add-location'
COLLAPSE_PREF = 'aggressive-collapse'
INCLUDE_PREF = 'include-in-pulldown'
AUTO_DETAILS_PREF = 'open-details-on-add'
BUTTONS_PREF = 'show-navigation-buttons'


NEW_AT_BEG = 'file-prepend'
NEW_AT_END = 'file-append'
NEW_AS_CHILD = 'as-child-or-sib'


def username():
    try: name = os.environ['NAME'] + "'s"
    except KeyError:
        try:
            import pwd
            name = pwd.getpwuid(os.getuid())[4] + "'s"
        except (ImportError, AttributeError):
            name = 'Your'
    return name



class FileDialogExtras:
    def __init__(self, frame):
        # create a small subwindow for the extra buttons
        self._controls = Frame(frame, relief=GROOVE, borderwidth=2)
        self._controls.pack(fill=X)
        frame = Frame(self._controls)
        frame.pack(fill=X)
        label = Label(frame, text='Bookmark File Shortcuts:')
        label.pack(side=LEFT, anchor=W)
        grailbtn = Button(frame, text='Grail',
                          command=self.set_for_grail)
        netscapebtn = Button(frame, text='Netscape',
                             command=self.set_for_netscape)
        tktools.unify_button_widths(grailbtn, netscapebtn)
        netscapebtn.pack(side=RIGHT, padx='1m', pady='1m')
        grailbtn.pack(side=RIGHT)
        tktools.unify_button_widths(
            self.ok_button, self.filter_button, self.cancel_button)

    def _set_to_file(self, path):
        dir, file = os.path.split(path)
        olddir, pat = self.get_filter()
        self.set_filter(dir, pat)
        self.set_selection(file)
        self.filter_command()

    def set_for_grail(self): self._set_to_file(DEFAULT_GRAIL_BM_FILE)
    def set_for_netscape(self): self._set_to_file(DEFAULT_NETSCAPE_BM_FILE)


class BMLoadDialog(FileDialog.LoadFileDialog, FileDialogExtras):
    def __init__(self, master, controller):
        self._controller = controller
        FileDialog.LoadFileDialog.__init__(self, master, 'Load Bookmarks File')
        FileDialogExtras.__init__(self, self.top)


class BMSaveDialog(FileDialog.SaveFileDialog, FileDialogExtras):
    def __init__(self, master, controller):
        self._controller = controller
        FileDialog.SaveFileDialog.__init__(self, master, 'Save Bookmarks File')
        FileDialogExtras.__init__(self, self.top)
        self.__create_widgets(master)
        self.set_filetype(
            "html" or
            controller._app.prefs.Get("bookmarks", "default-save-format"))

    def __create_widgets(self, master):
        self.__filetype = StringVar(master)
        self.__export = BooleanVar(master)
        self.__export.set(0)
        frame = Frame(self._controls)
        frame.pack(fill=X)
        label = Label(frame, text='File Format:')
        label.pack(side=LEFT, anchor=W)
        options = OptionMenu(frame, self.__filetype,
                             "HTML", "XBEL")
        options["anchor"] = W
        options["width"] = 13
        options.pack(side=RIGHT)
        ckbox = Checkbutton(self._controls, variable=self.__export,
                            name="exportCheckbox")
        ckbox.pack(fill=X)

    def export(self):
        return self.__export.get()

    __charmap_out = string.maketrans(" ", "-")
    __charmap_in = string.maketrans("-", " ")
    def get_filetype(self):
        f = self.__filetype.get()
        f = string.translate(f, self.__charmap_out)
        f = string.lower(f)
        return f

    def set_filetype(self, filetype):
        dir, oldpat = self.get_filter()
        if filetype[:4] == "html":
            filetype = "HTML"
            pat = "*.html"
        elif filetype == "XBEL":
            pat = "*.xml"
        else:
            pat = "*.pkl"
        if pat != oldpat:
            self.set_filter(dir, pat)
        if filetype not in ("HTML", "XBEL"):
            filetype = string.capwords(
                string.translate(filetype, self.__charmap_in))
        self.__filetype.set(filetype)


class BookmarksIO:
    __format = None

    def __init__(self, frame, controller):
        self.__controller = controller
        self.__frame = frame

    def filename(self):
        return self.__controller._app.prefs.Get(
            BMPREFGROUP, "bookmark-file")
    def set_filename(self, filename):
        self.__controller._app.prefs.Set(
            BMPREFGROUP, "bookmark-file", filename)
        self.__controller._app.prefs.Save()

    def format(self):
        return self.__format
    def set_format(self, format):
        self.__format = format

    def __choose_reader(self, fp, what="file"):
        format = bookmarks.get_format(fp)
        if format:
            self.set_format(format)
            parser = bookmarks.get_parser_class(format)(self.filename())
            return bookmarks.BookmarkReader(parser)
        raise bookmarks.BookmarkFormatError(
            self.filename(), 'unknown or missing bookmarks', what=what)

    def __open_file_for_reading(self, filename):
        import errno
        try:
            fp = open(filename, 'r')
            return fp, self.__choose_reader(fp)
        except IOError, error:
            if error[0] == errno.ENOENT:
                # 'No such file or directory'
                raise
            raise bookmarks.BookmarkFormatError(filename, error)

    def __open_url_for_reading(self, url):
        import urllib
        try:
            from cStringIO import StringIO
        except ImportError:
            from StringIO import StringIO
        try:
            fp = urllib.urlopen(url)
            sio = StringIO(fp.read())
            fp.close()
            return sio, self.__choose_reader(sio)
        except IOError, error:
            raise bookmarks.BookmarkFormatError(url, error, what="URL")

    def load(self, usedefault=0, filename=None):
        req_filename = filename
        filename = filename or self.filename() or DEFAULT_GRAIL_BM_FILE
        if not (usedefault or req_filename):
            loader = BMLoadDialog(self.__frame, self.__controller)
            fname, ext = os.path.splitext(filename)
            filename = loader.go(filename, "*" + ext, key="bookmarks")
        cachename = (os.path.splitext(filename)[0]
                     + bookmarks.get_default_extension(CACHE_FORMAT))
        if (cachename != filename
            and os.path.isfile(filename)
            and os.path.isfile(cachename)):
            # cache exists; check it for currency:
            req_mtime = None
            mtime = 0
            try:
                fp = open(cachename)
                fp.readline()           # skip header
                fp.readline()           # skip embedded file name
                mtime = int(string.strip(fp.readline()))
                fp.close()
            except IOError:
                pass
            else:
                req_mtime = os.stat(filename)[stat.ST_MTIME]
            if mtime == req_mtime:
                # ok, the mtimes match; load the cache
                parser = bookmarks.get_parser_class(CACHE_FORMAT)(cachename)
                reader = bookmarks.BookmarkReader(parser)
                try:
                    fp = open(cachename, "rb")
                    root = reader.read_file(fp)
                except (IOError, bookmarks.BookmarkFormatError):
                    fp.close()
                else:
                    # get format of the original file:
                    fp = open(filename)
                    format = bookmarks.get_format(fp)
                    fp.close()
                    self.set_filename(filename)
                    self.set_format(format)
                    return root, reader
        # load the file
        root = reader = None
        if filename:
            try:
                fp, reader = self.__open_file_for_reading(filename)
            except IOError, error:
                # only ENOENT is passed through like this
                fp, reader = self.__open_url_for_reading(filename)
            root = reader.read_file(fp)
            fp.close()
            if not req_filename:
                # only set this if the filename wasn't passed in:
                self.set_filename(filename)
        return root, reader

    def __save_to_file(self, root, filename):
        try: os.rename(filename, filename+'.bak')
        except os.error: pass # no file to backup
        format = self.format()
        writer = bookmarks.get_writer_class(format)(root)
        fp = open(filename, 'w')
        writer.write_tree(fp)
        fp.close()
        # now save a cached copy:
        if format != CACHE_FORMAT:
            cachename = (os.path.splitext(filename)[0]
                         + bookmarks.get_default_extension(CACHE_FORMAT))
            mtime = os.stat(filename)[stat.ST_MTIME]
            writer = bookmarks.get_writer_class(CACHE_FORMAT)(root)
            # these only work on the cache format:
            writer.set_original_filename(filename)
            writer.set_original_mtime(mtime)
            # now write the cache, but just discard it on errors:
            try:
                fp = open(cachename, "wb")
                writer.write_tree(fp)
                fp.close()
            except IOError:
                try: os.unlink(cachename)
                except: pass

    def save(self, root):
        if not self.filename(): self.saveas(root)
        else: self.__save_to_file(root, self.filename())

    def saveas(self, root, export=0):
        filename = self.filename() or DEFAULT_GRAIL_BM_FILE
        saver = BMSaveDialog(self.__frame, self.__controller)
        saver.set_filetype(self.format())
        savefile = saver.go(filename, key="bookmarks")
        if savefile:
            self.set_format(saver.get_filetype())
            if saver.export():
                # remove the added/modified/visited information:
                import bookmarks.exporter
                collection = self.__controller._collection.copytree(root)
                root = collection.get_root()
                exporter = bookmarks.exporter.ExportWalker(root)
                exporter.walk()
            self.__save_to_file(root, savefile)
            if not export:
                self.set_filename(savefile)


class IOErrorDialog:
    def __init__(self, master, where, errmsg):
        msg = 'Bookmark file error encountered %s:' % where
        self._frame = tktools.make_toplevel(master, msg)
        self._frame.protocol('WM_DELETE_WINDOW', self.close)
        label = Label(self._frame, text=msg)
        label.pack()
        errlabel = Label(self._frame, text=errmsg)
        errlabel.pack()
        b = Button(self._frame, text="OK", command=self.close)
        b.pack()
        b.focus_set()
        b.config(default="active")
        self._frame.grab_set()

    def close(self):
        self._frame.grab_release()
        self._frame.destroy()



class TkListboxViewer(OutlinerViewer):
    def __init__(self, root, listbox):
        self._listbox = listbox
        OutlinerViewer.__init__(self, root)
        if len(self._nodes) > 0:
            self.select_node(0)
            self._listbox.activate(0)

    def _clear(self):
        self._listbox.delete(0, END)

    def _insert(self, node, index=None):
        if index is None: index = END
        nodetype = node.get_nodetype()
        if nodetype == "Folder":
            if node.expanded_p():
                title = "- " + (node.title() or "")
            else:
                title = "+ " + (node.title() or "")
        elif nodetype == "Alias":
            refnode = node.get_refnode()
            if refnode is None:
                title = "  <<unresolvable alias>>"
            elif refnode.get_nodetype() == "Folder":
                title = "> " + (refnode.title() or "")
            else:
                title = "  " + (refnode.title() or "")
        elif nodetype == "Separator":
            title = "  ------------------------------------"
        else:
            title = "  " + (node.title() or "")
        self._listbox.insert(index, "  "*(node.depth() - 1) + title)

    def _delete(self, start, end=None):
        if not end: self._listbox.delete(start)
        else: self._listbox.delete(start, end)

    def _select(self, index):
        last = self._listbox.index(END)
        if not (0 <= index < last): index = 0
        self._listbox.select_clear(0, END)
        self._listbox.select_set(index)
        self._listbox.activate(index)
        self._listbox.see(index)


class BookmarksDialog:
    def __init__(self, master, controller):
        # create the basic controls of the dialog window
        self._frame = tktools.make_toplevel(master, class_='Bookmarks')
        self._frame.title("Grail Bookmarks")
        self._frame.iconname("Bookmarks")
        self._frame.protocol('WM_DELETE_WINDOW', controller.hide)
        self._controller = controller
        infoframe = Frame(self._frame, name="info")
        infoframe.pack(fill=BOTH)
        self._title = Label(infoframe, text=controller.root().title(),
                            name="title")
        self._title.pack(fill=BOTH)
        self._file = Label(infoframe, text=controller.filename(),
                           name="file")
        self._file.pack(fill=BOTH)
        self._create_menubar()
        self._create_buttonbar()
        self._create_listbox()
        self._create_other_bindings()
        self._frame.focus_set()

    def _create_menubar(self):
        self._menubar = Frame(self._frame, class_="Menubar", name="menubar")
        self._menubar.pack(fill=X)
        #
        # file menu
        #
        filebtn = Menubutton(self._menubar, name="file")
        filebtn.pack(side=LEFT)
        filemenu = Menu(filebtn, name="menu")
        filemenu.add_command(label="Load...",
                             command=self.load,
                             underline=0, accelerator="Alt-L")
        self._frame.bind("<Alt-l>", self.load)
        self._frame.bind("<Alt-L>", self.load)
##      filemenu.add_command(label="Merge...",
##                           command=self._controller.merge,
##                           underline=0, accelerator="Alt-M")
##      self._frame.bind("<Alt-m>", self._controller.merge)
##      # Why can't I bind <Alt-M> here???!!!  I get a TclError...
##      # The "M" is short for the "Meta-" modifier.
##      self._frame.bind("<Alt-Shift-m>", self._controller.merge)
        filemenu.add_command(label="Save",
                             command=self._controller.save,
                             underline=0, accelerator="Alt-S")
        self._frame.bind("<Alt-s>", self._controller.save)
        self._frame.bind("<Alt-S>", self._controller.save)
        filemenu.add_command(label="Save As...",
                             command=self._controller.saveas)
        filemenu.add_command(label="Export Selection...",
                             command=self._controller.export)
        filemenu.add_command(label="Import Bookmarks...",
                             command=self._controller.importBookmarks,
                             underline=0, accelerator="Alt-I")
        self._frame.bind("<Alt-i>", self._controller.importBookmarks)
        self._frame.bind("<Alt-I>", self._controller.importBookmarks)
        filemenu.add_command(label="Title...",
                             command=self._controller.title_dialog,
                             underline=0, accelerator="Alt-T")
        self._frame.bind("<Alt-t>", self._controller.title_dialog)
        self._frame.bind("<Alt-T>", self._controller.title_dialog)
        filemenu.add_command(label="View Bookmarks in Grail",
                             command=self._controller.bookmark_goto,
                             underline=0, accelerator="Alt-V")
        self._frame.bind("<Alt-v>", self._controller.bookmark_goto)
        self._frame.bind("<Alt-V>", self._controller.bookmark_goto)
        filemenu.add_separator()
        filemenu.add_command(label="Close",
                             command=self._controller.hide,
                             underline=0, accelerator="Alt-W")
        self._frame.bind("<Alt-w>", self._controller.hide)
        self._frame.bind("<Alt-W>", self._controller.hide)
        filebtn.config(menu=filemenu)
        #
        # item menu
        #
        itembtn = Menubutton(self._menubar, name='item')
        itembtn.pack(side=LEFT)
        itemmenu = Menu(itembtn, name="menu")
        import SearchMenu
        SearchMenu.SearchMenu(itemmenu, self._frame, self._controller)
        itemmenu.add_separator()
        itemmenu.add_command(label="Add Current",
                             command=self._controller.add_current,
                             underline=0, accelerator='Alt-A')
        self._frame.bind("<Alt-a>", self._controller.add_current)
        self._frame.bind("<Alt-A>", self._controller.add_current)
        insertsubmenu = Menu(itemmenu, tearoff='No')
        insertsubmenu.add_command(label='Insert Separator',
                                  command=self._controller.insert_separator,
                                  underline=7, accelerator='S')
        self._frame.bind('s', self._controller.insert_separator)
        self._frame.bind('S', self._controller.insert_separator)
        insertsubmenu.add_command(label='Insert Header',
                                  command=self._controller.insert_header,
                                  underline=7, accelerator='H')
        self._frame.bind('h', self._controller.insert_header)
        self._frame.bind('H', self._controller.insert_header)
        insertsubmenu.add_command(label='Insert Link Entry',
                                  command=self._controller.insert_entry,
                                  underline=10, accelerator='K')
        self._frame.bind('k', self._controller.insert_entry)
        self._frame.bind('K', self._controller.insert_entry)
        itemmenu.add_cascade(label='Insert', menu=insertsubmenu)
        itemmenu.add_command(label='Make Alias',
                             command=self._controller.make_alias)
        itemmenu.add_command(label='Remove Entry',
                             command=self._controller.remove_entry,
                             accelerator='X')
        self._frame.bind('x', self._controller.remove_entry)
        self._frame.bind('X', self._controller.remove_entry)
        itemmenu.add_separator()
        itemmenu.add_command(label="Details...",
                             command=self._controller.details,
                             underline=0, accelerator="Alt-D")
        self._frame.bind("<Alt-d>", self._controller.details)
        self._frame.bind("<Alt-D>", self._controller.details)
        itemmenu.add_command(label="Go To Bookmark",
                             command=self._controller.goto,
                             underline=0, accelerator="G")
        self._frame.bind("g", self._controller.goto)
        self._frame.bind("G", self._controller.goto)
        self._frame.bind("<KeyPress-space>", self._controller.goto)
        itemmenu.add_command(label="Go in New Window",
                             command=self._controller.goto_new)
        itembtn.config(menu=itemmenu)
        #
        # arrange menu
        #
        arrangebtn = Menubutton(self._menubar, name="arrange")
        arrangebtn.pack(side=LEFT)
        arrangemenu = Menu(arrangebtn, name="menu")
        arrangemenu.add_command(label="Expand",
                            command=self._controller.expand_cmd,
                            underline=0, accelerator="E")
        self._frame.bind("e", self._controller.expand_cmd)
        self._frame.bind("E", self._controller.expand_cmd)
        arrangemenu.add_command(label="Collapse",
                            command=self._controller.collapse_cmd,
                            underline=0, accelerator="C")
        self._frame.bind("c", self._controller.collapse_cmd)
        self._frame.bind("C", self._controller.collapse_cmd)
        arrangemenu.add_separator()
        arrangemenu.add_command(label='Shift Entry Left',
                             command=self._controller.shift_left_cmd,
                             underline=12, accelerator='L')
        self._frame.bind('l', self._controller.shift_left_cmd)
        self._frame.bind('L', self._controller.shift_left_cmd)
        arrangemenu.add_command(label='Shift Entry Right',
                             command=self._controller.shift_right_cmd,
                             underline=12, accelerator='R')
        self._frame.bind('r', self._controller.shift_right_cmd)
        self._frame.bind('R', self._controller.shift_right_cmd)
        arrangemenu.add_command(label='Shift Entry Up',
                             command=self._controller.shift_up_cmd,
                             underline=12, accelerator='U')
        self._frame.bind('u', self._controller.shift_up_cmd)
        self._frame.bind('U', self._controller.shift_up_cmd)
        arrangemenu.add_command(label='Shift Entry Down',
                             command=self._controller.shift_down_cmd,
                             underline=12, accelerator='D')
        self._frame.bind('d', self._controller.shift_down_cmd)
        self._frame.bind('D', self._controller.shift_down_cmd)
        arrangebtn.config(menu=arrangemenu)
        self._frame.bind("<Up>", self._controller.previous_cmd)
        self._frame.bind("p", self._controller.previous_cmd)
        self._frame.bind("P", self._controller.previous_cmd)
        self._frame.bind("<Down>", self._controller.next_cmd)
        self._frame.bind("n", self._controller.next_cmd)
        self._frame.bind("N", self._controller.next_cmd)

    def _create_listbox(self):
        self._listbox, frame = tktools.make_list_box(self._frame,
                                                     60, 24, 1, 1)
        self._listbox.config(font='fixed')
        # bind keys
        self._listbox.bind('<ButtonPress-2>', self._highlight)
        self._listbox.bind('<Double-Button-1>', self._controller.goto)
        self._listbox.bind('<Double-Button-2>', self._controller.goto_new)
        self._listbox.config(takefocus=0, exportselection=0)

    def _create_buttonbar(self):
        # create the button bars
        btmframe = Frame(self._frame)
        btmframe.pack(side=BOTTOM, fill=BOTH)
        topframe = Frame(self._frame)
        # bottom buttonbar buttons
        okbtn = Button(self._frame, name='ok', command=self.okay_cmd)
        okbtn.pack(side=LEFT, in_=btmframe)
        savebtn = Button(self._frame, name='save', command=self.save_cmd)
        savebtn.pack(side=LEFT, in_=btmframe)
        self._frame.bind("<Return>", self.okay_cmd)
        status = Label(self._frame, name="status",
                       textvariable=self._controller.statusmsg)
        status.pack(side=LEFT, expand=1, fill=BOTH, in_=btmframe)
        cancelbtn = Button(self._frame, name='cancel', command=self.cancel_cmd)
        cancelbtn.pack(side=RIGHT, in_=btmframe)
        self._frame.bind('<Alt-w>', self.cancel_cmd)
        self._frame.bind('<Alt-W>', self.cancel_cmd)
        self._frame.bind('<Control-c>', self.cancel_cmd)
        self._frame.bind('<Control-C>', self.cancel_cmd)
        # top buttonbar buttons
        self._optional_frame = topframe
        prevbtn = Button(self._frame, name='prev',
                         command=self._controller.previous_cmd)
        nextbtn = Button(self._frame, name='next',
                         command=self._controller.next_cmd)
        prevbtn.pack(side=LEFT, expand=1, fill=BOTH, in_=topframe)
        nextbtn.pack(side=LEFT, expand=1, fill=BOTH, in_=topframe)
        gotobtn = Button(self._frame, name='goto',
                         command=self._controller.goto)
        gotobtn.pack(side=LEFT, expand=1, fill=BOTH, in_=topframe)
        colbtn = Button(self._frame, name='collapse',
                        command=self._controller.collapse_cmd)
        expbtn = Button(self._frame, name='expand',
                        command=self._controller.expand_cmd)
        colbtn.pack(side=LEFT, expand=1, fill=BOTH, in_=topframe)
        expbtn.pack(side=LEFT, expand=1, fill=BOTH, in_=topframe)
        self.update_prefs()

    _optional_buttons_packed = 0

    def update_prefs(self):
        pack = self._controller.optionalbuttons.get()
        if self._optional_buttons_packed != pack:
            if pack:
                self._optional_frame.pack(side=BOTTOM, fill=BOTH)
            else:
                self._optional_frame.forget()
            self._optional_buttons_packed = pack

    def _create_other_bindings(self):
        # bindings not associated with menu entries or buttons
        w = self._frame
        w.bind("<Home>", self._controller.shift_to_top_cmd)
        w.bind("<End>", self._controller.shift_to_bottom_cmd)

    def set_modflag(self, flag):
        if flag: text = '<== Changes are unsaved!'
        else: text = ''
        self._controller.statusmsg.set(text)

    def load(self, event=None):
        try:
            self._controller.load()
        except IOError, errmsg:
            IOErrorDialog(self._frame, 'during loading', errmsg)
        except bookmarks.BookmarkFormatError, e:
            IOErrorDialog(self._frame, 'during loading', e.problem)

    def show(self):
        self._frame.deiconify()
        self._frame.tkraise()
        self._frame.focus_set()

    def save_cmd(self, event=None):
        self._controller.save()
    def okay_cmd(self, event=None):
        self._controller.save()
        self._controller.hide()
    def cancel_cmd(self, event=None):
        self._controller.revert()
        self._controller.hide()

    def hide(self):
        browser = self._controller.get_browser()
        if browser:
            browser.root.focus_set()
        self._frame.withdraw()

    def visible_p(self):
        return self._frame.state() <> 'withdrawn'

    def set_labels(self, filename, title):
        self._file.config(text=filename)
        self._title.config(text=title)

    def _highlight(self, event):
        self._listbox.select_clear(0, END)
        self._listbox.select_set('@%d,%d' % (event.x, event.y))


class DetailsDialog:
    def __init__(self, master, node, controller):
        self._frame = tktools.make_toplevel(master, class_='Detail',
                                            title="Bookmark Details")
        self._frame.protocol('WM_DELETE_WINDOW', self.cancel)
        self._node = node
        self._controller = controller
        fr, top, bottom = tktools.make_double_frame(self._frame)
        self._create_form(top)
        self._create_buttonbar(bottom)
        self._frame.bind('<Return>', self.done)
        self._frame.bind('<Alt-W>', self.cancel)
        self._frame.bind('<Alt-w>', self.cancel)
        self._frame.bind('<Control-c>', self.cancel)
        self._frame.bind('<Control-C>', self.cancel)
        self._title.focus_set()

    def _create_form(self, top):
        is_root = self._node is self._controller.root()
        self._form = []
        self._title = self._add_field(top, 'Name', 40)
        if self._node.get_nodetype() == "Bookmark":
            self._location = self._add_field(top, 'Location', 40)
            self._visited = self._add_field(top, 'Last Visited', 40)
            self._modified = self._add_field(top, 'Last Modified', 40)
        else:
            self._location = None
            self._visited = None
            self._modified = None
        if is_root:
            self._added_on = None
        else:
            self._added_on = self._add_field(top, 'Added On', 40)
        self._description = self._add_field(top, 'Description', 40, 5)
        self.revert()

    def _add_field(self, master, label, width, height=1):
        entry, frame, label = tktools.make_labeled_form_entry(
            master, label, width, height, 12, takefocus=0)
        return entry

    def _create_buttonbar(self, top):
        btnbar = Frame(top)
        donebtn = Button(top, name='ok', command=self.done)
        applybtn = Button(top, name='apply', command=self.apply)
        cancelbtn = Button(top, name='cancel', command=self.cancel)
        tktools.unify_button_widths(donebtn, applybtn, cancelbtn)
        donebtn.pack(side=LEFT, in_=btnbar)
        applybtn.pack(side=LEFT, padx='1m', in_=btnbar)
        cancelbtn.pack(side=RIGHT, in_=btnbar)
        btnbar.pack(fill=BOTH)

    def revert(self):
        # fill in the entry fields
        self._title.delete(0, END)
        self._title.insert(0, self._node.title())
        self._title.select_range(0, END)
        if self._node.get_nodetype() == "Bookmark":
            self._location.delete(0, END)
            self._location.insert(0, self._node.uri())
        self._description.delete(1.0, END)
        self._description.insert(END, self._node.description() or "")
        self.update_timestamp_fields()

    def update_timestamp_fields(self):
        set_timestamp = self._set_timestamp_field
        if self._visited:
            set_timestamp(self._visited,  self._node.last_visited())
        if self._added_on:
            set_timestamp(self._added_on, self._node.add_date())
        if self._modified:
            set_timestamp(self._modified, self._node.last_modified())

    def _set_timestamp_field(self, entry, t):
        entry.config(state=NORMAL)
        entry.delete(0, END)
        if t:
            entry.insert(0, time.ctime(t))
        entry.config(state=DISABLED)

    def apply(self):
        self._node.set_title(self._title.get())
        if self._node.get_nodetype() == "Bookmark":
            old_uri = self._node.uri()
            new_uri = self._location.get()
            if new_uri != old_uri:
                collection = self._controller._collection
                collection.del_node(self._node)
                self._node.set_uri(new_uri)
                collection.add_Bookmark(self._node)
        self._node.set_description(self._description.get(1.0, END))
        if self._node is self._controller.root():
            self._controller.update_title_node()
        else:
            self._controller.viewer().update_node(self._node)
            self._controller.viewer().select_node(self._node)
        self._controller.set_modflag(1)

    def cancel(self, event=None):
        self.revert()
        self.hide()

    def done(self, event=None):
        self.apply()
        self.hide()

    def show(self):
        self._frame.deiconify()
        self._frame.tkraise()
        self._title.focus_set()

    def hide(self):
        # these two calls are order dependent!
        self._controller.focus_on_dialog()
        self._frame.withdraw()

    def destroy(self):
        self._frame.destroy()
        self._controller = self._node = None



class BookmarksController(OutlinerController):
    _initialized_p = 0
    _active = 0
    _dialog = None
    _listbox = None

    def __init__(self, app):
        default_root = bookmarks.nodes.Folder()
        default_root.set_title(username() + " Bookmarks")
        OutlinerController.__init__(self, default_root)
        self._master = master = app.root
        self._app = app
        self._iomgr = BookmarksIO(master, self)
        self._details = {}
        self._menus = []
        #
        self.aggressive = BooleanVar(master)
        self.addcurloc =  StringVar(master)
        self.fileformat = StringVar(master)
        self.statusmsg = StringVar(master)
        self.includepulldown = BooleanVar(master)
        self.optionalbuttons = BooleanVar(master)
        self.autodetails = BooleanVar(master)
        #
        # get preferences and set the values
        self._prefs = prefs = app.prefs
        prefs.AddGroupCallback(BMPREFGROUP, self._notify)
        self._notify()
        # other initializations
        self.fileformat.set('Automatic')
        self.statusmsg.set('')
        self._modflag = 0
        app.register_on_exit(self.on_app_exit)

    def _notify(self):
        prefs = self._app.prefs
        try:
            where = prefs.Get(BMPREFGROUP, ADDLOC_PREF)
            if where not in [NEW_AT_BEG, NEW_AT_END, NEW_AS_CHILD]:
                raise TypeError
        except (TypeError, KeyError):
            where = NEW_AT_BEG
        self.addcurloc.set(where)
        self.aggressive.set(self.__get_boolean_pref(COLLAPSE_PREF))
        self.includepulldown.set(self.__get_boolean_pref(INCLUDE_PREF))
        self.optionalbuttons.set(self.__get_boolean_pref(BUTTONS_PREF))
        self.autodetails.set(self.__get_boolean_pref(AUTO_DETAILS_PREF))
        if self._dialog:
            self._dialog.update_prefs()

    def __get_boolean_pref(self, option, default=0):
        try:
            return self._app.prefs.GetBoolean(BMPREFGROUP, option) and 1 or 0
        except (TypeError, KeyError):
            return default and 1 or 0

    def add_watched_menu(self, menu):
        self._menus.append(menu)

    def remove_watched_menu(self, menu):
        self._menus.remove(menu)
        
    def set_browser(self, browser=None):
        self._active = browser

    def get_browser(self):
        if self._active not in self._app.browsers:
            try:
                self._active = self._app.browsers[-1]
            except IndexError:
                self._active = None     # all browsers have been closed
        return self._active

    ## coordinate with Application instance

    def on_app_exit(self):
        if self._modflag: self.save(exiting=1)
        self._app.unregister_on_exit(self.on_app_exit)

    ## Modifications updating
    def set_modflag(self, flag, quiet=0):
        if not quiet:
            if self._dialog:
                self._dialog.set_modflag(flag)
            for menu in self._menus:
                menu.set_modflag(flag)
        self._modflag = flag

    ## I/O

    def initialize(self):
        if self._initialized_p:
            return
        # Attempt to read each bookmarks file in the BOOKMARKS_FILES list.
        root = None
        filenames = BOOKMARKS_FILES[:]
        fn = self._iomgr.filename()
        if fn:
            filenames.insert(0, fn)
        for file in filenames:
            self._iomgr.set_filename(file)
            try:
                root, reader = self._iomgr.load(usedefault=1)
                break
            except bookmarks.BookmarkFormatError:
                pass
        if not root:
            root = bookmarks.nodes.Folder()
            root.set_title(username() + " Bookmarks")
            self._iomgr.set_filename(DEFAULT_GRAIL_BM_FILE)
        self.set_root(root)
        self._collection = bookmarks.collection.Collection(root)
        self._initialized_p = 1

    def _on_new_root(self):
        for dialog in self._details.values(): dialog.destroy()
        self._details = {}
        self.set_viewer(TkListboxViewer(self.root(), self._listbox))
        self.root_redisplay()
        # set up new state
        node = self.viewer().node(0)
        self.set_modflag(0)
        if node: self.viewer().select_node(node)
        self._collection = bookmarks.collection.Collection(self.root())

    def load(self, usedefault=0):
        root, reader = self._iomgr.load(usedefault=usedefault)
        if not root and not reader:
            # load dialog was cancelled
            return
        self._dialog.set_labels(self._iomgr.filename(), root.title())
        # clear out all the old state
        self.set_root(root)
        self._on_new_root()

    def revert(self):
        OutlinerController.revert(self)
        self._on_new_root()

    def save(self, event=None, exiting=0):
        # if it hasn't been modified, it doesn't need saving
        if not self.set_modflag: return
        self._iomgr.save(self._root)
        self.set_modflag(0)
        self.update_backup()
        if self._dialog and not exiting:
            self._dialog.set_labels(self._iomgr.filename(), self._root.title())

    def saveas(self, event=None):
        # always save-as, even if unmodified
        self._iomgr.saveas(self._root)
        self.set_modflag(0)
        self.update_backup()
        if self._dialog:
            self._dialog.set_labels(self._iomgr.filename(), self._root.title())

    def export(self, event=None):
        # save the selected node
        node, selection = self._get_selected_node()
        if node:
            self._iomgr.saveas(node, export=1)

    def importBookmarks(self, event=None):
        # need to get URL or filename here...
        import OpenURIDialog
        dialog = OpenURIDialog.OpenURIDialog(
            self._master, title="Import Bookmarks Dialog", new=0)
        filename, new = dialog.go()
        if not filename:
            return
        node, reader = self._iomgr.load(filename=filename)
        if not node:
            return
        node.set_add_date(int(time.time()))
        if not node.title():
            node.set_title("Imported bookmarks from " + filename)
        parent, at_end = self.get_insertion_info()
        self._collection.merge_node(node, parent)
        if not at_end:
            parent.insert_child(node, 0)
        self.root_redisplay()
        self.set_modflag(1)
        self.viewer().select_node(node)
        if self.autodetails.get():
            self.show_details(node)

    # Other commands

    def set_listbox(self, listbox): self._listbox = listbox
    def set_dialog(self, dialog): self._dialog = dialog
    def filename(self): return self._iomgr.filename()
    def dialog_is_visible_p(self):
        return self._dialog and self._dialog.visible_p()

    def get_type_counts(self):
        return self._collection.get_type_counts()

    def get_bookmarks_by_uri(self, uri):
        self.initialize()
        return self._collection.get_bookmarks_by_uri(uri)

    def record_visit(self, uri, last_modified):
        bookmarks = self.get_bookmarks_by_uri(uri)
        if bookmarks:
            now = int(time.time())
            for bookmark in bookmarks:
                bookmark.set_last_visited(now)
                if last_modified:
                    # If we set this unconditionally, we lose information when
                    # the page is loaded from the cache.  This is a problem
                    # with the Grail cache machinery, and probably isn't worth
                    # fixing. ;-(
                    bookmark.set_last_modified(last_modified)
                if self._details.has_key(id(bookmark)):
                    self._details[id(bookmark)].update_timestamp_fields()
            self.set_modflag(1, quiet=1)

    def focus_on_dialog(self):
        self._dialog and self._dialog.show()

    def _get_selected_node(self):
        node = selection = None
        try:
            list = self._listbox.curselection()
            if len(list) > 0:
                selection = string.atoi(list[0])
                return self.viewer().node(selection), selection
        except AttributeError: pass
        return node, selection

    def toggle_node_expansion(self, node):
        if node.expanded_p(): self.collapse_node(node)
        else: self.expand_node(node)
        self.viewer().select_node(node)
        self.set_modflag(1, quiet=1)

    def goto(self, event=None):
        node, selection = self._get_selected_node()
        if not node: return
        if node.leaf_p():
            self.goto_node(node)
        else:
            self.toggle_node_expansion(node)

    def goto_new(self, event=None):
        node, selection = self._get_selected_node()
        if not node: return
        if node.leaf_p():
            from Browser import Browser
            self.goto_node(node, Browser(self._app.root, self._app))
        else:
            self.toggle_node_expansion(node)

    def bookmark_goto(self, event=None):
        browser = self.get_browser()
        if not browser:
            return
        filename = self._iomgr.filename()
        if filename and os.path.splitext(filename)[1] in (".html", ".htm"):
            browser.context.load('file:' + filename)
        else:
            # clear out the viewer to a "new page"
            browser.context.save_page_state()
            browser.context.clear_reset()
            # display the bookmarks the hard way:
            BookmarksFormatter(browser, self.root())

    def goto_node(self, node, browser=None):
        nodetype = node and node.get_nodetype()
        if nodetype == "Bookmark" and node.uri():
            self.visit_node(node, browser)
            self.viewer().select_node(node)
        elif nodetype == "Alias":
            refnode = node.get_refnode()
            if refnode is None:
                return
            nodetype = refnode.get_nodetype()
            if nodetype == "Bookmark":
                self.visit_node(refnode, browser=browser)
                self.viewer().select_node(node)
            else:
                # move to the actual folder and expand:
                self.expand_node(refnode)
                self.viewer().select_node(refnode)

    def visit_node(self, node, browser=None):
        if browser is None:
            browser = self.get_browser()
            if browser is None:
                return
        browser.context.load(node.uri())
        self.set_modflag(1, quiet=1)

    def insert_node(self, node):
        addlocation = self.addcurloc.get()
        parent, at_end = self.get_insertion_info()
        if not parent:
            return
        if at_end:
            parent.append_child(node)
        else:
            parenr.insert_child(node, 0)
        # scroll the newly added node into view
        self.set_modflag(1)
        self.root_redisplay()
        self.viewer().select_node(node)

    def get_insertion_info(self):
        """Return folder to insert info, and flag indicating which end."""
        addlocation = self.addcurloc.get()
        if addlocation == NEW_AT_END:
            return self.root(), 1
        if addlocation == NEW_AT_BEG:
            return self.root(), 0
        if addlocation == NEW_AS_CHILD:
            snode, selection = self._get_selected_node()
            # if no node was selected, then just insert it at the top.
            if not snode:
                return self.root(), 0
            nodetype = snode.get_nodetype()
            if nodetype in ("Bookmark", "Separator"):
                return snode.parent(), 1
            if nodetype == "Alias":
                if snode.get_refnode().get_nodetype() == "Bookmark":
                    return snode.parent(), 1
                else:
                    # refers to a Folder
                    return snode.get_refnode(), 1
            # snode is a Folder
            snode.expand()
            return snode, 1
        return None, 0

    def make_alias(self, event=None):
        node, selection = self._get_selected_node()
        if node and node.get_nodetype() in ("Bookmark", "Folder"):
            id = node.id()
            if not id:
                node.set_id(self._collection.new_id())
            self.insert_node(bookmarks.nodes.Alias(node))

    def add_current(self, event=None):
        # create a new node for the page in the current browser
        browser = self.get_browser()
        if browser is None:
            return
        title = browser.context.get_title()
        url = browser.context.get_baseurl()
        node = self.add_link(url, title)
        headers = browser.context.get_headers()
        if headers.has_key("last-modified"):
            modified = headers["last-modified"]
            if type(modified) is type(''):
                import ht_time
                try:
                    modified = ht_time.parse(modified)
                except:
                    pass
                else:
                    node.set_last_modified(modified)

    def add_link(self, url, title=''):
        # create a new node to represent this addition and then fit it
        # into the tree, updating the listbox
        now = int(time.time())
        title = title or self._app.global_history.lookup_url(url)[0] or url
        node = bookmarks.nodes.Bookmark()
        node.set_title(title)
        node.set_uri(url)
        node.set_add_date(now)
        node.set_last_visited(now)
        self.insert_node(node)
        self._collection.add_Bookmark(node)
        if self.autodetails.get():
            self.show_details(node)
        return node

    def details(self, event=None):
        node, selection = self._get_selected_node()
        self.show_details(node)

    def show_details(self, node):
        if not node or node.get_nodetype() == "Separator": return
        if node.get_nodetype() == "Alias":
            node = node.get_refnode()
            if node is None:
                # need error dialog here
                return
        if self._details.has_key(id(node)):
            details = self._details[id(node)]
            details.show()
        else:
            details = DetailsDialog(self._dialog._frame, node, self)
            self._details[id(node)] = details

    def title_dialog(self, event=None):
        self.show_details(self.root())

    def update_title_node(self):
        self._dialog.set_labels(self._iomgr.filename(), self.root().title())

    def show(self, event=None):
        # note that due to a weird Tk `buglet' if you do a deiconify
        # on a newly created toplevel widget, it causes a roundtrip
        # with the X server too early in the widget creation cycle.
        # for those window managers without automatic (random)
        # placement, the user will see a zero-sized widget
        show_p = 1
        if not self._dialog:
            self._dialog = BookmarksDialog(self._master, self)
            self._listbox = self._dialog._listbox # TBD: gross
            viewer = TkListboxViewer(self.root(), self._listbox)
            self.set_viewer(viewer)
            viewer.populate()
            if viewer.count() > 0: viewer.select_node(viewer.node(0))
            show_p = 0
        if show_p: self._dialog.show()

    def hide(self, event=None): self._dialog.hide()
    def quit(self, event=None): sys.exit(0)

    def _insert_at_node(self, node, newnode):
        if node.leaf_p() or not node.expanded_p():
            parent, sibi, sibs = self._sibi(node)
            if not parent: return
            parent.insert_child(newnode, sibi+1)
        else:
            # Mimic Netscape behavior: when a separator is added to a
            # header, the node is added as the header's first child.
            # If the header is collapsed, it is first expanded.
            node.expand()
            node.insert_child(newnode, 0)
        self.root_redisplay()
        self.viewer().select_node(newnode)
        self.set_modflag(1)

    def insert_separator(self, event=None):
        node, selection = self._get_selected_node()
        if not node: return
        newnode = bookmarks.nodes.Separator()
        self._insert_at_node(node, newnode)

    def insert_header(self, event=None):
        node, selection = self._get_selected_node()
        if not node: return
        newnode = bookmarks.nodes.Folder()
        newnode.set_title('<Category>')
        newnode.set_add_date(int(time.time()))
        self._collection.add_Folder(newnode)
        self._insert_at_node(node, newnode)
        details = DetailsDialog(self._dialog._frame, newnode, self)
        self._details[id(newnode)] = details

    def insert_entry(self, event=None):
        node, selection = self._get_selected_node()
        if not node: return
        newnode = bookmarks.nodes.Bookmark()
        newnode.set_title('<Entry>')
        newnode.set_add_date(int(time.time()))
        self._insert_at_node(node, newnode)
        details = DetailsDialog(self._dialog._frame, newnode, self)
        self._details[id(newnode)] = details

    def remove_entry(self, event=None):
        node, selection = self._get_selected_node()
        if not node: return
        parent = node.parent()
        if not parent: return
        # which node gets selected?
        selection = self.viewer().index(node) - 1
        if selection < 0: selection = 0
        parent.del_child(node)
        self.root_redisplay()
        self.viewer().select_node(self.viewer().node(selection))
        self.set_modflag(1)
        # destroy the details dialog for the node, if it has one
        if self._details.has_key(id(node)):
            self._details[id(node)].destroy()
            del self._details[id(node)]
        # remove it from the URI and ID maps
        self._collection.del_node(node)

    ## OutlinerController overloads

    def set_aggressive_collapse(self, flag):
        if flag: self.aggressive.set(1)
        else: self.aggressive.set(0)
    def aggressive_collapse_p(self): return self.aggressive.get()

    def collapsable_p(self, node):
        if node == self.root(): return 0
        else: return OutlinerController.collapsable_p(self, node)

    ## Commands

    def _cmd(self, method, quiet=0):
        node, selection = self._get_selected_node()
        if node:
            selected_node = method(node)
            if not selected_node: selected_node = node
            self.viewer().select_node(selected_node)
            self.set_modflag(1, quiet=quiet)

    def shift_left_cmd(self, event=None):  self._cmd(self.shift_left)
    def shift_right_cmd(self, event=None): self._cmd(self.shift_right)
    def shift_up_cmd(self, event=None):    self._cmd(self.shift_up)
    def shift_down_cmd(self, event=None):  self._cmd(self.shift_down)
    def collapse_cmd(self, event=None):
        self._cmd(self.collapse_node, quiet=1)
    def expand_cmd(self, event=None):
        self._cmd(self.expand_node, quiet=1)

    def shift_to_top_cmd(self, event=None):
        node = self.root()
        if node.children():
            self.viewer().select_node(node.children()[0])

    def shift_to_bottom_cmd(self, event=None):
        node = self.root()
        while node.children():
            node = node.children()[-1]
            if node.leaf_p() or not node.expanded_p():
                break
        if node is not self.root():
            self.viewer().select_node(node)

    def _prevnext(self, delta):
        node, selection = self._get_selected_node()
        if node:
            node = self.viewer().node(selection + delta)
            if node: self.viewer().select_node(node)
    def previous_cmd(self, event=None): self._prevnext(-1)
    def next_cmd(self, event=None): self._prevnext(1)

    # interface for searching

    def search_for_pattern(self, pattern,
                           regex_flag, case_flag, backwards_flag):
        # is case important in a literal match?
        if regex_flag:
            if case_flag:
                cre = regex.compile(pattern, casefold)
            else:
                cre = regex.compile(pattern)
        elif not case_flag:
            pattern = string.lower(pattern)
        # depth-first search for the next (or previous) node
        # containing the pattern.  Handle wrapping.
        sv = OutlinerViewer(self._root,
                            follow_all_children=1,
                            shared_root=1)
        sv.populate()
        # get the index of the listbox's selected node in the search
        # viewer's flat space
        startnode, selection = self._get_selected_node()
        nodei = sv.index(startnode)
        node = None
        while 1:
            if backwards_flag:
                nodei = nodei - 1
                if nodei < 0:
                    nodei = sv.count() - 1
            else:
                nodei = nodei + 1
                if nodei == sv.count():
                    nodei = 0
            node = sv.node(nodei)
##          print 'checking nodei(%d): %s' % (nodei, node)
            if not node:
                print 'no node for', nodei
                return None
            # match can occur in the title, uri string, or
            # description string. get this as one big ol' string
            nodetype = node.get_nodetype()
            if nodetype == "Folder":
                text = '%s\n%s\n' % (node.title(), node.description())
            elif nodetype == "Bookmark":
                text = '%s\n%s\n%s\n' % (node.title(), node.uri(),
                                         node.description())
            else:
                continue
            if not regex_flag and not case_flag:
                text = string.lower(text)
            # literal match
            if not regex_flag:
                if string.find(text, pattern) >= 0:
                    break
            # regex match
            elif cre.search(text) >= 0:
                break
            # have we gone round the world without a match?
            if node == startnode:
                return None
        # we found a matching node. make sure it's visible in the
        # listbox and then select it.
        self.show_node(node)
        self.viewer().select_node(node)
        self.set_modflag(1, quiet=1)
        return 1


class BookmarksFormatter:
    def __init__(self, browser, root):
        import formatter
        self.__app = get_grailapp()
        self.viewer = browser.viewer
        self.formatter = formatter.AbstractFormatter(self.viewer)
        self.viewer.unfreeze()
        browser.set_title(root.title() or "Bookmarks")
        try:
            self.fmt_root(root)
        finally:
            self.viewer.freeze()

    def fmt_root(self, root):
        self.formatter.end_paragraph(1)
        self.formatter.push_font(("h1", 0, 1, 0))
        self.formatter.add_flowing_data(root.title())
        self.formatter.pop_font()
        self.formatter.end_paragraph(1)
        desc = root.description()
        if desc:
            self.__fmt_description(desc)
            self.formatter.end_paragraph(1)
        self.formatter.add_hor_rule()
        self.formatter.end_paragraph(1)
        map(self.fmt_any, root.children())

    def fmt_any(self, node):
        try:
            method = getattr(self, "fmt_" + node.get_nodetype())
        except AttributeError:
            pass
        else:
            method(node)

    def fmt_Alias(self, node):
        refnode = node.get_refnode()
        nodetype = refnode.get_nodetype()
        if nodetype == "Folder":
            self.fmt_Folder(refnode, alias=1)
        elif nodetype == "Bookmark":
            self.fmt_Bookmark(refnode, alias=1)

    def fmt_Bookmark(self, node, alias=0):
        uri = node.uri()
        atag = 'a'
        utag = '>' + uri
        self.viewer.bind_anchors(utag)
        if self.__app.global_history.inhistory_p(uri):
            atag = 'ahist'
        if alias:
            self.formatter.push_font((None, alias, None, None))
        self.formatter.push_style(atag, utag)
        self.formatter.add_flowing_data(node.title() or "")
        self.formatter.pop_style(2)
        if alias:
            self.formatter.add_flowing_data(" (Alias)")
            self.formatter.pop_font()
        self.formatter.add_line_break()
        self.__fmt_description(node.description())

    def fmt_Folder(self, node, alias=0):
        id = node.id()
        if id and not alias:
            idtag = "#" + id
            self.viewer.add_target(idtag)
        elif alias:
            idtag = ">#" + id
            self.viewer.bind_anchors(idtag)
        else:
            idtag = None
        self.formatter.end_paragraph(1)
        self.formatter.push_font((None, alias, 1, None))
        self.formatter.push_style(idtag)
        self.formatter.add_flowing_data(node.title())
        self.formatter.pop_style()
        if alias:
            self.formatter.pop_font()
            self.formatter.push_font((None, alias, 0, None))
            self.formatter.add_flowing_data(" (Alias)")
        self.formatter.pop_font()
        self.formatter.end_paragraph(1)
        desc = node.description()
        if desc:
            self.__fmt_description(desc)
            self.formatter.end_paragraph(1)
        if not alias:
            # could be a recursive relationship, so just skip it
            children = node.children()
            if children:
                self.formatter.push_margin('folder')
                map(self.fmt_any, children)
                self.formatter.pop_margin()
                self.formatter.end_paragraph(1)

    def fmt_Separator(self, node):
        self.formatter.add_hor_rule()

    def __fmt_description(self, desc):
        if desc:
            self.formatter.push_margin('description')
            self.formatter.add_flowing_data(desc)
            self.formatter.add_line_break()
            self.formatter.pop_margin()


class BookmarksMenuLeaf:
    def __init__(self, node, controller):
        self._node = node
        self._controller = controller
    def goto(self): self._controller.goto_node(self._node)

class BookmarksMenuViewer(OutlinerViewer):
    def __init__(self, controller, parentmenu):
        self._controller = controller
        self._depth = 0
        self._menustack = [parentmenu]
        root = controller.root().clone()
        OutlinerViewer.__init__(self, root)
        self._follow_all_children_p = 1

    def _insert(self, node, index=None):
        depth = node.depth()
        # this is the best way to pop the stack.  kinda kludgy...
        if depth < len(self._menustack):
            del self._menustack[depth:]
        # get the current menu we're building
        menu = self._menustack[depth-1]
        nodetype = node.get_nodetype()
        if nodetype == "Alias" \
           and node.get_refnode().get_nodetype() == "Bookmark":
            node = node.get_refnode()
            nodetype = "Bookmark"
        if nodetype == "Separator":
            menu.add_separator()
        elif nodetype == "Bookmark":
            leaf = BookmarksMenuLeaf(node, self._controller)
            menu.add_command(label=_node_title(node), command=leaf.goto)
        elif nodetype == "Folder":
            submenu = Menu(menu, tearoff=0)
            self._menustack.append(submenu)
            menu.add_cascade(label=_node_title(node), menu=submenu)


MAX_TITLE_WIDTH = 50

def _node_title(node):
    """Return an abbreviated version of the node title."""
    # Could be better -- try to break on word boundaries.
    title = node.title()
    if not title:
        title = node.uri()
    if not title:
        return "(Unknown)"
    if len(title) > MAX_TITLE_WIDTH:
        return title[:MAX_TITLE_WIDTH - 4] + " ..."
    return title


class BookmarksMenu:
    """This is top level hook between the Grail Browser and the
    Bookmarks subdialogs.  When invoked from within Grail, all
    functionality falls from this entry point.
    """
    def __init__(self, menu):
        self._menu = menu
        self._browser = menu.grail_browser
        self._frame = self._browser.root
        self._app = self._browser.app
        self._viewer = None
        # set up the global controller.  Only one of these in every
        # application
        try:
            self._controller = self._app.bookmarks_controller
        except AttributeError:
            self._controller = self._app.bookmarks_controller = \
                               BookmarksController(self._app)
        self._controller.add_watched_menu(self)
        # currently, too difficult to coordinate edits to bookmarks
        # with tear-off menus, so just disable these for now and
        # create the rest of this menu every time the menu is posted
        self._menu.config(tearoff='No', postcommand=self.post)
        # fill in the static part of the menu
        self._menu.add_command(label='Add Current',
                               command=self.add_current,
                               underline=0, accelerator='Alt-A')
        self._browser.root.bind('<Alt-a>', self.add_current)
        self._browser.root.bind('<Alt-A>', self.add_current)
        self._menu.add_command(label='Bookmarks Viewer...',
                               command=self.show,
                               underline=0, accelerator='Alt-B')
        self._browser.root.bind('<Alt-b>', self.show)
        self._browser.root.bind('<Alt-B>', self.show)

    def post(self, event=None):
        # delete any old existing bookmark entries
        if not self._viewer:
            last = self._menu.index(END)
            if last > 1:
                self._menu.delete(2, END)
            if self._controller.includepulldown.get():
                self._menu.add_separator()
                # First make sure the controller has initialized
                self._controller.initialize()
                self._controller.set_browser(self._browser)
                self._viewer = BookmarksMenuViewer(self._controller,
                                                   self._menu)
                self._viewer.populate()

    def show(self, event=None):
        # make sure controller is initialized
        self._controller.initialize()
        self._controller.set_browser(self._browser)
        self._controller.show()

    def add_current(self, event=None):
        # make sure controller is initialized
        self._controller.initialize()
        self._controller.set_browser(self._browser)
        self._controller.add_current()
        # if the dialog is unmapped, then do a save
        if not self._controller.dialog_is_visible_p():
            self._controller.save()

    def set_modflag(self, flag):
        if flag:
            self._viewer = None

    def close(self):
        self._controller.remove_watched_menu(self)
