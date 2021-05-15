"""image/gif document handling for Grail.

This supports both plain Tk support and PIL-enhanced support.  When PIL is
available and the line

        browser--enable-pil: 1

is located in the ~/.grail/grail-preferences file, PIL will be used and can
support animation of GIF89a files as well as single-frame display.  We still
need a way for the user to STOP the animation!

The files Grail/*.py from the PIL distribution should be installed in the
same directory as this file.
"""
import AsyncImage
import grailutil
import os
import string
import sys
import tempfile
import Tkinter

from formatter import AS_IS

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


ERROR_FILE = os.path.join("icons", "sadsmiley.gif")


class pil_interface:
    """Dummy class to keep us from having to define PILGifParser within a
    try/except construct."""
    pass

try:
    import Image
    import ImageTk
    from pil_interface import pil_interface
except ImportError:
    _use_pil = 0
else:
    _use_pil = 1


class PILGifParser(pil_interface):
    im = None
    currentpos = 0
    duration = 0
    loop = 0

    def close(self):
        if self.buf:
            self.label.config(text="<decoding>")
            self.label.update_idletasks()
            data = string.joinfields(self.buf, "")
            self.buf = None             # free lots of memory!
            try:
                self.im = im = Image.open(StringIO(data))
                im.load()
                self.tkim = tkim = ImageTk.PhotoImage(im.mode, im.size)
                tkim.paste(im)
            except:
                # XXX What was I trying to catch here?
                # I think (EOFError, IOError).
                self.broken = 1
                stdout = sys.stdout
                try:
                    sys.stdout = sys.stderr
                    print "Error decoding image:"
                    print str(sys.exc_type) + ":", sys.exc_value
                finally:
                    sys.stdout = stdout
            else:
                self.label.config(image=tkim)
                if im.info.has_key("duration"):
                    self.duration = im.info["duration"]
                if im.info.has_key("loop"):
                    self.duration = self.duration or 100
                    self.loop = im.info["loop"]
                    self.data = data
                if self.duration or self.loop:
                    self.viewer.register_reset_interest(self.cancel_loop)
                    self.after_id = self.label.after(self.duration,
                                                     self.next_image)
        if self.broken:
            self.label.image = Tkinter.PhotoImage(
                file=grailutil.which(ERROR_FILE))
            self.label.config(image = self.label.image)
            self.viewer.text.insert(Tkinter.END, '\nBroken Image!')

    def next_image(self):
        newpos = self.currentpos + 1
        try:
            self.im.seek(newpos)
        except (ValueError, EOFError):
            # past end of animation
            if self.loop:
                self.reset_loop()
            else:
                # all done
                self.viewer.unregister_reset_interest(self.cancel_loop)
                return
        else:
            self.currentpos = newpos
            self.tkim.paste(self.im)
        self.after_id = self.label.after(self.duration, self.next_image)

    def reset_loop(self):
        im = Image.open(StringIO(self.data))
        im.load()
        self.tkim.paste(im)
        self.im = im
        self.currentpos = 0

    def cancel_loop(self, *args):
        self.viewer.unregister_reset_interest(self.cancel_loop)
        self.label.after_cancel(self.after_id)


class TkGifParser:
    """Parser for image/gif files.

    Collect all the data on a temp file and then create an in-line
    image from it.
    """

    def __init__(self, viewer, reload=0):
        self.tf = self.tfname = None
        self.viewer = viewer
        self.viewer.new_font((AS_IS, AS_IS, AS_IS, 1))
        self.tfname = tempfile.mktemp()
        self.tf = open(self.tfname, 'wb')
        self.label = Tkinter.Label(self.viewer.text, text=self.tfname,
                                   highlightthickness=0, borderwidth=0)
        self.viewer.add_subwindow(self.label)

    def feed(self, data):
        self.tf.write(data)

    def close(self):
        if self.tf:
            self.tf.close()
            self.tf = None
            self.label.image = Tkinter.PhotoImage(file=self.tfname)
            self.label.config(image=self.label.image)
        if self.tfname:
            try:
                os.unlink(self.tfname)
            except os.error:
                pass


def parse_image_gif(*args, **kw):
    """Create the appropriate image handler, and replace this function with
    the handler for future references (to skip the determination step)."""

    global parse_image_gif
    if _use_pil and AsyncImage.isPILAllowed():
        parse_image_gif = PILGifParser
    else:
        parse_image_gif = TkGifParser
    return apply(parse_image_gif, args, kw)
