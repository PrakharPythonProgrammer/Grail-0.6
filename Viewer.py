"""Viewer class."""

import sys
from Tkinter import *
import tktools
import formatter
import string
from string import strip
from Context import Context, SimpleContext
from Cursors import *
from types import StringType
from urlparse import urljoin, urlparse
from Stylesheet import UndefinedStyle


MIN_IMAGE_LEADER = "\240"               # Non-spacing space
INDENTATION_WIDTH = 30                  # Pixels / indent level
TARGET_SEPARATOR = '\1'                 # url TARGET_SEPARATOR target


font_dingbats = {
    'disc': ('\x6c', '_ding'),
    'circle': ('\x6d', '_ding'),
    'square': ('\x6f', '_ding'),
    }


class WidthMagic:
    def __init__(self, viewer, abswidth, percentwidth):
        self.__abswidth = abswidth
        self.__percentwidth = percentwidth
        self.__text = viewer.text
        dents = viewer.marginlevel + viewer.rightmarginlevel
        self.__removable = (dents * INDENTATION_WIDTH) \
                           + viewer.RULE_WIDTH_MAGIC

    def close(self):
        self.__text = None              # free reference

    def get_available_width(self):
        #  Getting the 'padx' option of the text widget needs to be done
        #  here for an as-yet undetermined reason.
        return int(self.__text.winfo_width() - self.__removable
                   - (2 * string.atoi(self.__text["padx"])))

    def get_requested_widths(self):
        return self.__abswidth, self.__percentwidth


class HRule(Canvas):
    def __init__(self, viewer, abswidth, percentwidth, height=2, **kw):
        self.__magic = viewer.width_magic(abswidth, percentwidth)
        kw["borderwidth"] = 1
        kw["relief"] = SUNKEN
        kw["height"] = max(0, height - 2)
        bgcolor = viewer.text["background"]
        kw["background"] = bgcolor
        kw["highlightbackground"] = bgcolor
        kw["highlightthickness"] = 0
        kw["width"] = self.get_width()
        apply(Canvas.__init__, (self, viewer.text), kw)

    def get_width(self):
        maxwid = self.__magic.get_available_width()
        abswidth, percentwidth = self.__magic.get_requested_widths()
        if abswidth:
            return min(abswidth, maxwid)
        else:
            return maxwid * percentwidth

    def destroy(self):
        self.__magic.close()
        Canvas.destroy(self)


