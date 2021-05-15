"""Print Dialog for Grail Browser.

This displays a dialog allowing the user to control printing of the current
document.  The following printing characteristics can be controlled from the
dialog:

        - the print command (which should take PostScript from stdin
          or a %s can be placed on the command line where the filename
          of a file containing the postscript output will be placed)
        - a check box for printing to a file
        - the filename (to receive the PostScript instead)
        - some options for controlling the output
        - an OK button
        - a Cancel button

The last state (print command, check box, filename, options) is saved in
a global settings variable managed by the printing.settings module.

When OK is activated, the HTML or text file is read using urllib.urlopen()
and the PSWriter class is used to generate the PostScript.

When Cancel is actiavted, the dialog state is still saved.

The document to be printed is checked for its MIME type; if it isn't
text/html but is text/*, text/plain is used as the handler.  If no type
is known at all (possibly a disk file without a recognized extension),
an intermediate dialog is used to inform the user that text/plain will
be assumed, giving the option to cancel.

"""

from Cursors import CURSOR_WAIT
from Tkinter import *
import grailutil
import os
import printing.paper
import printing.settings
import Reader
import string
import sys
import tktools


USER_DATA_DIR = grailutil.abspath(
    os.path.join(grailutil.getgraildir(), "data"))


def get_scaling_adjustments(w):
    scheight = float(w.winfo_screenheight())
    scwidth = float(w.winfo_screenwidth())
    scheight_mm = float(w.winfo_screenmmheight())
    scwidth_mm = float(w.winfo_screenmmwidth())
    vert_pixels_per_in = scheight / (scheight_mm / 25)
    horiz_pixels_per_in = scwidth / (scwidth_mm / 25)
    result = (72.0 / horiz_pixels_per_in), (72.0 / vert_pixels_per_in)
##     print "scaling adjustments:", result
    return result


def PrintDialog(context, url, title):
    try:
        infp = context.app.open_url_simple(url)
    except IOError, msg:
        context.error_dialog(IOError, msg)
        return
    content_encoding, transfer_encoding = Reader.get_encodings(infp.info())
    try:
        ctype = infp.info()['content-type']
    except KeyError:
        ctype, encoding = context.app.guess_type(url)
        if not content_encoding:
            content_encoding = encoding
    if not ctype:
        MaybePrintDialog(context, url, title, infp)
        return
    if not Reader.support_encodings(content_encoding, transfer_encoding):
        # create an alert of some sort....
        return
    ctype, ctype_params = grailutil.conv_mimetype(ctype)
    mod = context.app.find_type_extension("printing.filetypes", ctype)
    if ctype != "application/postscript" and not mod.parse:
        context.error_dialog(
            "Unprintable document",
            "No printing support is available for the %s media type." % ctype)
        return
    RealPrintDialog(context, url, title, infp, ctype)


class MaybePrintDialog:

    UNKNOWN_TYPE_MESSAGE = \
"""No MIME type is known for this
document.  It will be printed as
plain text if you elect to continue."""

    def __init__(self, context, url, title, infp):
        self.__context = context
        self.__url = url
        self.__title = title
        self.__infp = infp
        top = self.__top = tktools.make_toplevel(context.browser.root)
        top.title("Print Action")
        fr, topfr, botfr = tktools.make_double_frame(top)
        Label(topfr, bitmap="warning", foreground='red'
              ).pack(side=LEFT, fill=Y, padx='2m')
        # font used by the Tk4 dialog.tcl script:
        font = "-Adobe-Times-Medium-R-Normal--*-180-*-*-*-*-*-*"
        try:
            label = Label(topfr, text=self.UNKNOWN_TYPE_MESSAGE,
                          font=font, justify=LEFT)
        except TclError:
            # font not found, use one we are sure exists:
            font = context.browser.viewer.text.tag_cget('h2_b', '-font')
            label = Label(topfr, text=self.UNKNOWN_TYPE_MESSAGE,
                          font=font, justify=LEFT)
        label.pack(side=RIGHT, fill=BOTH, expand=1, padx='1m')
        b1 = Button(botfr, text="Cancel", command=self.skipit)
        b1.pack(side=RIGHT)
        b2 = Button(botfr, text="Print", command=self.doit)
        b2.pack(side=LEFT)
        tktools.unify_button_widths(b1, b2)
        tktools.set_transient(top, context.browser.root)

    def doit(self, event=None):
        self.__top.destroy()
        RealPrintDialog(self.__context,
                        self.__url,
                        self.__title,
                        self.__infp,
                        "text/plain")
        self.__context = None
        self.__infp = None

    def skipit(self, event=None):
        self.__context = None
        self.__top.destroy()
        self.__infp.close()
        self.__infp = None


