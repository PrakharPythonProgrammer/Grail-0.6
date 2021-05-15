"""Support for Netscape's <FRAMESET> tag (and <FRAME> and <NOFRAMES>)."""


import string
from Tkinter import *


def start_frameset(parser, attrs):
    # Augment parser object
    tags = parser.object_aware_tags
    if 'frameset' not in tags:
        tags.append('noframes')
    rows = ""
    cols = ""
    for name, value in attrs:
        if name == "rows": rows = value
        if name == "cols": cols = value
    if not hasattr(parser, "frameset"):
        parent = None
    else:
        parent = parser.frameset
    parser.frameset = FrameSet(parser, rows, cols, parent)

def end_frameset(parser):
    if parser.frameset:
        parser.frameset.done()
        parser.frameset = parser.frameset.parent

def do_frame(parser, attrs):
    if not (hasattr(parser, "frameset") and parser.frameset):
        return
    src = ""
    fname = ""
    marginwidth = ""
    marginheight = ""
    scrolling = "auto"
    noresize = ""
    for name, value in attrs:
        if name == "src": src = value
        if name == "name": fname = value
        if name == "marginheight": marginheight = value
        if name == "marginwidth": marginwidth = value
        if name == "scrolling": scrolling = value
        if name == "noresize": noresize = value
    scrolling = string.lower(scrolling)
    # Make scrolling either "auto" or a boolean
    if scrolling in ("a", "au", "aut", "auto"):
        scrolling = "auto"
    else:
        scrolling = scrolling in ("yes", "on", "true", "1")
    parser.frameset.add_frame(src, fname, marginwidth, marginheight,
                              scrolling, noresize)

def start_noframes(parser, attrs):
    if parser.push_object("noframes"):
        return
    parser.set_suppress()

def end_noframes(parser):
    parser.pop_object()


class FrameSet:

    def __init__(self, parser, rows, cols, parent):
        self.parser = parser
        self.rows = rows
        self.cols = cols
        self.parent = parent            # None or a FrameSet instance
        if self.parent:
            self.viewer = self.parent.make_next_viewer(scrolling=0)
        else:
            self.viewer = self.parser.viewer
        if self.viewer:
            self.master = self.viewer.frame
        else:
            self.master = None
        self.frames = []
        self.viewers = []
        self.nextframe = 0
        if self.master and (self.rows or self.cols):
            self.make_sizes()
            self.make_frames()
            self.viewer.register_resize_interest(self.on_viewer_resize)
            self.viewer.register_reset_interest(self.on_viewer_reset)

    def make_sizes(self):
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        self.colsizes = self.calculate_sizes(self.cols, width)
        self.rowsizes = self.calculate_sizes(self.rows, height)

    def make_frames(self):
        y = 0
        for height in self.rowsizes:
            x = 0
            for width in self.colsizes:
                frame = Frame(self.master)
                self.frames.append(frame)
                frame.place(x=x, y=y, width=width, height=height)
                x = x + width
            y = y + height

    def on_viewer_resize(self, viewer):
        self.make_sizes()
        self.resize_frames()

    def on_viewer_reset(self, viewer):
        viewer.unregister_resize_interest(self.on_viewer_resize)
        viewer.unregister_reset_interest(self.on_viewer_reset)
        viewers = self.viewers
        self.viewers = []
        for viewer in viewers:
            viewer.close()
        frames = self.frames
        self.frames = []
        for frame in frames:
            frame.destroy()

    def resize_frames(self):
        i = 0
        y = 0
        for height in self.rowsizes:
            x = 0
            for width in self.colsizes:
                frame = self.frames[i]
                i = i+1
                frame.place(x=x, y=y, width=width, height=height)
                x = x + width
            y = y + height

    import regex
    sizeprog = regex.compile("[ \t]*\([0-9]*\)\([%*]?\)")

    def calculate_sizes(self, sizes, total):
        rawlist = string.splitfields(sizes, ",")
        sizelist = []
        fixed = nfixed = 0
        percent = npercent = 0
        star = nstar = 0
        for raw in rawlist:
            if self.sizeprog.match(raw) >= 0:
                number, type = self.sizeprog.group(1, 2)
            else:
                number, type = "1", "*"
                # XXX report error?
            if not number:
                if type != '*':
                    # XXX report error?
                    type = '*'
                number = 1
            else:
                try:
                    number = string.atoi(number)
                except:
                    # XXX report error?
                    number, type = 1, '*'
            if type == '%':
                npercent = npercent + 1
                percent = percent + number
            elif type == '*':
                nstar = nstar + 1
                star = star + number
            else:
                nfixed = nfixed + 1
                fixed = fixed + number
            sizelist.append((number, type))

        available = total - fixed
        if available < 0 or available > 0 and not (percent or star):
            for i in range(len(sizelist)):
                number, type = sizelist[i]
                if not type:
                    number = number * total / fixed
                    sizelist[i] = number, type
            available = 0
        if percent or star:
            scale = 100
            if percent:
                requested = total * percent / scale
                if requested > available or requested < available and not star:
                    scale = percent * total / requested
                    requested = total * percent / scale
                available = max(0, available - requested)
            for i in range(len(sizelist)):
                number, type = sizelist[i]
                if type == '%':
                    number = total * number / scale
                    sizelist[i] = number, type
                    fixed = fixed + number
                elif type == '*':
                    number = available * number / star
                    sizelist[i] = number, type

        list = []
        for number, type in sizelist:
            list.append(number)
        return list

    def add_frame(self, src, name, marginwidth, marginheight,
                  scrolling, noresize):
        viewer = self.make_next_viewer(name, scrolling)
        if viewer:
            self.do_margin(viewer, 'padx', marginwidth)
            self.do_margin(viewer, 'pady', marginheight)
            src = self.viewer.context.get_baseurl(src)
            viewer.context.load(src, reload=self.parser.reload)

    def do_margin(self, viewer, attr, value):
        try:
            mw = string.atoi(value)
        except ValueError:
            pass
        else:
            if mw >= 0: viewer.text[attr] = mw

    def done(self):
        while self.make_next_viewer():
            pass

    def make_next_viewer(self, name="", scrolling="auto"):
        frame = self.get_next_frame()
        if frame:
            viewer = self.viewer.make_subviewer(frame, name, scrolling)
            if viewer:
                self.viewers.append(viewer)
            return viewer

    def get_next_frame(self):
        if self.nextframe >= len(self.frames):
            return None
        frame = self.frames[self.nextframe]
        self.nextframe = self.nextframe + 1
        return frame