class Viewer(formatter.AbstractWriter):

    """A viewer is mostly a fancy text widget with scroll bars.

    It also doubles as the 'writer' for a Formatter.

    """

    def __init__(self, master, browser=None, context=None, stylesheet=None,
                 width=80, height=40, name="", scrolling="auto",
                 parent=None):
        formatter.AbstractWriter.__init__(self)
        self.master = master
        if not browser:
            if parent:
                browser = parent.context.browser
        self.context = context or Context(self, browser)
        self.prefs = self.context.app.prefs
        self.stylesheet = stylesheet or self.context.app.stylesheet
        self.name = name
        self.scrolling = scrolling
        self.parent = parent
        self.subwindows = []
        self.rules = []
        self.subviewers = []
        self.resize_interests = [self.__class__.resize_rules]
        self.reset_interests = [self.__class__.clear_targets]
        self.current_cursor = CURSOR_NORMAL
        if not self.parent:
            # Avoid showing the widget until it's fully constructed:
            self.master.withdraw()
        self.__fonttags_built = {}
        self.init_presentation()
        self.create_widgets(width=width, height=height)
        self.reset_state()
        self.freeze(1)
        self.text.bind('<Configure>', self.resize_event)
        self._atemp = []
        self.current_index = None
        self.popup_menu = None
        self.status = StringVar(self.master)
        self.linkinfo = ""
        if self.context.viewer is self:
            self.frame.bind('<Enter>', self.enter_frame)
        if self.parent:
            self.parent.add_subviewer(self)
        self.message("")
        self.add_styles_callbacks()
        if not self.parent:
            # Ok, now show the fully constructed widget:
            self.master.deiconify()
            self.master.tkraise()

    def add_styles_callbacks(self):
        """Add prefs callbacks so text widget's reconfigured on major changes.
        """
        self.prefs.AddGroupCallback('styles-common', self.init_styles)
        self.prefs.AddGroupCallback('styles-fonts', self.init_styles)
        self.prefs.AddGroupCallback('styles', self.init_styles)
        self.prefs.AddGroupCallback('presentation',
                                    self.configure_presentation)

    def remove_styles_callbacks(self):
        self.prefs.RemoveGroupCallback('styles-common', self.init_styles)
        self.prefs.RemoveGroupCallback('styles-fonts', self.init_styles)
        self.prefs.RemoveGroupCallback('styles', self.init_styles)
        self.prefs.RemoveGroupCallback('presentation',
                                       self.configure_presentation)

    def message(self, message):
        if not self.context or self.linkinfo:
            return
        if self.name:
            message = "%s: %s" % (self.name, message)
        self.status.set(message)
        if not self.parent:
            self.context.browser.messagevariable(self.status)
        if self.context.busy() and self.context.viewer is self:
            cursor = CURSOR_WAIT
        else:
            cursor = CURSOR_NORMAL
        self.set_cursor(cursor)

    def enter_frame(self, event):
        self.context.browser.messagevariable(self.status)

    def reset_state(self):
        self.fonttag = None             # Tag specifying font
        self.margintag = None           # Tag specifying margin (left)
        self.marginlevel = 0            # Numeric margin level (left)
        self.rightmargintag = None      # Tag specifying margin (right)
        self.rightmarginlevel = 0       # Numeric margin level (right)
        self.spacingtag = None          # Tag specifying spacing
        self.addtags = ()               # Additional tags (e.g. anchors)
        self.align = None               # Alignment setting
        self.pendingdata = ''           # Data 'on hold'
        self.targets = {}               # Mark names for anchors/footnotes
        self.new_tags()

    def __del__(self):
        self.close()

    def close(self):
        context = self.context
        self.remove_styles_callbacks()
        if context and context.viewer is self:
            context.stop()
        if context:
            self.clear_reset()
            self.context = None
        frame = self.frame
        if frame:
            self.text = None
            frame.destroy()
            self.frame = None
        parent = self.parent
        if parent:
            parent.remove_subviewer(self)
            self.parent = None

    def create_widgets(self, width, height):
        bars = self.scrolling == "auto" or self.scrolling
        self.smoothscroll = bars and self.context.app.prefs.GetBoolean(
            "browser", "smooth-scroll-hack")
        if self.smoothscroll:
            from supertextbox import make_super_text_box
            self.text, self.frame = make_super_text_box(self.master,
                                                      width=width,
                                                      height=height,
                                                      hbar=bars, vbar=bars)
        else:
            self.text, self.frame = tktools.make_text_box(self.master,
                                                      width=width,
                                                      height=height,
                                                      hbar=bars, vbar=bars,
                                                      class_="Viewer")
        if self.parent:
            self.text.config(background=self.parent.text['background'],
                             foreground=self.parent.text['foreground'])
        self.text.config(padx=10, cursor=self.current_cursor,
                         selectbackground='yellow', insertwidth=0)
        self.default_bg = self.text['background']
        self.default_fg = self.text['foreground']
        self.configure_styles()
        if self.parent:
            link = self.parent.text.tag_configure('a', 'foreground')[-1]
            vlink = self.parent.text.tag_configure('ahist', 'foreground')[-1]
            alink = self.parent.text.tag_configure('atemp', 'foreground')[-1]
            hover_fg = self.parent.text.tag_configure(
                'hover', 'foreground')[-1]
            hover_un = self.parent.text.tag_configure(
                'hover', 'underline')[-1]
            self.text.tag_configure('a', foreground=link)
            self.text.tag_configure('ahist', foreground=vlink)
            self.text.tag_configure('atemp', foreground=alink)
            self.text.tag_configure(
                'hover', foreground=hover_fg, underline=hover_un)
        self.configure_tags_fixed()
        if self.context.viewer is self:
            self.text.config(takefocus=1)
        self.text.bind("<Tab>", self.tab_event)
        self.text.bind("<Shift-Tab>", self.shift_tab_event)
        self.text.bind("<Button-1>", self.button_1_event)
        self.text.bind("<Button-2>", self.button_2_event)
        self.text.bind("<Button-3>", self.button_3_event)
        self.frame.bind("<Button-3>", self.button_3_event)

    def init_presentation(self):
        self.SHOW_TITLES = self.prefs.GetBoolean(
            'presentation',  'show-link-titles')
        self.hovering_enabled = self.prefs.GetBoolean(
            'presentation', 'hover-on-links')

    def configure_presentation(self):
        self.init_presentation()
        if self.hovering_enabled:
            foreground = self.prefs.Get(
                'presentation', 'hover-foreground')
            underline = self.prefs.Get(
                'presentation', 'hover-underline')
        else:
            foreground = underline = None
        self.text.tag_configure(
            'hover', foreground=foreground, underline=underline)

    def init_styles(self):
        self.configure_styles(new_styles=1)

    def configure_styles(self, new_styles=0):
        """Used on widget creation, clear, and as a callback when style
        preferences change."""
        try:
            self.configure_tags(self.stylesheet)
        except UndefinedStyle:
            pass
        self.configure_presentation()

    def configure_tags(self, stylesheet):
        if self.text:
            if not self.parent:
                # Top level viewer.
                current_cursor = self.current_cursor
                self.set_cursor(CURSOR_WAIT)

            self.text.config(stylesheet.default)
            use_font_dingbats = 1
            # Build tags that we might be using or have special semantics;
            # other font tags will be configured dynamically.
            for tag in ['_ding'] + self.__fonttags_built.keys():
                try:
                    self.configure_fonttag(tag)
                except TclError, err:
                    # This extra logic is needed to switch to gif-based
                    # dingbats if the font is not available in the current
                    # size.
                    if tag == '_ding':
                        use_font_dingbats = 0
                    else:
                        raise TclError, err, sys.exc_traceback
                else:
                    if tag == '_ding':
                        try:
                            fontname = self.stylesheet.styles[tag]['font']
                            fontname = self.text.tk.call('font', 'create',
                                                         '-family', fontname)
                            if string.find(fontname, 'dingbat') == -1:
                                use_font_dingbats = 0
                        except TclError:
                            pass            # pre-8.0 Tk
            #
            # Set dingbat approach appropriately:
            #
            if use_font_dingbats:
                for name, value in font_dingbats.items():
                    self.context.app.set_dingbat(name, value)
            else:
                map(self.context.app.clear_dingbat, font_dingbats.keys())
            #
            for tag, cnf in stylesheet.history.items():
                self.text.tag_configure(tag, cnf)
            self.text.tag_add('hover', '0.1', '0.1')
            self.text.tag_raise('ahist', 'a')
            self.text.tag_raise('hover', 'ahist')
            self.text.tag_raise('atemp', 'hover')

            if not self.parent:
                self.resize_event()
                self.set_cursor(current_cursor)
            self.init_presentation()

    def configure_tags_fixed(self):
        # These are used in aligning block-level elements:
        self.text.tag_configure('right', justify='right')
        self.text.tag_configure('center', justify='center')
        #  Typographic controls:
        self.text.tag_configure('pre', wrap='none')
        self.text.tag_configure('underline', underline=1)
        self.text.tag_configure('overstrike', overstrike=1)
        self.text.tag_configure('red', foreground='red')
        self.text.tag_configure('ins', foreground='darkgreen')
        # Configure margin tags
        for level in range(1, 20):
            pix = level * INDENTATION_WIDTH
            self.text.tag_configure('margin_%d' % level,
                                    lmargin1=pix, lmargin2=pix)
            self.text.tag_configure('rightmargin_%d' % level, rmargin=pix)
            tabs = "%d right %d left" % (pix-5, pix)
            self.text.tag_configure('label_%d' % level,
                                    lmargin1=pix-INDENTATION_WIDTH, tabs=tabs)
        # Configure anchor tags
        for tag in 'a', 'ahist':
            self.text.tag_bind(tag, '<ButtonPress-1>', self.anchor_press)
            self.text.tag_bind(tag, '<Shift-ButtonPress-1>',
                               self.shift_anchor_press)
            self.text.tag_bind(tag, '<ButtonPress-2>', self.anchor_press)
            self.text.tag_bind(tag, '<ButtonRelease-1>', self.anchor_click)
            self.text.tag_bind(tag, '<ButtonRelease-2>', self.anchor_click_new)
            self.text.tag_bind(tag, '<Leave>', self.anchor_leave)

    def configure_fonttag(self, tag):
        # configure a single font
        if self.__fonttags_built is None:
            self.__fonttags_built = {}
        self.__fonttags_built[tag] = tag
        apply(self.text.tag_configure, (tag,), self.stylesheet.styles[tag])

    def bind_anchors(self, tag):
        # Each URL must have a separate binding so moving between
        # adjacent anchors updates the URL shown in the feedback area
        self.text.tag_bind(tag, '<Enter>', self.anchor_enter)
        # XXX Don't tag bindings need to be garbage-collected?

    def register_interest(self, interests, func):
        interests.append(func)

    def unregister_interest(self, interests, func):
        found = -1
        for i in range(len(interests)):
            if interests[i] == func:
                found = i
        if found < 0:
            print "resize interest", func, "not registered"
            return
        del interests[found]

    def register_reset_interest(self, func):
        self.register_interest(self.reset_interests, func)

    def unregister_reset_interest(self, func):
        self.unregister_interest(self.reset_interests, func)

    def register_resize_interest(self, func):
        self.register_interest(self.resize_interests, func)

    def unregister_resize_interest(self, func):
        self.unregister_interest(self.resize_interests, func)

    def clear_reset(self):
        self._atemp = []
        for func in self.reset_interests[:]:
            func(self)
        # XXX Eventually the following code should be done using interests too
        subwindows = self.subwindows + self.rules
        subviewers = self.subviewers
        self.subwindows = []
        self.rules = []
        self.subviewers = []
        for viewer in subviewers:
            viewer.close()
        for w in subwindows:
            w.destroy()
        if self.text:
            self.pendingdata = ''
            self.unfreeze()
            self.text.delete('1.0', END)
            self.freeze()
            self.text.config(background=self.default_bg,
                             foreground=self.default_fg)
            self.configure_styles()
            self.reset_state()

    def tab_event(self, event):
        w = self.text.tk_focusNext()
        if w:
            w.focus_set()
        return 'break'

    def shift_tab_event(self, event):
        w = self.text.tk_focusPrev()
        if w:
            w.focus_set()
        return 'break'

    def button_1_event(self, event):
        self.context.viewer.text.focus_set()
        self.current_index = self.text.index(CURRENT) # For anchor_click

    def button_2_event(self, event):
        self.current_index = self.text.index(CURRENT) # For anchor_click_new

    def button_3_event(self, event):
        url = self.find_tag_url()
        if url:
            url, target = self.split_target(self.context.get_baseurl(url))
            self.add_temp_tag()
        self.open_popup_menu(event, link_url=url)

    def open_popup_menu(self, event, link_url=None, image_url=None):
        if not self.popup_menu:
            self.popup_menu = ViewerMenu(self.text, self)
        self.popup_menu.set_link_url(link_url)
        self.popup_menu.set_image_url(image_url)
        self.popup_menu.tk_popup(event.x_root, event.y_root)

    def resize_event(self, event=None):
        for func in self.resize_interests:
            func(self)

    def resize_rules(self):
        for rule in self.rules:
            rule["width"] = rule.get_width()

    def unfreeze(self):
        self.text['state'] = NORMAL

    def freeze(self, update=0):
        if self.pendingdata and strip(self.pendingdata):
            self.text.insert(END, self.pendingdata, self.flowingtags)
            self.pendingdata = ''
        if self.smoothscroll:
            from supertextbox import resize_super_text_box
            resize_super_text_box(frame=self.frame)
        self.text['state'] = DISABLED
        if update:
            self.text.update_idletasks()

    def flush(self):
        if self.pendingdata:
            self.text.insert(END, self.pendingdata, self.flowingtags)
            self.pendingdata = ''

    def scroll_page_down(self, event=None):
        self.text.tk.call('tkScrollByPages', self.text.vbar, 'v', 1)

    def scroll_page_up(self, event=None):
        self.text.tk.call('tkScrollByPages', self.text.vbar, 'v', -1)

    def scroll_line_down(self, event=None):
        self.text.tk.call('tkScrollByUnits', self.text.vbar, 'v', 1)

    def scroll_line_up(self, event=None):
        self.text.tk.call('tkScrollByUnits', self.text.vbar, 'v', -1)

    def new_tags(self, doit_now = 0):
        if self.pendingdata and strip(self.pendingdata):
            self.text.insert(END, self.pendingdata, self.flowingtags)
            self.pendingdata = ''
        self.flowingtags = filter(
            None,
            (self.align, self.fonttag, self.margintag, self.rightmargintag,
             self.spacingtag) + self.addtags)

    # AbstractWriter methods

    def new_alignment(self, align):
