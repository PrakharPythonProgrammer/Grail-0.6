from Tkinter import *

STYLEGROUP = 'styles-common'
AHISTPREF = 'history-ahist-foreground'
APREF = 'history-a-foreground'
ATEMPPREF = 'history-atemp-foreground'

class ImageWindow(Frame):

    image_loaded = 0

    def __init__(self, viewer, url, src, alt, usemap, ismap, align,
                 width, height, borderwidth, target="", reload=0):
        self.viewer = viewer
        self.context = self.viewer.context
        self.src, self.alt, self.align = src, alt, align
        self.target = target
        ### set up mapping is either and server map or a client map
        if usemap:
            self.map = usemap
            self.url = None
            self.ismap = None
        elif ismap:
            self.ismap = 1
            self.url = url
            self.map = None
        else:
            self.url = url
            self.ismap = None
            self.map = None
        bgcolor = self.get_bgcolor(borderwidth)
        Frame.__init__(self, viewer.text, borderwidth=borderwidth,
                       background=bgcolor)
        self.borderwidth = borderwidth
        label = Label(self, text=self.alt, background=bgcolor, borderwidth=0)
        label.pack(fill=BOTH, expand=1)
        if width > 0 or height > 0:
            self.propagate(0)
            self.config(width=width + 2*borderwidth,
                        height=height + 2*borderwidth)
        if self.url or self.map:
            self.bind('<Enter>', self.enter)
            self.bind('<Leave>', self.leave)
            if (self.ismap and self.url) or self.map:
                label.bind('<Motion>', self.motion)
            label.bind('<ButtonRelease-1>', self.follow)
            label.bind('<ButtonRelease-2>', self.follow_new)
        label.bind("<Button-3>", self.button_3_event)
        self.image = self.context.get_async_image(
            self.src, reload, width=width, height=height)
        if self.image:
            label['image'] = self.image

    def get_bgcolor(self, borderwidth):
        # figure out colors for link, if the image is a link
        if borderwidth:
            app = self.context.app
            if self.url:
                histurl = self.context.get_baseurl(self.url)
                if app.global_history.inhistory_p(histurl):
                    bg = app.prefs.Get(STYLEGROUP, AHISTPREF)
                else:
                    bg = app.prefs.Get(STYLEGROUP, APREF)
            elif self.map:
                bg = app.prefs.Get(STYLEGROUP, APREF)
            else:
                bg = self.viewer.text['foreground']
        else:
            bg = self.viewer.text['background']
        return bg

    def enter(self, event):
        url, target = self.whichurl(event)
        if url:
            if target: url = url + " in " + target
            self.context.viewer.enter_message(url)

    def leave(self, event):
        self.context.viewer.leave_message()

    def motion(self, event):
        url, target = self.whichurl(event)
        if url:
            if target: url = url + " in " + target
            self.context.viewer.enter_message(url)
        else:
            self.context.viewer.leave_message()

    def follow(self, event):
        url, target = self.whichurl(event)
        if url:
            app = self.context.app
            self['background'] = app.prefs.Get(STYLEGROUP, ATEMPPREF)
            self.context.follow(url, target=target)
        else:
            self.context.viewer.leave_message()

    def follow_new(self, event):
        url, target = self.whichurl(event)
        if url:
            app = self.context.app
            self['background'] = app.prefs.Get(STYLEGROUP, ATEMPPREF)
            url = self.context.get_baseurl(url)
            from Browser import Browser
            Browser(app.root, app).context.load(url)
            self['background'] = app.prefs.Get(STYLEGROUP, AHISTPREF)
        else:
            self.context.viewer.leave_message()

    def whichurl(self, event):
        # perhaps having a usemap and an ismap is a bad idea
        # because we now need *two* tests for maps when the 
        # common case might be no map
        if self.ismap:
            return self.url + "?%d,%d" % (event.x, event.y), ""
        elif self.map:
            return self.map.url(event.x,event.y)
        return self.url, self.target

    # table width calculation interface

    def table_geometry(self):
        import string
        bw = self.borderwidth
        if self.image:
            w = self.image.width() + 2 * bw
            h = self.image.height() + 2 * bw
        else:
            w = h = 2 * bw
        x = self.winfo_x()
        y = self.winfo_y()
        return x+w, x+w, y+h

    def button_3_event(self, event):
        url, target = self.whichurl(event)
        imgurl = self.src
        if imgurl:
            imgurl = self.context.get_baseurl(imgurl)
        self.viewer.open_popup_menu(event, link_url=url, image_url=imgurl)
