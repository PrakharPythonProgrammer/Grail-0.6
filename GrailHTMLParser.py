"""HTML parser class with support for applets and other Grail features."""

# XXX Need to split this in a perfectly safe module that knows about
# XXX anchors, images and subwindows, and a less safe module that
# XXX supports embedded applets.


from Tkinter import *
import os
import urllib
import urlparse
import string
import tktools
import formatter
import Viewer
import grailutil

from grailutil import extract_attribute, extract_keyword
from sgml.HTMLParser import HTMLParser, HeaderNumber


AS_IS = formatter.AS_IS

# Get rid of some methods so we can implement as extensions:
if hasattr(HTMLParser, 'do_isindex'):
    del HTMLParser.do_isindex
if hasattr(HTMLParser, 'do_link'):
    del HTMLParser.do_link

_inited = 0

def init_module(prefs):
    for opt in (1, 2, 3, 4, 5, 6):
        fmt = prefs.Get('parsing-html', 'format-h%d' % opt)
        HeaderNumber.set_default_format(opt - 1, eval(fmt))


class GrailHTMLParser(HTMLParser):

    object_aware_tags = ['param', 'a', 'alias', 'applet', 'script', 'object']

    def __init__(self, viewer, reload=0):
        global _inited
        self.viewer = viewer
        self.reload = reload
        self.context = self.viewer.context
        self.app = self.context.app
        self.load_dingbat = self.app.load_dingbat
        self.loaded = []
        self.current_map = None
        self.target = None
        self.formatter_stack = []
        fmt = formatter.AbstractFormatter(self.viewer)
        HTMLParser.__init__(self, fmt)
        self.push_formatter(fmt)
        if not _inited:
            _inited = 1
            init_module(self.app.prefs)
        self._ids = {}
        # Hackery so reload status can be reset when all applets are loaded
        import AppletLoader
        self.reload1 = self.reload and AppletLoader.set_reload(self.context)
        if self.reload1:
            self.reload1.attach(self)
        if self.app.prefs.GetBoolean('parsing-html', 'strict'):
            self.sgml_parser.restrict(0)
        # Information from <META ... CONTENT="..."> is collected here.
        # Entries are KEY --> [(NAME, HTTP-EQUIV, CONTENT), ...], where
        # KEY is (NAME or HTTP-EQUIV).
        self._metadata = {}

    def close(self):
        HTMLParser.close(self)
        if self.reload1:
            self.reload1.detach(self)
        self.reload1 = None
        refresh = None
        if self._metadata.has_key("refresh"):
            name, http_equiv, refresh = self._metadata["refresh"][0]
        elif self.context.get_headers().has_key("refresh"):
            refresh = self.context.get_headers()["refresh"]
        if refresh:
            DynamicReloader(self.context, refresh)

    # manage the formatter stack
    def get_formatter(self):
        return self.formatter_stack[-1]

    def push_formatter(self, formatter):
        self.formatter_stack.append(formatter)
        self.set_formatter(formatter)

    def pop_formatter(self):
        del self.formatter_stack[-1]
        self.set_formatter(self.formatter_stack[-1])

    def set_formatter(self, formatter):
        self.formatter = formatter      ## in base class
        self.viewer = formatter.writer
        self.context = self.viewer.context
        if self.nofill:
            self.set_data_handler(formatter.add_literal_data)
        else:
            self.set_data_handler(formatter.add_flowing_data)

    # Override HTMLParser internal methods

    def get_devicetypes(self):
        """Return sequence of device type names."""
        return ('viewer', 'writer')

    def register_id(self, id):
        if self._ids.has_key(id):
            self.badhtml = 1
            return 0
        self._ids[id] = id
        self.viewer.add_target('#' + id)
        return 1

    def anchor_bgn(self, href, name, type, target="", id=None):
        self.anchor = href
        self.target = target
        atag, utag, idtag = None, None, None
        if href:
            atag = 'a'
            if target:
                utag = '>%s%s%s' % (href, Viewer.TARGET_SEPARATOR, target)
            else:
                utag = '>' + href
            self.viewer.bind_anchors(utag)
            hist = self.app.global_history
            if hist.inhistory_p(self.context.get_baseurl(href)):
                atag = 'ahist'
        if id and self.register_id(id):
            idtag = id and ('#' + id) or None
        if name and self.register_id(name):
            self.formatter.push_style(atag, utag, '#' + name, idtag)
        else:
            self.formatter.push_style(atag, utag, None, idtag)

    def anchor_end(self):
        self.formatter.pop_style(4)
        self.anchor = self.target = None

    def do_hr(self, attrs):
        if attrs.has_key('src') and self.app.load_images:
            align = extract_keyword('align', attrs, default='center',
                    conv=lambda s,gu=grailutil: gu.conv_enumeration(
                        gu.conv_normstring(s), ['left', 'center', 'right']))
            self.implied_end_p()
            self.formatter.push_alignment(align)
            self.do_img({'border': '0', 'src': attrs['src']})
            self.formatter.pop_alignment()
            self.formatter.add_line_break()
            return
        HTMLParser.do_hr(self, attrs)
        color = extract_keyword('color', attrs)
        rule = self.viewer.rules[-1]
        if attrs.has_key('noshade') and self.viewer.rules:
            if color:
                if not self.configcolor('background', color, widget=rule):
                    self.configcolor('background',
                                     self.viewer.text['foreground'],
                                     widget=rule)
            else:
                # this color is known to work already
                rule.config(background=self.viewer.text['foreground'])
            rule.config(relief=FLAT)
            size = extract_keyword('size', attrs, 2,
                                   conv=grailutil.conv_integer)
            if size == 1:
                # could not actually set it to 1 unless it was flat; do it now:
                width = string.atoi(rule.cget('width'))
                rule.config(borderwidth=0, height=1, width=width+2)
        elif color:
            self.configcolor('background', color, widget=rule)

    # Duplicated from htmllib.py because we want to have the border attribute
    def do_img(self, attrs):
        align, usemap = BASELINE, None
        extract = extract_keyword
        ## align = extract('align', attrs, align, conv=conv_align)
        alt = extract('alt', attrs, '(image)')
        border = extract('border', attrs, self.anchor and 2 or None,
                         conv=string.atoi)
        ismap = attrs.has_key('ismap')
        if ismap and border is None: border = 2
        src = extract('src', attrs, '')
        width = extract('width', attrs, 0, conv=string.atoi)
        height = extract('height', attrs, 0, conv=string.atoi)
        hspace = extract('hspace', attrs, 0, conv=string.atoi)
        vspace = extract('vspace', attrs, 0, conv=string.atoi)
        # not sure how to assert(value[0] == '#')
        usemap = extract('usemap', attrs, conv=string.strip)
        if usemap:
            if usemap[0] == '#': value = string.strip(usemap[1:])
            from ImageMap import MapThunk
            usemap = MapThunk(self.context, usemap)
            if border is None: border = 2
        self.handle_image(src, alt, usemap, ismap,
                          align, width, height, border or 0, self.reload1,
                          hspace=hspace, vspace=vspace)

    def handle_image(self, src, alt, usemap, ismap, align, width,
                     height, border=2, reload=0, hspace=0, vspace=0):
        if not self.app.prefs.GetBoolean("browser", "load-images"):
            self.handle_data(alt)
            return
        from ImageWindow import ImageWindow
        window = ImageWindow(self.viewer, self.anchor, src, alt or "(Image)",
                             usemap, ismap, align, width, height,
                             border, self.target, reload)
        self.add_subwindow(window, align=align, hspace=hspace, vspace=vspace)

    def add_subwindow(self, w, align=CENTER, hspace=0, vspace=0):
        self.formatter.flush_softspace()
        if self.formatter.nospace:
            # XXX Disgusting hack to tag the first character of the line
            # so things like indents and centering work
            self.viewer.prepare_for_insertion()
        self.viewer.add_subwindow(w, align=align)
