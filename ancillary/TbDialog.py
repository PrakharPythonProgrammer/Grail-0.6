"""Modeless dialog displaying exception and traceback."""

import string
import tk_tools
import traceback

from tkinter import *


class TracebackDialog:

    def __init__(self, master, exc, val, tb):
        self.master = master
        self.exc = exc
        self.val = val
        self.tb = tb
        self.root = tk_tools.make_toplevel(self.master,
                                          title="Traceback Dialog")
        close = self.close_command
        self.close_button = Button(self.root, text="Close",
                                   command=close, default="active")
        self.root.protocol("WM_DELETE_WINDOW", close)
        self.root.bind("<Alt-W>", close)
        self.root.bind("<Alt-w>", close)
        anchor = None
        if tk_tools._inTkStep(self.root):
            anchor = E
        self.close_button.pack(side=BOTTOM, pady='1m', padx='1m',
                               anchor=anchor)
        self.close_button.focus_set()
        self.label = Label(self.root, text="%s: %s" % (exc, str(val)))
        self.label.pack(fill=X)
        self.text, self.text_frame = tk_tools.make_text_box(self.root, width=90)
        lines = traceback.format_exception(exc, val, tb)
        lines.append('')
        tb = string.join(map(string.rstrip, lines), '\n')
        self.text.insert(END, tb)
        self.text.yview_pickplace(END)
        self.text["state"] = DISABLED

    def close_command(self, event=None):
        self.root.destroy()