##      print "New alignment:", align
        if align == 'left': align = None
        self.align = align
        self.new_tags()

    def new_font(self, font):
##      print "New font:", font
        if font:
            tag = self.make_fonttag(font)
        else:
            tag = None
        if tag != self.fonttag:
            self.flush()
            self.fonttag = tag
        self.new_tags()

    def make_fonttag(self, (tag, i, b, tt)):
        tag = tag or ''
        if tt: tag = tag + '_tt'
        if b: tag = tag + '_b'
        if i: tag = tag + '_i'
        if tag:
            if self.__fonttags_built and self.__fonttags_built.has_key(tag):
                return tag
            self.configure_fonttag(tag)
        return tag or None

    def get_font(self, spec=None):
        tag = self.fonttag
        if spec:
            tag = self.make_fonttag(spec)
        if tag:
            font = self.text.tag_cget(tag, '-font')
        else:
            font = self.text["font"]
        return font

    def new_margin(self, margin, level):
##      print "New margin:", margin, level
        self.marginlevel = level
        self.margintag = level and ('margin_%d' % level)
        self.new_tags()

    def new_spacing(self, spacing):
        self.spacingtag = spacingtag
        self.new_tags()

    def new_styles(self, styles):
##      print 'New styles:', styles
        self.addtags = styles
        if self.pendingdata:
            self.text.insert(END, self.pendingdata, self.flowingtags)
            self.pendingdata = ''
        self.rightmarginlevel = rl = map(None, styles).count('blockquote')
        self.rightmargintag = rl and ('rightmargin_%d' % rl) or None
        self.flowingtags = filter(
            None,
            (self.align, self.fonttag, self.margintag, self.rightmargintag,
             self.spacingtag) + styles)

    def send_paragraph(self, blankline):
        self.pendingdata = self.pendingdata + ('\n' * blankline)