##      if hspace or vspace:
##          self.viewer.text.window_config(w, padx=hspace, pady=vspace)
        self.formatter.assert_line_data()

    # Extend tag: </TITLE>

    def end_title(self):
        HTMLParser.end_title(self)
        self.context.set_title(self.title)
        if not self.inhead:
            self.badhtml = 1

    # Override tag: <BODY colorspecs...>

    def start_body(self, attrs):
        HTMLParser.start_body(self, attrs)
        if not self.app.prefs.GetBoolean('parsing-html', 'honor-colors'):
            return
        from grailutil import conv_normstring
        bgcolor = extract_keyword('bgcolor', attrs, conv=conv_normstring)
        if bgcolor:
            clr = self.configcolor('background', bgcolor)
            if clr:
                #  Normally not important, but ISINDEX would cause
                #  these to be non-empty, as would all sorts of illegal stuff:
                for hr in self.viewer.rules + self.viewer.subwindows:
                    hr.config(highlightbackground = clr)
        self.configcolor('foreground',
                         extract_keyword('text', attrs, conv=conv_normstring))
        self.configcolor('foreground',
                         extract_keyword('link', attrs, conv=conv_normstring),
                         'a')
        self.configcolor('foreground',
                         extract_keyword('vlink', attrs, conv=conv_normstring),
                         'ahist')
        self.configcolor('foreground',
                         extract_keyword('alink', attrs, conv=conv_normstring),
                         'atemp')

    # These are defined by the HTML 3.2 (Wilbur) version of HTML.
    _std_colors = {"black": "#000000",
                   "silver": "#c0c0c0",
                   "gray": "#808080",
                   "white": "#ffffff",
                   "maroon": "#800000",
                   "red": "#ff0000",
                   "purple": "#800080",
                   "fuchsia": "#ff00ff",
                   "green": "#008000",
                   "lime": "#00ff00",
                   "olive": "#808000",
                   "yellow": "#ffff00",
                   "navy": "#000080",
                   "blue": "#0000ff",
                   "teal": "#008080",
                   "aqua": "#00ffff",
                   }

    def configcolor(self, option, color, tag=None, widget=None):
        """Set a color option, returning the color that was actually used.

        If no color was set, `None' is returned.
        """
        if not color:
            return None
        if not widget:
            widget = self.viewer.text
        c = try_configcolor(option, color, tag, widget)
        if color[0] != '#' and not c:
            c = try_configcolor(option, '#' + color, tag, widget)
        if not c and self._std_colors.has_key(color):
            color = self._std_colors[color]
            c = try_configcolor(option, color, tag, widget)
        return c

    # Override tag: <BASE HREF=...>

    def do_base(self, attrs):
        base = None
        target = None
        if attrs.has_key('href'):
            base = attrs['href']
        if attrs.has_key('target'):
            target = attrs['target']
        self.context.set_baseurl(base, target)

    # Override tag: <META ...>

    def do_meta(self, attrs):
        # CONTENT='...' is required;
        # at least one of HTTP-EQUIV=xyz or NAME=xyz is required.
        if not attrs.has_key("content") \
           or not (attrs.has_key("http-equiv") or attrs.has_key("name")):
            self.badhtml = 1
            return
        name = extract_keyword("name", attrs, conv=grailutil.conv_normstring)
        http_equiv = extract_keyword("http-equiv", attrs,
                                     conv=grailutil.conv_normstring)
        key = name or http_equiv
        if not key:
            self.badhtml = 1
            return
        content = extract_keyword("content", attrs, conv=string.strip)
        item = (name, http_equiv, content)
        if self._metadata.has_key(key):
            self._metadata[key].append(item)
        else:
            entries = self._metadata[key] = [item]
        if key == "grail:parse-mode":
            content = grailutil.conv_normstring(content)
            strict = self.sgml_parser.strict_p()
            if content == "strict" and not strict:
                self.sgml_parser.restrict(0)
                self.context.message("Entered strict parsing mode on"
                                     " document request.")
            elif content == "forgiving" and strict:
                self.sgml_parser.restrict(1)
                self.context.message("Exited strict parsing mode on"
                                     " document request.")

    # Duplicated from htmllib.py because we want to have the target attribute
    def start_a(self, attrs):
        if self.get_object():           # expensive!
            self.get_object().anchor(attrs)
            return
        name = type = target = title = ''
        id = None
        has_key = attrs.has_key
        #
        href = string.strip(attrs.get("urn", ""))
        scheme, resturl = urllib.splittype(href)
        if scheme == "urn":
            scheme, resturl = urllib.splittype(resturl)
        if scheme not in ("doi", "hdl", "ietf"):
            # this is an unknown URN scheme or there wasn't a URN
            href = string.strip(attrs.get("href", ""))
        name = extract_keyword('name', attrs,
                               conv=grailutil.conv_normstring)
        if has_key('type'): type = string.lower(attrs['type'] or '')
        if has_key('target'): target = attrs['target']
        if has_key('id'): id = attrs['id']
        self.anchor_bgn(href, name, type, target, id)
        # Delay this at least a little, since we don't want to add the title
        # to the history until the last possible moment.  We need a non-history
        # way to do this; a resources database would be much better.
        if has_key('title'):
            title = string.join(string.split(attrs['title'] or ''))
            if title:
                url = self.context.get_baseurl(
                    string.joinfields(string.split(href), ''))
                old_title, when = self.app.global_history.lookup_url(url)
                if not old_title:
                    # Only do this if there's not already a title in the
                    # history.  If the URL wasn't in the history, it will
                    # be given a timestamp, which is bad. ;-(
                    self.app.global_history.set_title(url, title)

    # New tag: <MAP> (for client side image maps)

    def start_map(self, attrs):
        # ignore maps without names
        if attrs.has_key('name'):
            from ImageMap import MapInfo
            self.current_map = MapInfo(attrs['name'])
        else:
            self.badhtml = 1

    def end_map(self):
        if self.current_map:
            self.context.image_maps[self.current_map.name] = self.current_map
            self.current_map = None

    # New tag: <AREA> (goes inside a map)

    def do_area(self, attrs):
        """Handle the <AREA> tag."""

        if self.current_map:
            extract = extract_keyword
            shape = extract('shape', attrs, 'rect',
                            conv=grailutil.conv_normstring)
            if shape == 'polygon':
                shape = 'poly'
                self.badhtml = 1
            coords = extract('coords', attrs, '')
            alt = extract('alt', attrs, '')
            target = extract('target', attrs, '')
            # not sure what the point of NOHREF is
            url = extract('nohref', attrs, extract('href', attrs, ''))

            try:
                self.current_map.add_shape(
                    shape, self.parse_area_coords(shape, coords), url, target)
            except (IndexError, ValueError):
                # wrong number of coordinates
                # how should this get reported to the user?
                self.badhtml = 1
                print "imagemap specifies bad coordinates:", `coords`
                pass
        else:
            self.badhtml = 1

    def parse_area_coords(self, shape, text):
        """Parses coordinate string into list of numbers.

        Coordinates are stored differently depending on the shape of
        the object.

        Raise string.atoi_error when bad numbers occur.
        Raise IndexError when not enough coordinates are specified.
        
        """
        import regsub

        coords = []

        terms = map(string.atoi, regsub.split(string.strip(text), '[, ]+'))

        if shape == 'poly':
            # list of (x,y) tuples
            while len(terms) > 0:
                coords.append((terms[0], terms[1]))
                del terms[:2]
            if coords[0] != coords[-1:]:
                # make sure the polygon is closed
                coords.append(coords[0])
        elif shape == 'rect':
            # (x,y) tuples for upper left, lower right
            coords.append((terms[0], terms[1]))
            coords.append((terms[2], terms[3]))
        elif shape == 'circle':
            # (x,y) tuple for center, followed by int for radius
            coords.append((terms[0], terms[1]))
            coords.append(terms[2])
        return coords

    # New tag: <APPLET>

    def start_applet(self, attrs):
        # re-write the attributes to use the <OBJECT> support:
        import copy
        nattrs = copy.copy(attrs)
        if attrs.has_key('name'):
            nattrs['classid'] = attrs['name']
            del nattrs['name']
        if attrs.has_key('code') and not attrs.has_key('codebase'):
            nattrs['codebase'] = attrs['code']
            del nattrs['code']
        self.start_object(nattrs, 'applet')

    def end_applet(self):
        self.end_object()

    # New tag: <APP> (for Grail 0.2 compatibility)

    def do_app(self, attrs):
        mod, cls, src = self.get_mod_class_src(attrs)
        if not (mod and cls): return
        width = extract_attribute('width', attrs, conv=string.atoi, delete=1)
        height = extract_attribute('height', attrs, conv=string.atoi, delete=1)
        menu = extract_attribute('menu', attrs, delete=1)
        mod = mod + ".py"
        import AppletLoader
        apploader = AppletLoader.AppletLoader(
            self, code=mod, name=cls, codebase=src,
            width=width, height=height, menu=menu,
            reload=self.reload1)
        if apploader.feasible():
            for name, value in attrs.items():
                apploader.set_param(name, value)
            apploader.go_for_it()
        else:
            apploader.close()

    # Subroutines for <APP> tag parsing

    def get_mod_class_src(self, keywords):
        cls = extract_attribute('class', keywords, '', delete=1)
        src = extract_attribute('src', keywords, delete=1)
        if '.' in cls:
            i = string.rfind(cls, '.')
            mod = cls[:i]
            cls = cls[i+1:]
        else:
            mod = cls
        return mod, cls, src

    # Heading support for dingbats (iconic entities):

    def header_bgn(self, tag, level, attrs):
        HTMLParser.header_bgn(self, tag, level, attrs)
        dingbat = extract_keyword('dingbat', attrs)
        if dingbat:
            self.unknown_entityref(dingbat, '')
            self.formatter.add_flowing_data(' ')
        elif attrs.has_key('src'):
            self.do_img(attrs)
            self.formatter.add_flowing_data(' ')

    # List attribute extensions:

    def start_ul(self, attrs, tag='ul'):
        if attrs.has_key('dingbat'):
            self.list_handle_dingbat(attrs)
        elif attrs.has_key('src'):
            self.list_handle_src(attrs)
        HTMLParser.start_ul(self, attrs, tag=tag)

    def do_li(self, attrs):
        if attrs.has_key('dingbat'):
            if self.list_stack:
                if self.list_stack[-1][0] == 'ul':
                    self.list_handle_dingbat(attrs)
            else:
                self.list_handle_dingbat(attrs)
        elif attrs.has_key('src'):
            if self.list_stack:
                if self.list_stack[-1][0] == 'ul':
                    self.list_handle_src(attrs)
            else:
                self.list_handle_src(attrs)
        HTMLParser.do_li(self, attrs)

    def list_handle_dingbat(self, attrs):
        if attrs['dingbat']:
            img = self.load_dingbat(attrs['dingbat'])
            if img: attrs['type'] = img

    def list_handle_src(self, attrs):
        if not self.app.prefs.GetBoolean("browser", "load-images"):
            return
        src = string.joinfields(string.split(attrs['src']), '')
        image = self.context.get_async_image(src, self.reload)
        if image: attrs['type'] = image

    # Override make_format():
    # This allows disc/circle/square to be mapped to dingbats.

    def make_format(self, format, default='disc', listtype=None):
        fmt = format or default
        if type(fmt) is StringType:
            fmt = string.lower(fmt)
        if fmt in ('disc', 'circle', 'square'):
            if listtype == 'ul':
                img = self.load_dingbat(fmt)
                return img or HTMLParser.make_format(self, format, default,
                                                     listtype = listtype)
            else:
                return '1.'
        else:
            return HTMLParser.make_format(self, format, default,
                                          listtype = listtype)

    def report_unbalanced(self, tag):
        self.badhtml = 1

    # Handle proposed iconic entities (see W3C working drafts or HTML 3):

    def unknown_entityref(self, entname, terminator):
        if self.suppress_output:
            return
        img = self.load_dingbat(entname)
        if img:
            if type(img) is TupleType:
                s, tag = img
                if tag:
                    if tag != "_ding":
                        tag = (self.formatter.writer.fonttag or '') + tag
                    self.viewer.configure_fonttag(tag)
                    self.formatter.push_style(tag)
                    self.viewer.text.tag_raise(tag)
                    self.handle_data(s)
                    self.formatter.pop_style()
                else:
                    self.handle_data(s)
            else:
                bgcolor = self.viewer.text['background']
                label = Label(self.viewer.text, image=img,
                              background=bgcolor, borderwidth=0)
                self.add_subwindow(label)
                # this needs to be done *after* the add_subwindow()
                # call to get the right <Button-3> bindings.
                if self.anchor:
                    IconicEntityLinker(self.viewer, self.anchor,
                                       self.target, label)
        else:
            # Could not load dingbat, allow parent class to handle:
            HTMLParser.unknown_entityref(self, entname, terminator)

    def entref_nbsp(self, terminator):
        self.__do_invisible('i')

    def entref_emsp(self, terminator):
        self.__do_invisible("M")

    def entref_quad(self, terminator):
        self.__do_invisible("MMMM")

    def __do_invisible(self, s):
        #
        # This breaks using the X-Selection for cut & paste somewhat: the
        # invisible text does not get translated to space characters, so
        # whatever was used gets pasted.
        #
        self.formatter.softspace = 0
        bgcolor = self.viewer.text["background"]
        self.viewer.text.tag_config("INVISIBLE", foreground=bgcolor)
        self.formatter.push_style("INVISIBLE")
        self.handle_data(s)
        self.formatter.pop_style()
        self.formatter.nospace = 1


