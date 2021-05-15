__version__ = '$Revision: 1.5 $'

import Reader
import string


class PrintingTextParser(Reader.TextParser):
    __buffer = ''

    def __init__(self, writer, strip_blanks, title):
        self.__strip_blanks = strip_blanks
        writer.ps.set_title(title)
        writer.ps.prune_titles()
        Reader.TextParser.__init__(self, writer)

    def close(self):
        self.write_page(self.__buffer)
        self.__buffer = ''
        Reader.TextParser.close(self)

    def feed(self, data):
        data = self.__buffer + data
        self.__buffer = ''
        strings = string.splitfields(data, "\f")
        if strings:
            for s in strings[:-1]:
                self.write_page(s)
            self.__buffer = strings[-1]

    __first = 1
    def write_page(self, data):
        data = string.rstrip(data)
        if self.__strip_blanks:
            data = self.strip_blank_lines(data)
            # discard blank pages:
            if not data:
                return
        if self.__first:
            self.__first = 0
        else:
            self.viewer.ps.close_line()
            self.viewer.ps.push_page_break()
        self.viewer.send_literal_data(data)

    def strip_blank_lines(self, data):
        lines = map(string.rstrip, string.splitfields(data, "\n"))
        while lines:
            if string.strip(lines[0]) == "":
                del lines[0]
            else:
                break
        return string.joinfields(lines, "\n")


def parse_text(writer, settings, context):
    return PrintingTextParser(
        writer, settings.strip_blanks, settings.__title)


def add_options(dialog, settings, top):
    import Tkinter
    import tktools
    textfr = tktools.make_group_frame(top, "textoptions",
                                      "Text options:", fill=Tkinter.X)
    #  The titleentry widget is used to set the title for text/plain
    #  documents; the title is printed in the page headers and
    #  possibly on an accounting page if your site uses them.
    dialog.__titleentry, dummyframe = tktools.make_form_entry(textfr, "Title:")
    if dialog.title:
        dialog.__titleentry.insert(Tkinter.END, dialog.title)
    dialog.add_entry(dialog.__titleentry)
    Tkinter.Frame(textfr, height=4).pack()
    dialog.__strip_blanks = dialog.new_checkbox(
        textfr, "Strip leading blank lines", settings.strip_blanks)


def update_settings(dialog, settings):
    settings.strip_blanks = dialog.__strip_blanks.get()
    dialog.title = dialog.__titleentry.get()
    settings.__title = dialog.title
