# Java compatibility :-)

from Tkinter import *

class ImageLoopItem:

    def __init__(self, master, img='logo:',
                 pause=3900, delay=100, align=None, text="?", **kw):
        self.master = master
        self.pause = pause
        self.delay = delay
        self.context = master.grail_context
        self.urlpattern = img + "T%d.gif"
        self.images = []
        self.index = 0
        self.done = 0
        self.label = Label(master, text=text, background=master['background'])
        self.label.pack()
        self.loadnext()
        self.schedule()

    def loadnext(self):
        url = self.urlpattern % (len(self.images) + 1)
        image = self.context.get_async_image(url)
        if not image:
            self.done = 1
        else:
            self.images.append(image)

    def schedule(self):
        if not self.images: return
        delay = self.delay
        if self.done and self.index == 1%len(self.images):
            delay = delay + self.pause
        self.master.after(delay, self.update)

    def update(self):
        image = self.images[self.index]
        if not self.done:
            # Check status of image
            if not image.loaded:
                # Not loaded -- still busy or failed
                if image.get_load_status() == 'loading':
                    # Still busy -- come again later
                    self.schedule()
                    return
                # Image loading failed -- we're done
                self.done = 1
                del self.images[self.index]
                self.index = 0
                self.schedule()
                return
            # Loaded -- start loading the next one
            self.loadnext()
        # We get here only if the image has been successfully loaded
        try:
            self.label['image'] = image
        except TclError:
            # The widget probably has been destroyed
            return
        self.index = (self.index + 1) % len(self.images)
        self.schedule()