def try_configcolor(option, color, tag, widget):
    try:
        if tag:
            apply(widget.tag_config, (tag,), {option: color})
        else:
            widget[option] = color
    except TclError, msg:
        return None
    else:
        return color


def conv_align(val):
    # This should work, but Tk doesn't actually do the right
    # thing so for now everything gets mapped to BASELINE
    # alignment.
    return BASELINE
    conv = grailutil.conv_enumeration(
        grailutil.conv_normstring(val),
        {'top': TOP,
         'middle': CENTER,              # not quite right
         'bottom': BASELINE,
         'absbottom': BOTTOM,           # compatibility hack...
         'absmiddle': CENTER,           # compatibility hack...
         })
    if conv: return conv
    else: return CENTER


class IconicEntityLinker:
    __here = None

    def __init__(self, viewer, url, target, label):
        self.__target = target or ''
        self.__url = url
        self.__viewer = viewer
        label.bind("<ButtonPress-1>", self.button_1_press)
        label.bind("<ButtonRelease-1>", self.button_1_release)
        label.bind("<ButtonPress-2>", self.button_2_press)
        label.bind("<ButtonRelease-2>", self.button_2_release)
        label.bind("<Button-3>", self.button_3_event)
        label.bind("<Enter>", self.enter)
        label.bind("<Leave>", self.leave)

    def activate_link(self, event):
        self.__here = self.__viewer.text.index(At(event.x, event.y))
        tag = ">" + self.__url
        if self.__target:
            tag = tag + Viewer.TARGET_SEPARATOR + self.__target
        raw = self.__viewer.text.tag_ranges(tag)
        list = []
        for i in range(0, len(raw), 2):
            list.append((raw[i], raw[i+1]))
        if list:
            self.__viewer._atemp = list
            for (start, end) in list:
                self.__viewer.text.tag_add('atemp', start, end)

    def button_1_press(self, event):
        self.__viewer.text.focus_set()
        self.activate_link(event)

    def button_1_release(self, event):
        here = self.__viewer.text.index(At(event.x, event.y))
        if here == self.__here:
            self.__viewer.context.follow(self.__url, target=self.__target)

    def button_2_press(self, event):
        self.activate_link(event)

    def button_2_release(self, event):
        here = self.__viewer.text.index(At(event.x, event.y))
        if here != self.__here:
            return
        viewer = self.__viewer
        url = viewer.context.get_baseurl(self.__url)
        viewer.master.update_idletasks()
        import Browser
        app = viewer.context.app
        b = Browser.Browser(app.root, app)
        b.context.load(url)
        viewer.remove_temp_tag(histify=1)

    def button_3_event(self, event=None):
        url = self.__viewer.context.get_baseurl(self.__url)
        self.__viewer.open_popup_menu(event, link_url=url)

    def enter(self, event=None):
        target = self.__target
        if not self.__target:
            target = self.__viewer.context.get_target()
        if target:
            message = "%s in %s" % (self.__url, target)
        else:
            message = self.__url
        self.__viewer.enter_message(message)

    def leave(self, event=None):
        self.__here = None
        self.__viewer.leave_message()
        self.__viewer.remove_temp_tag()