class RealPrintDialog:

    def __init__(self, context, url, title, infp, ctype):
        import tktools
        #
        self.infp = infp
        self.ctype = ctype
        self.context = context
        self.baseurl = context.get_baseurl()
        self.prefs = context.app.prefs
        self.settings = printing.settings.get_settings(context.app.prefs)
        if USER_DATA_DIR not in self.settings.user_data_dirs:
            self.settings.user_data_dirs.append(USER_DATA_DIR)
        settings = self.settings
        #
        self.title = title
        self.master = self.context.root
        self.root = tktools.make_toplevel(self.master,
                                          title="Print Dialog",
                                          class_="PrintDialog")
        # do this early in case we're debugging:
        self.root.protocol('WM_DELETE_WINDOW', self.cancel_command)
        self.root.bind("<Alt-w>", self.cancel_event)
        self.root.bind("<Alt-W>", self.cancel_event)
        self.cursor_widgets = [self.root]

        fr, top, botframe = tktools.make_double_frame(self.root)

        #  Print to file controls:
        generalfr = tktools.make_group_frame(
            top, "general", "General options:", fill=X)

        self.cmd_entry, dummyframe = tktools.make_form_entry(
            generalfr, "Print command:")
        self.cmd_entry.insert(END, settings.printcmd)
        self.add_entry(self.cmd_entry)
        self.printtofile = IntVar(self.root)
        self.printtofile.set(settings.fileflag)
        fr = Frame(generalfr)
        fr.pack(fill=X)
        self.file_check = Checkbutton(fr, text = "Print to file:",
                                      command = self.check_command,
                                      variable = self.printtofile)
        self.file_check.pack(side=LEFT)
        self.file_entry = Entry(fr)
        self.file_entry.pack(side=RIGHT, fill=X)
        self.file_entry.insert(END, settings.printfile)
        self.add_entry(self.file_entry)

        if self.ctype != "application/postscript":
            # page orientation
            Frame(generalfr, height=2).pack()
            fr = Frame(generalfr)
            fr.pack(fill=X)
            self.orientation = StringVar(top)
            self.orientation.set(string.capitalize(settings.orientation))
            opts = printing.paper.paper_rotations.keys()
            opts.sort()
            opts = tuple(map(string.capitalize, opts))
            Label(fr, text="Orientation: ", width=13, anchor=E).pack(side=LEFT)
            Frame(fr, width=3).pack(side=LEFT)
            menu = apply(OptionMenu, (fr, self.orientation) + opts)
            width = reduce(max, map(len, opts), 6)
            menu.config(anchor=W, highlightthickness=0, width=width)
            menu.pack(expand=1, fill=NONE, anchor=W, side=LEFT)
            Frame(generalfr, height=2).pack()
            # font size
            fr = Frame(generalfr)
            fr.pack(fill=X)
            Label(fr, text="Font size: ", width=13, anchor=E).pack(side=LEFT)
            Frame(fr, width=3).pack(side=LEFT)
            e = self.fontsize = Entry(fr, width=12)
            e.insert(END, settings.get_fontspec())
            e.pack(side=LEFT)
            self.add_entry(e)

        self.mod = self.get_type_extension()
        if self.mod.add_options:
            Frame(top, height=8).pack()
            self.mod.add_options(self, settings, top)

        #  Command buttons:
        ok_button = Button(botframe, text="OK",
                           command=self.ok_command)
        ok_button.pack(side=LEFT)
        cancel_button = Button(botframe, text="Cancel",
                               command=self.cancel_command)
        cancel_button.pack(side=RIGHT)
        tktools.unify_button_widths(ok_button, cancel_button)

        tktools.set_transient(self.root, self.master)
        self.check_command()

    def get_type_extension(self):
        return self.context.app.find_type_extension(
            "printing.filetypes", self.ctype)

    def new_checkbox(self, parent, description, value):
        var = BooleanVar(parent)
        var.set(value)
        Checkbutton(parent, text=description, variable=var, anchor=W
                    ).pack(anchor=W, fill=X)
        return var

    def add_entry(self, entry):
        self.cursor_widgets.append(entry)
        entry.bind("<Return>", self.return_event)

    def return_event(self, event):
        self.ok_command()

    def check_command(self):
        if self.printtofile.get():
            self.file_entry['state'] = NORMAL
            self.cmd_entry['state'] = DISABLED
            self.file_entry.focus_set()
        else:
            self.file_entry['state'] = DISABLED
            self.cmd_entry['state'] = NORMAL
            self.cmd_entry.focus_set()

    def ok_command(self):
        if self.printtofile.get():
            filename = self.file_entry.get()
            if not filename:
                self.context.error_dialog("No file",
                                          "Please enter a filename")
                return
            try:
                fp = open(filename, "w")
            except IOError, msg:
                self.context.error_dialog(IOError, str(msg))
                return
        else:
            cmd = self.cmd_entry.get()
            if not cmd:
                self.context.error_dialog("No command",
                                          "Please enter a print command")
                return
            try:
                if string.find(cmd, '%s') != -1:
                    import tempfile
                    tempname = tempfile.mktemp()
                    fp = open(tempname, 'w')
                else:
                    fp = os.popen(cmd, "w")
            except IOError, msg:
                self.context.error_dialog(IOError, str(msg))
                return
        for e in self.cursor_widgets:
            e['cursor'] = CURSOR_WAIT
        self.root.update_idletasks()
        try:
            self.print_to_fp(fp)
        except:
            # don't want a try/finally since we don't need this to
            # execute unless we received an error
            for e in self.cursor_widgets: e['cursor'] = ''
            raise sys.exc_type, sys.exc_value, sys.exc_traceback
        sts = fp.close()
        if not sts:
            try:
                cmd_parts = string.splitfields(cmd, '%s')
                cmd = string.joinfields(cmd_parts, tempname)
                sts = os.system(cmd)
                os.unlink(tempname)
            except NameError:           # expected on tempname except on NT
                pass
        if sts:
            self.context.error_dialog("Exit",
                                      "Print command exit status %s" % `sts`)
        self.root.destroy()

    def cancel_event(self, event):
        self.cancel_command()

    def cancel_command(self):
        self.update_settings()
        self.root.destroy()

    def print_to_fp(self, fp):
        # do the printing
        from printing import paper
        from printing import PSWriter
        #
        self.update_settings()
        if self.ctype == "application/postscript":
            parser = self.wrap_parser(FileOutputParser(fp))
            parser.feed(self.infp.read())
            parser.close()
            self.infp.close()
            return
        apply(self.settings.set_scaling, get_scaling_adjustments(self.root))
        paper = paper.PaperInfo(self.settings.papersize,
                                margins=self.settings.margins,
                                rotation=self.settings.orientation)
        w = PSWriter.PSWriter(fp, self.title, self.baseurl, paper=paper,
                              settings=self.settings)
        p = self.mod.parse(w, self.settings, self.context)
        # need to decode the input stream a bit here:
        p = self.wrap_parser(p)
        p.feed(self.infp.read())
        self.infp.close()
        p.close()
        w.close()

    def wrap_parser(self, parser):
        # handle the content-encoding and content-transfer-encoding headers
        headers = self.infp.info()
        content_encoding, transfer_encoding = Reader.get_encodings(headers)
        return Reader.wrap_parser(parser, self.ctype,
                                  content_encoding, transfer_encoding)

    def update_settings(self):
        settings = self.settings
        settings.printcmd = self.cmd_entry.get()
        settings.printfile = self.file_entry.get()
        settings.fileflag = self.printtofile.get()
        if self.ctype == "application/postscript":
            return
        settings.set_fontsize(self.fontsize.get())
        settings.orientation = string.lower(self.orientation.get())
        if self.mod.update_settings:
            self.mod.update_settings(self, settings)


class FileOutputParser:
    def __init__(self, fp):
        self.__fp = fp

    def feed(self, data):
        self.__fp.write(data)

    def close(self):
        pass