##      self.text.update_idletasks()

    def send_line_break(self):
        self.pendingdata = self.pendingdata + '\n'
##      self.text.update_idletasks()

    def width_magic(self, abswidth, percentwidth):
        return WidthMagic(self, abswidth, percentwidth)

    def send_hor_rule(self, abswidth=None, percentwidth=1.0,
                      height=None, align=None):
        window = HRule(self, abswidth, percentwidth, height=(height or 0))
        self.rules.append(window)
        self.prepare_for_insertion(align)
        self.add_subwindow(window)
        del self.subwindows[-1]
        self.send_line_break()
##      self.text.update_idletasks()

    RULE_WIDTH_MAGIC = 10

    def send_label_data(self, data):
##      print "Label data:", `data`
        tags = self.flowingtags + ('label_%d' % self.marginlevel,)
        data_type = type(data)
        if data_type is StringType:
            self.text.insert(END, self.pendingdata, self.flowingtags,
                             '\t%s\t' % data, tags)
            self.pendingdata = ''
        elif data_type is TupleType:
            #  (string, fonttag) pair
            data, fonttag = data
            if fonttag:
                self.text.insert(END, self.pendingdata, self.flowingtags,
                                 '\t', tags,
                                 data, tags + (fonttag,))
                self.text.tag_raise(fonttag)
                self.pendingdata = '\t'
            else:
                self.text.insert(END, self.pendingdata, self.flowingtags,
                                 '\t%s\t' % data, tags)
                self.pendingdata = ''
        elif data_type is InstanceType:
            #  Some sort of image specified by DINGBAT or SRC
            self.text.insert(END, self.pendingdata, self.flowingtags,
                             '\t', tags)
            self.pendingdata = ''
            window = Label(self.text, image = data,
                           background = self.text['background'],
                           borderwidth = 0)
            self.add_subwindow(window, align=BASELINE)
            self.pendingdata = '\t'

    def send_flowing_data(self, data):