class DynamicReloader:
    def __init__(self, context, spec):
        self.__context = context
        self.__starting_url = context.get_baseurl()
        seconds, url = self.parse(spec)
        if seconds is None:             # parse failed
            return
        self.__target_url = url
        ms = int(seconds * 1000)        # convert to milliseconds
        if ms:
            context.viewer.master.after(ms, self.load)
        else:
            self.load()

    def load(self):
        context = self.__context
        if context.get_baseurl() == self.__starting_url \
           and context.viewer.text:
            same_page = (self.__starting_url == self.__target_url)
            if same_page:
                context.load_from_history(context.history.peek(0), reload=1)
            else:
                context.load(self.__target_url)

    def parse(self, spec):
        if ";" in spec:
            pos = string.find(spec, ";")
            spec = "%s %s" % (spec[:pos], spec[pos + 1:])
        specitems = string.split(spec)
        if not specitems:
            return None, None
        try:
            seconds = string.atof(specitems[0])
        except ValueError:
            return None, None
        if seconds < 0:
            return None, None
        if len(specitems) > 1:
            specurl = specitems[1]
            if len(specurl) >= 4 and string.lower(specurl[:4]) == "url=":
                specurl = specurl[4:]
            url = self.__context.get_baseurl(specurl)
        else:
            url = self.__context.get_baseurl()
        return seconds, url
