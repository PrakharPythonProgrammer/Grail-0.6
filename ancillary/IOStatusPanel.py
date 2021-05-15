from Tkinter import *
import tktools

class IOStatusPanel:

    def __init__(self, app):
        self.app = app
        self.id = None
        self.create_widgets()
        self.update()

    def create_widgets(self):
        self.top = tktools.make_toplevel(self.app.root,
                                         title="Grail: I/O Status",
                                         class_="IOStatusPanel")
        self.closebutton = Button(self.top, name="close", command=self.close,
                                  default="active")
        self.closebutton.pack(side=BOTTOM, pady='1m', padx='1m', anchor=E)
        self.closebutton.focus_set()
        self.infobox, self.frame = tktools.make_list_box(self.top, width=40)
        self.infobox.pack(expand=1, fill=BOTH, side=TOP)
        self.top.protocol('WM_DELETE_WINDOW', self.close)
        self.top.bind("<Alt-w>", self.close)
        self.top.bind("<Alt-W>", self.close)

    def close(self, event=None):
        self.cancel_update()
        top = self.top
        self.top = self.closebutton = self.infobox = None
        if top:
            top.destroy()

    def reopen(self):
        if self.top:
            self.top.deiconify()
            self.top.tkraise()
        else:
            self.create_widgets()
            self.update()

    def schedule_update(self):
        self.cancel_update()
        self.id = self.top.after(1000, self.call_update)

    def call_update(self):
        self.id = None
        self.update()

    def cancel_update(self):
        id = self.id
        self.id = None
        if id:
            if self.top:
                self.top.after_cancel(id)

    def update(self):
        if self.top:
            self.fill_info()
            self.schedule_update()

    def fill_info(self):
        count = 0
        self.infobox.delete(0, END)
        for browser in self.app.browsers:
            count = count+1
            headline = "<Browser %d>" % count
            self.infobox.insert(END, headline)
            self.add_context_info(browser.context)

    def add_context_info(self, context, level=1):
        indent = "   " * level
        headline = context.get_url() or "<no document>"
        if context.viewer.name:
            headline = "%s: %s" % (context.viewer.name, headline)
        self.infobox.insert(END, indent + headline)
        for reader in context.readers:
            self.add_reader_info(reader, level+1)
        for viewer in context.viewer.subviewers:
            subcontext = viewer.context
            if subcontext is not context:
                self.add_context_info(subcontext, level+1)

    def add_reader_info(self, reader, level):
        indent = "   " * level
        headline = str(reader)
        self.infobox.insert(END, indent + headline)
