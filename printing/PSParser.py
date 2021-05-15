"""HTML parser for printing."""

__version__ = '$Revision: 1.13 $'

import os
import string
import types
import urlparse

from formatter import AbstractFormatter
from formatter import AS_IS
from sgml.HTMLParser import HTMLParser
from sgml.utils import *

import epstools                         # in package
import utils


SIZE_STEP = 0.2


class PrintingHTMLParser(HTMLParser):

    """Class to override HTMLParser's default methods.

    Special support is provided for anchors, BASE, images, subscripts,
    and superscripts.

    Image loading is controlled by an optional parameter called
    `image_loader.'  The value of this parameter should be a function
    which resolves a URL to raw image data.  The image data should be
    returned as a string.

    If an image loader is provided, the `greyscale' parameter is used
    to determine how the image should be converted to postscript.

    The interpretation of anchor tags is controlled by two options,
    `footnote_anchors' and `underline_anchors.'  If footnote_anchors
    is true, anchors are assigned footnote numbers and the target URL
    is printed in a list appended following the body of the document.
    The underline_anchors flag controls the visual treatment of the
    anchor text in the main document.
    """
    _inited = 0
    _image_loader = None

    def __init__(self, writer, settings, context):
        if not self._inited:
            for k, v in self.fontdingbats.items():
                self.dingbats[(k, 'grey')] = v
                self.dingbats[(k, 'color')] = v
            import Greek
            for k, v in Greek.entitydefs.items():
                tup = (v, 'Symbol')
                self.dingbats[(k, 'grey')] = tup
                self.dingbats[(k, 'color')] = tup
            PrintingHTMLParser._inited = 1
        HTMLParser.__init__(self, AbstractFormatter(writer))
        if settings.strict_parsing:
            self.sgml_parser.restrict(0)
        self._baseurl = context.get_baseurl()
        self.context = context
        self.settings = settings
        if settings.imageflag:
            self._image_loader = utils.image_loader
        self._image_cache = {}
        self._anchors = {None: None}
        self._anchor_sequence = []
        self._anchor_xforms = []
        if not settings.footnoteflag:
            self.add_anchor_transform(disallow_anchor_footnotes)
        else:
            self.add_anchor_transform(
                disallow_self_reference(context.get_url()))
        self.__fontsize = [3]

    def close(self):
        if self._anchor_sequence:
            self.write_footnotes()
        HTMLParser.close(self)

    def get_devicetypes(self):
        """Return sequence of device type names."""
        return ('postscript', 'writer')

    def add_anchor_transform(self, xform):
        if xform not in self._anchor_xforms:
            self._anchor_xforms.insert(0, xform)

    def remove_anchor_transform(self, xform):
        if xform in self._anchor_xforms:
            self._anchor_xforms.remove(xform)

    def register_id(self, name):
        """Add page number of element start to internal database."""
        (scheme, netloc, path, params, query, fragment) = \
                 urlparse.urlparse(self.context.get_url())
        netloc = string.lower(netloc)
        url = urlparse.urlunparse(
            (scheme, netloc, path, params, query, name))
        pageno = self.formatter.writer.ps.get_pageno()
        self._set_docinfo(url, pageno, '')

    def do_base(self, attrs):
        HTMLParser.do_base(self, attrs)
        if self.base:
            self.context.set_baseurl(self.base)

    def __footnote_anchor(self, href, attrs):
        for xform in self._anchor_xforms:
            href = xform(href, attrs)
            if not href:
                return None
            attrs['href'] = href
        else:
            href = disallow_data_scheme(href, attrs)
        return href or None

    FOOTNOTE_DIV_ATTRIBUTES = {'align': 'left'}
    FOOTNOTE_LIST_ATTRIBUTES = {'type': '1.', 'compact': 'compact'}
    FOOTNOTE_INDICATOR_FORMAT = "[%d]"
    FOOTNOTE_HEADER = "URLs referenced in this document:"

    def write_footnotes(self):
        import copy
        self.close_paragraph()
        self.formatter.end_paragraph(1)
        self.do_hr({})
        self.start_div(copy.copy(self.FOOTNOTE_DIV_ATTRIBUTES))
        self.para_bgn({})
        self.handle_data(self.FOOTNOTE_HEADER)
        self.para_end()
        self.start_small({})
        self.start_ol(copy.copy(self.FOOTNOTE_LIST_ATTRIBUTES))
        history = self.context.app.global_history
        for anchor, title in self._anchor_sequence:
            self.do_li({})
            if not title and history:
                title, when = history.lookup_url(anchor)
            if not title:
                # Try getting this from our internal database if we haven't
                # already found it.
                pageno, title = self.get_docinfo(anchor)
            if title:
                # Set the title as a citation:
                self.start_cite({})
                self.handle_data(title)
                self.end_cite()
                self.handle_data(', ')
            self.handle_data(anchor)
        self.end_ol()
        self.end_small()
        self.end_div()

    _inanchor = 0
    def start_a(self, attrs):
        href = extract_keyword('href', attrs)
        if href:
            href = self.context.get_baseurl(href)
        self.anchor = href
        if href:
            if self.settings.underflag:
                self.formatter.push_style('underline')
                self._inanchor = 1
            if not self._anchors.has_key(href):
                href = self.anchor = self.__footnote_anchor(href, attrs)
                if self._anchors.has_key(href): return
                self._anchors[href] = len(self._anchor_sequence) + 1
                title = extract_keyword('title', attrs, '')
                title = string.join(string.split(title))
                self._anchor_sequence.append((href, title))
        else:
            self._inanchor = 0
        name = extract_keyword('name', attrs, conv=conv_normstring)
        if name:
            self.register_id(name)

    def end_a(self):
        if self.settings.underflag and self._inanchor:
            self.formatter.pop_style()
        if self.anchor:
            anchor, self.anchor = self.anchor, None
            old_size = self.formatter.writer.ps.get_fontsize()
            self.start_small({}, steps=2)
            new_size = self.formatter.writer.ps.get_fontsize()
            yshift = old_size - ((1.0 + SIZE_STEP / 2) * new_size)
            self.formatter.push_font((AS_IS, 0, 0, 0))
            self.formatter.writer.ps.push_yshift(yshift)
            self.handle_data(self.FOOTNOTE_INDICATOR_FORMAT
                             % self._anchors[anchor])
            self.formatter.writer.ps.pop_yshift()
            self.formatter.pop_font()
            self.end_small()

    def start_p(self, attrs):
        if (self.settings.paragraph_indent or self.settings.paragraph_skip) \
           and extract_keyword(
               'indent', attrs, conv=conv_normstring) != "no":
            self.para_bgn(attrs)
            if not self.formatter.have_label:
                self.formatter.writer.send_indentation(
                    self.settings.paragraph_indent)
        else:
            self.para_bgn(attrs)
        self.require_vspace(2)

    def end_p(self):
        if self.settings.paragraph_indent:
            self.para_end(parbreak=0)
        else:
            self.para_end(parbreak=1)
        self.formatter.writer.send_indentation(None)
        self.formatter.writer.suppress_indentation(0)

    def do_basefont(self, attrs):
        if attrs.has_key("size"):
            self.start_font({"size": attrs["size"]})

    def start_font(self, attrs):
        # very simple: only supports SIZE="...."
        size = None
        spec = extract_keyword('size', attrs, conv=conv_normstring)
        nsize = self.__fontsize[-1]
        op, diff = self.parse_fontsize(spec)
        if not diff:
            self.formatter.push_font((AS_IS, AS_IS, AS_IS, AS_IS))
        else:
            if op == "-":
                nsize = self.__fontsize[-1] - diff
                self.start_small({}, steps=diff)
            else:
                nsize = self.__fontsize[-1] + diff
                self.start_big({}, steps=diff)
        self.__fontsize.append(nsize)

    def parse_fontsize(self, spec):
        if not spec:
            return "+", 0
        op = ""
        if spec[0] in "-+":
            op = spec[0]
            spec = spec[1:]
        try:
            spec = string.atoi(spec)
        except ValueError:
            return "+", 0
        if op:
            return op, spec
        if spec < self.__fontsize[-1]:
            diff = self.__fontsize[-1] - spec
            return "-", diff
        diff = spec - self.__fontsize[-1]
        return "+", diff

    def end_font(self):
        del self.__fontsize[-1]
        self.formatter.pop_font()

    def end_title(self):
        HTMLParser.end_title(self)
        self.formatter.writer.ps.set_title(self.title)
        self.formatter.writer.ps.prune_titles()

    def start_small(self, attrs, steps=1):
        font_size = self.formatter.writer.ps.get_fontsize()
        while steps > 0:
            steps = steps - 1
            font_size = (1.0 - SIZE_STEP) * font_size
        self.formatter.push_font((font_size, AS_IS, AS_IS, AS_IS))

    def end_small(self):
        self.formatter.pop_font()

    def start_big(self, attrs, steps=1):
        font_size = self.formatter.writer.ps.get_fontsize()
        while steps > 0:
            steps = steps - 1
            font_size = (1.0 + SIZE_STEP) * font_size
        self.formatter.push_font((font_size, AS_IS, AS_IS, AS_IS))

    def end_big(self):
        self.end_small()

    def start_sup(self, attrs):
        font_size = self.formatter.writer.ps.get_fontsize()
        self.start_small(attrs)
        new_font_size = self.formatter.writer.ps.get_fontsize()
        yshift = font_size - ((1.0 - SIZE_STEP / 2) * new_font_size)
        self.formatter.writer.ps.push_yshift(yshift)

    def start_sub(self, attrs):
        self.start_small(attrs)
        new_font_size = self.formatter.writer.ps.get_fontsize()
        self.formatter.writer.ps.push_yshift(-(SIZE_STEP / 2) * new_font_size)

    def end_sup(self):
        self.formatter.writer.ps.pop_yshift()
        self.end_small()

    def end_sub(self):
        self.end_sup()

    def start_pre(self, attrs):
        HTMLParser.start_pre(self, attrs)
        new_size = AS_IS
        width = extract_keyword('width', attrs, 0, conv=conv_integer)
        if width > 0:
            ps = self.formatter.writer.ps
            space_width = ps._font.text_width(' ')
            pagewidth = ps.get_pagewidth()
            required = space_width * width
            if required > pagewidth:
                factor = pagewidth / required
                new_size = ps.get_fontsize() * factor
        self.formatter.push_font((new_size, AS_IS, AS_IS, AS_IS))

    def end_pre(self):
        self.formatter.pop_font()
        HTMLParser.end_pre(self)

    __docinfo = None
    def _set_docinfo(self, url, pageno, title):
        if self.__docinfo is None:
            self.__docinfo = {}
        self.__docinfo[url] = (pageno, title)

    def get_docinfo(self, url):
        if self.__docinfo and self.__docinfo.has_key(url):
            return self.__docinfo[url]
        return None, None

    # These are really hackish, but improve some things just a little:
    def start_tr(self, attrs):
        self.start_div({})

    def end_tr(self):
        self.end_div()

    def start_table(self, attrs):
        self.para_bgn({}, parbreak=0)

    def end_table(self):
        self.para_end(parbreak=0)

    def start_td(self, attrs):
        pass

    def start_th(self, attrs):
        self.formatter.push_font((AS_IS, AS_IS, 1, AS_IS))

    def end_th(self):
        self.formatter.pop_font()

    def start_caption(self, attrs):
        self.start_div({"align": "center"})
        self.formatter.writer.suppress_indentation()

    def end_caption(self):
        self.end_div()

    def handle_image(self, src, alt, ismap, align, width,
                     height, border=2, *args, **kw):
        if self.settings.imageflag:
            utils.debug("handle_image('%s', ...)" % src)
            imageurl = self.context.get_baseurl(src)
            if self._image_cache.has_key(imageurl):
                image = self._image_cache[imageurl]
            else:
                try:
                    image = self.load_image(imageurl)
                except epstools.EPSError:
                    self._image_cache[imageurl] = image = None
                else:
                    if len(image.data) < 10240:
                        self._image_cache[imageurl] = image
            if image:
                self.print_image(image, width, height, align)
            else:
                #  previous load resulted in failure:
                self.handle_data(alt)
        else:
            self.handle_data(alt)

    def print_image(self, image, width, height, align=None):
        image.reset()                   # restart scaling calculations
        if width and height:
            image.set_size(width, height)
        elif width:
            image.set_width(width)
        elif height:
            image.set_height(height)
        self.formatter.writer.send_eps_data(image, string.lower(align or ''))
        self.formatter.assert_line_data()

    def header_bgn(self, tag, level, attrs):
        HTMLParser.header_bgn(self, tag, level, attrs)
        dingbat = extract_keyword('dingbat', attrs)
        if dingbat:
            self.unknown_entityref(dingbat, '')
            self.formatter.add_flowing_data(' ')
        elif attrs.has_key('src'):
            self.do_img(attrs)
            self.formatter.add_flowing_data(' ')

    def header_end(self, tag, level):
        HTMLParser.header_end(self, tag, level)
        self.formatter.writer.suppress_indentation()

    def header_number(self, tag, level, attrs):
        # make sure we have at least 3*fontsize vertical space available:
        self.require_vspace(3)
        # now call the base class:
        HTMLParser.header_number(self, tag, level, attrs)

    def require_vspace(self, factor):
        ps = self.formatter.writer.ps
        fontsize = ps._font.font_size()
        available = ps.get_pageheight() + ps._ypos
        if available < (factor * fontsize):
            ps.push_page_break()

    def pi_page_break(self, arglist):
        self.formatter.add_line_break()
        self.formatter.writer.ps.push_page_break()

    def pi_debugging_on(self, arglist):
        self.__do_debugging(1, arglist)

    def pi_debugging_off(self, arglist):
        self.__do_debugging(0, arglist)

    def __do_debugging(self, flag, arglist):
        arglist = arglist or (None,)
        for subsystem in arglist:
            utils.set_debugging(flag, subsystem)

    # List attribute extensions:

    def start_ul(self, attrs, *args, **kw):
        self.list_check_dingbat(attrs)
        apply(HTMLParser.start_ul, (self, attrs) + args, kw)
        self.formatter.writer.suppress_indentation()

    def end_ul(self):
        HTMLParser.end_ul(self)
        self.formatter.writer.suppress_indentation(0)

    def start_dl(self, attrs):
        HTMLParser.start_dl(self, attrs)
        self.formatter.writer.suppress_indentation()

    def end_dl(self):
        HTMLParser.end_dl(self)
        self.formatter.writer.suppress_indentation(0)

    def start_ol(self, attrs):
        HTMLParser.start_ol(self, attrs)
        self.formatter.writer.suppress_indentation()

    def end_ol(self):
        HTMLParser.end_ol(self)
        self.formatter.writer.suppress_indentation(0)

    def do_li(self, attrs):
        self.list_check_dingbat(attrs)
        HTMLParser.do_li(self, attrs)
        self.formatter.writer.suppress_indentation()

    def do_dd(self, attrs):
        HTMLParser.do_dd(self, attrs)
        self.formatter.writer.suppress_indentation()

    def do_dt(self, attrs):
        HTMLParser.do_dt(self, attrs)
        self.formatter.writer.suppress_indentation()

    def list_check_dingbat(self, attrs):
        if attrs.has_key('dingbat') and attrs['dingbat']:
            img = self.load_dingbat(attrs['dingbat'])
            if img: attrs['type'] = img

    # Override make_format():
    # This allows disc/circle/square to be mapped to images.

    def make_format(self, format, default='disc', listtype = None):
        fmt = format or default
        if fmt in ('disc', 'circle', 'square') and listtype == 'ul':
            img = self.load_dingbat(fmt)
            return img or HTMLParser.make_format(self, format, default)
        else:
            return HTMLParser.make_format(self, format, default,
                                          listtype = listtype)

    def unknown_entityref(self, entname, terminator):
        dingbat = self.load_dingbat(entname)
        if type(dingbat) is types.TupleType:
            apply(self.formatter.writer.ps.push_font_string, dingbat)
            self.formatter.assert_line_data()
        elif dingbat:
            dingbat.restrict(0.9 * self.formatter.writer.ps.get_fontsize(),
                             self.formatter.writer.ps.get_pagewidth())
            self.formatter.writer.send_eps_data(dingbat, 'absmiddle')
            self.formatter.assert_line_data()
        else:
            HTMLParser.unknown_entityref(self, entname, terminator)


    dingbats = {}                       # (name, cog) ==> EPSImage
                                        #                 | (string, font)
                                        #                 | None

    fontdingbats = {'disc': ('\x6c', 'ZapfDingbats'),
                    'circle': ('\x6d', 'ZapfDingbats'),
                    'square': ('\x6f', 'ZapfDingbats'),
                    'sp': (' ', None),
                    'thinsp': ('\240', None),
                    'endash': ('-', None),
                    'ndash': ('-', None),
                    'emdash': ('--', None),
                    'mdash': ('--', None),
                    }

    def load_dingbat(self, entname):
        """Load the appropriate EPSImage object for an entity.
        """
        if self.settings.greyscale:
            img = self.load_dingbat_cog(entname, 'grey')
        else:
            img = self.load_dingbat_cog(entname, 'color')
            if not img:
                img = self.load_dingbat_cog(entname, 'grey')
        return img

    def load_dingbat_cog(self, entname, cog):
        """Load EPSImage object for an entity with a specified conversion.

        The conversion is not downgraded to grey if 'color' fails.  If the
        image is not available or convertible, returns None.
        """
        key = (entname, cog)
        if self.dingbats.has_key(key):
            return self.dingbats[key]
        gifname = entname + '.gif'
        epsname = os.path.join('eps.' + cog, entname + '.eps')
        self.dingbats[key] = None
        for p in self.context.app.iconpath:
            epsp = os.path.join(p, epsname)
            gifp = os.path.join(p, gifname)
            if os.path.exists(epsp):
                self.load_dingbat_eps(key, epsp)
            elif os.path.exists(gifp):
                try:
                    newepsp = epstools.convert_gif_to_eps(cog, gifp, epsp)
                except:
                    pass
                else:
                    self.load_dingbat_eps(key, newepsp)
                    if newepsp != epsp:
                        os.unlink(newepsp)
                break
        return self.dingbats[key]

    def load_dingbat_eps(self, key, epsfile):
        """Loads the EPSImage object and stores in the cache.
        """
        try:
            img = epstools.load_eps(epsfile)
        except epstools.EPSError:
            #  no bounding box
            self.dingbats[key] = None
        else:
            self.dingbats[key] = img

    def load_image(self, imageurl):
        """Load image and return EPS data and bounding box.

        If the conversion from raster data to EPS fails, then EPSError is
        raised.
        """
        try:
            image = self._image_loader(imageurl)
        except:
            raise epstools.EPSError('Image could not be loaded.')
        if not image:
            raise epstools.EPSError('Image could not be loaded.')
        import tempfile
        img_fn = tempfile.mktemp()
        fp = open(img_fn, 'wb')
        try:
            fp.write(image)
        except:
            raise epstools.EPSError('Failed to write image to external file.')
        fp.close()
        return epstools.load_image_file(img_fn, self.settings.greyscale)


# These functions and classes are "filters" which can be used as anchor
# transforms with the PrintingHTMLParser class.


def disallow_data_scheme(href, attrs):
    """Cancel data: URLs."""
    if urlparse.urlparse(href)[0] == 'data':
        href = None
    return href


def disallow_anchor_footnotes(href, attrs):
    """Cancel all anchor footnotes."""
    return None


class disallow_self_reference:
    """Cancel all anchor footnotes which refer to the current document."""
    def __init__(self, baseurl):
        self.__baseref = urlparse.urlparse(baseurl)[:-1] + ('',)

    def __call__(self, href, attrs):
        ref = urlparse.urlparse(href)[:-1] + ('',)
        if ref == self.__baseref:
            href = None
        return href