##      print "Flowing data:", `data`, self.flowingtags
        self.pendingdata = self.pendingdata + data

    def send_literal_data(self, data):
##      print "Literal data:", `data`, self.flowingtags + ('pre',)
        self.text.insert(END, self.pendingdata, self.flowingtags,
                         data, self.flowingtags + ('pre',))
        self.pendingdata = ''

    # Viewer's own methods

    SHOW_TITLES = 0
    def anchor_enter(self, event):
        tagurl = self.find_tag_url()
        url, target = self.split_target(tagurl)
        message = ''
        if url:
            if self.SHOW_TITLES:
                absurl = self.context.get_baseurl(url)
                ghist = self.context.app.global_history
                title, when = ghist.lookup_url(absurl)
                if title:
                    message = string.join(string.split(title))
            self.text.tag_remove('hover', '0.1', END)
            ranges = self.find_tag_ranges()
            split = string.split
            point = map(int, split(self.text.index(CURRENT), '.'))
            for start, end in ranges:
                startv = map(int, split(start, '.'))
                endv = map(int, split(end, '.'))
                if startv <= point < endv:
                    self.text.tag_add('hover', start, end)
                    break
        if not message:
            url = url or "???"
            if not target:
                target = self.context.get_target()
            if target:
                message = "%s in %s" % (url, target)
            else:
                message = url
        self.enter_message(message)

    def enter_message(self, message):
        self.linkinfo = message
        self.status.set(message)
        self.context.browser.messagevariable(self.status)
        self.set_cursor(CURSOR_LINK)

    def anchor_leave(self, event):
        self.text.tag_remove('hover', '1.0', END)
        self.leave_message()

    def leave_message(self):
        self.linkinfo = ""
        self.context.message_clear()

    def anchor_press(self, event):
        self._shifted = 0
        self.context.viewer.text.focus_set()
        self.current_index = self.text.index(CURRENT) # For anchor_click
        url = self.find_tag_url()
        if url:
            self.add_temp_tag()

    def shift_anchor_press(self, event):
        self.anchor_press(event)
        self._shifted = 1

    def anchor_click(self, event):
        here = self.text.index("@%d,%d" % (event.x, event.y))
        if self.current_index != here:
            self.remove_temp_tag()
            return
        url = self.find_tag_url()
        if url:
            self.linkinfo = ""
            url, target = self.split_target(self.context.get_baseurl(url))
            if self._shifted:
                self.remove_temp_tag(
                    histify=self.context.save_document(url))
            else:
                self.context.follow(url, target)

    def anchor_click_new(self, event):
        here = self.text.index("@%d,%d" % (event.x, event.y))
        if self.current_index != here:
            return
        url = self.find_tag_url()
        if url:
            url, target = self.split_target(url)
            self.master.update_idletasks()
            from Browser import Browser
            app = self.context.app
            b = Browser(app.root, app)
            b.context.load(self.context.get_baseurl(url))
            self.remove_temp_tag(histify=1)

    def split_target(self, url):
        i = string.find(url, TARGET_SEPARATOR)
        if i < 0: return url, ""
        return url[:i], url[i+1:]

    def add_temp_tag(self):
        list = self.find_tag_ranges()
        if list:
            self._atemp = list
            for (start, end) in list:
                self.text.tag_add('atemp', start, end)

    def remove_temp_tag(self, histify=0):
        for (start, end) in self._atemp:
            self.text.tag_remove('atemp', start, end)
        if histify:
            for (start, end) in self._atemp:
                self.text.tag_add('ahist', start, end)
        self._atemp = []

    def find_tag_ranges(self):
        for tag in self.text.tag_names(CURRENT):
            if tag[0] == '>':
                raw = self.text.tag_ranges(tag)
                list = []
                for i in range(0, len(raw), 2):
                    list.append((raw[i], raw[i+1]))
                return list
        return ()

    def find_tag_url(self):
        for tag in self.text.tag_names(CURRENT):
            if tag[0] == '>':
                return tag[1:]

    def find_tag_label(self):
        for tag in self.text.tag_names(CURRENT):
            if tag[0] == '#':
                return tag[1:]

    def get_cursor(self):
        return self.current_cursor

    def set_cursor(self, cursor):
        if cursor != self.current_cursor:
            self.text['cursor'] = self.current_cursor = cursor
            if cursor == CURSOR_WAIT:
                self.text.update_idletasks()

    def scrollpos(self): return self.text.index('@0,0')
    def scroll_to_position(self, pos): self.text.yview(pos)

    def clear_targets(self):
        targs = self.targets.keys()
        if targs:
            apply(self.text.mark_unset, tuple(targs))

    def add_target(self, fragment):
        if self.pendingdata:
            self.text.insert(END, self.pendingdata, self.flowingtags)
            self.pendingdata = ''
        self.text.mark_set(fragment, END + ' - 1 char')
        self.text.mark_gravity(fragment, 'left')
        self.targets[fragment] = 1

    def scroll_to(self, fragment):
        fragment = '#' + fragment
        if self.targets.has_key(fragment):
            r = self.text.tag_nextrange(fragment, '1.0')
            if not r:
                #  Maybe an empty target; try the mark database:
                try:
                    first = self.text.index(fragment)
                except TclError:
                    return              # unknown mark
                #  Highlight the entire line:
                r = (first,
                     `1 + string.atoi(string.splitfields(first,'.')[0])` \
                     + '.0')
        else:
            r = self.parse_range(fragment)
            if not r:
                return
        first, last = r
        self.text.yview(first)
        self.text.tag_remove(SEL, '1.0', END)
        self.text.tag_add(SEL, first, last)

    def clear_selection(self):
        self.text.tag_remove(SEL, '1.0', END)

    def parse_range(self, fragment):
        try:
            p = self.range_pattern
        except AttributeError:
            import regex
            p = regex.compile('#\([0-9]+\.[0-9]+\)-\([0-9]+\.[0-9]+\)')
            self.range_pattern = p
        if p.match(fragment) == len(fragment):
            return p.group(1, 2)
        else:
            return None

    def prepare_for_insertion(self, align=None):
        if align:
            if align == 'left':
                align = None
        else:
            align = self.align
        prev_align, self.align = self.align, align
        self.new_tags()
        self.pendingdata = self.pendingdata + MIN_IMAGE_LEADER
        self.align = prev_align
        self.new_tags()

    def add_subwindow(self, window, align=CENTER, index=END):
        if self.pendingdata:
            self.text.insert(END, self.pendingdata, self.flowingtags)
            self.pendingdata = ''
        window.bind("<Button-3>", self.button_3_event)
        self.subwindows.append(window)
        self.text.window_create(index, window=window, align=align)

    def add_subviewer(self, subviewer):
        self.flush()
        self.subviewers.append(subviewer)

    def remove_subviewer(self, subviewer):
        if subviewer in self.subviewers:
            self.subviewers.remove(subviewer)

    def make_subviewer(self, master, name="", scrolling="auto"):
        depth = 0
        v = self
        while v:
            depth = depth + 1
            v = v.parent
        if depth > 5:
            return None                 # Ridiculous nesting
        viewer = Viewer(master=master,
                        browser=self.context.browser,
                        stylesheet=self.stylesheet,
                        name=name,
                        scrolling=scrolling,
                        parent=self)
        viewer.context.set_baseurl(self.context.get_baseurl())
        return viewer

    def find_subviewer(self, name):
        if self.name == name:
            return self
        for v in self.subviewers:
            v = v.find_subviewer(name)
            if v:
                return v

    def find_parentviewer(self):
        return self.parent


class ViewerMenu:
    __have_link = 0
    __have_image = 0
    __link_url = None
    __image_url = None
    __image_file = ""
    __image_prev = None

    def __init__(self, master, viewer):
        self.__menu = menu = Menu(master, tearoff=0)
        self.__context = context = viewer.context
        self.__viewer = viewer
        menu.add_command(label="Back in Frame", command=context.go_back)
        menu.add_command(label="Forward in Frame",
                         command=context.go_forward)
        menu.add_command(label="Reload Frame",
                         command=context.reload_page)
        menu.add_command(label="Open Frame in New Window",
                         command=self.__open_in_new)
        menu.add_separator()
        menu.add_command(label="Frame History...",
                         command=context.show_history_dialog)
        menu.add_separator()
        menu.add_command(label="View Frame Source",
                         command=context.view_source)
        import DocumentInfo
        menu.add_command(label="Document Info...",
                         command=DocumentInfo.DocumentInfoCommand(viewer))
        self.__source_item = menu.index(END)
        menu.add_command(label="Print Frame...",
                         command=context.print_document)
        menu.add_command(label="Save Frame As...",
                         command=context.save_document)
        self.__last_standard_index = menu.index(END)
        menu.bind("<Unmap>", self.__unmap)

    def tk_popup(self, x, y):
        # update the "Forward in Frame" item
        context = self.__context
        future, page = context.history.peek(+1)
        self.__menu.entryconfig(1, state=(page and NORMAL or DISABLED))
        #
        # update the "Back in Frame" item
        viewer = self.__viewer
        future, page = context.history.peek(-1)
        while viewer.parent and not page:
            viewer = viewer.parent
            context = viewer.context
            future, page = context.history.peek(-1)
        self.__menu.entryconfig(0, state=(page and NORMAL or DISABLED))
        #
        # update the "Open Frame in New Window" item
        # (disable if there is no parent frame)
        parent = self.__context.viewer.parent
        self.__menu.entryconfig(3, state=(parent and NORMAL or DISABLED))
        #
        need_link = self.__link_url and 1 or 0
        need_image = self.__image_url and 1 or 0
        if (need_link != self.__have_link
            or need_image != self.__have_image
            or self.__image_prev != self.__image_file):
            if self.__have_link or self.__have_image:
                self.__menu.delete(self.__last_standard_index + 1, END)
                self.__have_link = self.__have_image = 0
            if need_link:
                self.__add_link_items()
            if need_image:
                self.__add_image_items()
            self.__menu.update_idletasks()
        self.__menu.tk_popup(x, y)

    def set_link_url(self, url):
        self.__link_url = url or None

    def set_image_url(self, url):
        self.__image_url = url or ""
        url = self.__context.get_baseurl(url)
        if len(url) < 5 or string.lower(url[:5]) != "data:":
            from posixpath import basename
            self.__image_file = basename(urlparse(url)[2])
        else:
            self.__image_file = ""

    def __add_image_items(self):
        self.__have_image = 1
        self.__menu.add_separator()
        self.__image_prev = self.__image_file
        self.__menu.add_command(label="Open Image " + self.__image_file,
                                command=self.__open_image)
        self.__menu.add_command(label="Save Image %s..." % self.__image_file,
                                command=self.__save_image)
        self.__menu.add_command(label="Copy Image Location",
                                command=self.__select_image_url)

    def __add_link_items(self):
        self.__have_link = 1
        self.__menu.add_separator()
        self.__menu.add_command(label="Bookmark Link",
                                command=self.__bkmark_link)
        self.__menu.add_command(label="Print Link...",
                                command=self.__print_link)
        self.__menu.add_command(label="Save Link As...",
                                command=self.__save_link)
        self.__menu.add_command(label="Copy Link Location",
                                command=self.__select_link_url)

    __selection = ''
    def __select_image_url(self, event=None):
        self.__select(self.__context.get_baseurl(self.__image_url))

    def __select_link_url(self, event=None):
        self.__select(self.__context.get_baseurl(self.__link_url))

    def __select(self, selection):
        self.__selection = selection
        self.__viewer.text.selection_handle(self.__selection_handler)
        self.__viewer.text.selection_own()

    def __selection_handler(self, offset, maxbytes):
        offset = string.atoi(offset)
        maxbytes = string.atoi(maxbytes)
        endpos = min(maxbytes + offset, len(self.__selection))
        return self.__selection[offset:endpos]

    def __bkmark_link(self, event=None):
        try:
            bmarks = self.__context.browser.app.bookmarks_controller
        except AttributeError:
            import BookmarksGUI
            bmarks = BookmarksGUI.BookmarksController(
                self.__context.browser.app)
            self.__context.browser.app.bookmarks_controller = bmarks
        bmarks.add_link(self.__context.get_baseurl(self.__link_url))

    def __print_link(self, event=None):
        context = self.__copy_context()
        context.print_document()
        context.browser.remove()

    def __save_link(self, event=None):
        self.__viewer.remove_temp_tag(
            histify=self.__context.save_document(self.__link_url))

    def __open_image(self, event=None):
        self.__context.follow(self.__image_url)

    def __save_image(self, event=None):
        self.__context.save_document(self.__image_url)

    class DummyBrowser:
        context = None

        def __init__(self, browser):
            self.app = browser.context.app
            self.root = browser.root
            self.master = browser.master
            # this is the really evil part:
            #app.browsers.append(self)

        def remove(self):
            # remove faked out connections to other objects
            #self.app.browsers.remove(self)
            self.context = self.app = self.root = None

        def message(self): pass

    def __copy_context(self, url=None):
        # copy context and set to link target
        br = self.DummyBrowser(self.__context.browser)
        context = SimpleContext(self.__context.viewer, br)
        context._url = context._baseurl = url or self.__link_url
        br.context = context
        return context

    def __unmap(self, event=None):
        if self.__link_url:
            self.__viewer.remove_temp_tag()

    def __open_in_new(self, event=None):
        from Browser import Browser
        url = self.__context.get_url()
        b = Browser(self.__context.browser.master, self.__context.app)
        b.context.load(url)


def test():
    """Test the Viewer class."""
    import sys
    file = "Viewer.py"
    if sys.argv[1:]: file = sys.argv[1]
    f = open(file)
    data = f.read()
    f.close()
    root = Tk()
    v = Viewer(root, None)
    v.handle_data(data)
    root.mainloop()


if __name__ == '__main__':
    test()
