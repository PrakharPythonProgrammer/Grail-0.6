"""Access to font metrics and PostScript name mappings.

All access is through the PSFont class.
"""
__version__ = '$Revision: 1.4 $'

import fonts                            # package
import utils


# This dictionary maps PostScript font names to the normal, bold and
# italic suffixes for the font.  Key is the short name describing the
# font, value is a tuple indicating the real name of the font (for
# mapping fonts to other fonts), then the regular, bold, and italic
# suffix modifiers of the font.  Note that if their is no regular name
# modifier, then use the empty string, but if there is a regular name
# modifier, make sure it includes a leading dash.  Other modifiers
# should not include the dash.

fontdefs = {
    'Times':            (None, '-Roman', 'Bold', 'Italic'),
    'Helvetica':        (None, '',       'Bold', 'Oblique'),
    'NewCenturySchlbk': (None, '-Roman', 'Bold', 'Italic'),
    'Courier':          (None, '',       'Bold', 'Oblique'),
    # The code from HTML-PSformat.c says:
    # "This is a nasty trick, I have put Times in place of Lucida,
    # because most printers don't have Lucida font"
    # Hmm...  -BAW
    #'Lucida':           ('Times', None, 'Bold', 'Italic'),
    'Lucida':           (None, '', 'Bold', 'Italic'),
    #
    'Palatino':         (None, '-Roman', 'Bold', 'Italic'),
    }

# Mappings between HTML header tags and font sizes
# Entries in the dictionary are factors used with DEFAULT_FONT_SIZE
# The values used by Mosaic
#DEFAULT_FONT_SIZE = 12.0
#font_sizes = {
#    None: 1.0,
#    'h1': 3.0,
#    'h2': 2.0,
#    'h3': 1.5,
#    'h4': 1.67,
#    'h5': 1.0,
#    'h6': 0.83
#    }

# The values used by Grail
DEFAULT_FONT_SIZE = 10.0
font_sizes = {
    None: 1.0,
    'h1': 1.8,
    'h2': 1.4,
    'h3': 1.2,
    'h4': 1.0,
    'h5': 1.0,
    'h6': 1.0
    }


class PSFont:
    """This class manages font changes and calculation of associated
    metrics for PostScript output.  It basically defines a mapping
    between a PostScript definition for a font and a short name used
    by PostScript functions defined in header.ps.

    When the font is created, it is passed the name of a variable
    width family and a fixed width family.  Those are the only
    configuration options you have.  Should probably allow a scaling
    factor to be passed in, mapping GUI dpi to PostScript dpi, but
    that would have to be calculated by Grail for the underlying GUI.

    Exported methods:

       __init__(optional: VARIFAMILY, FIXEDFAMILY)
       set_font((SIZE, ITALIC?, BOLD?, TT?)) ==> (PSFONTNAME, SIZE)
       text_width(TEXT) ==> WIDTH_IN_POINTS
       font_size(optional: (SIZE, ITALIC?, BOLD?, TT?)) ==> SZ_IN_POINTS
    """
    def __init__(self, varifamily='Times', fixedfamily='Courier',
                 size=DEFAULT_FONT_SIZE):
        """Create a font definition using VARIFAMILY as the variable
        width font and FIXEDFAMILY as the fixed width font.  Defaults
        to Helvetica and Courier respectively.
        """
        # current font is a tuple of size, family, italic, bold
        self.vfamily = varifamily
        self.ffamily = fixedfamily
        self.font = (size, 'FONTV', '', '')
        self.base_size = self._fontsize = size

        # TBD: this number is slightly bogus, but the rational is
        # thus.  The original code was tied fairly closely with X so
        # it had to map screen resolutions to PostScript.  I don't
        # want this version to be tied to X at all, if possible, so I
        # ignore all screen resolution parameters.  The tradeoff is
        # that the hardcopy will probably not be formatted exactly as
        # it appears on the screen, but I believe that is appropriate.
        # Should we decide to change that, this scaling factor may
        # come into play, but should probably be passed in from Grail,
        # since only it can interface to the underlying window system.
        self.points_per_pixel = 72.0 / 72.0

        # calculate document fonts
        if not fontdefs.has_key(self.vfamily): self.vfamily = 'Helvetica'
        if not fontdefs.has_key(self.ffamily): self.ffamily = 'Courier'
        vrealname, vreg, vbold, vitalic = fontdefs[self.vfamily]
        frealname, freg, fbold, fitalic = fontdefs[self.ffamily]
        # fonts may be mapped to other fonts
        if not vrealname: vrealname = self.vfamily
        if not frealname: frealname = self.ffamily

        # calculate font names in PostScript space. Eight fonts are
        # used, naming scheme is as follows.  All PostScript font
        # name definitions start with `FONT', followed by `V' for the
        # variable width font and `F' for the fixed width font.  `B'
        # for the bold version, `I' for italics, and for the
        # bold-italic version, `B' *must* preceed `I'.  See header.ps
        # for more info.
        self.docfonts = {
            'FONTV':   '%s%s' % (vrealname, vreg),
            'FONTVB':  '%s-%s' % (vrealname, vbold),
            'FONTVI':  '%s-%s' % (vrealname, vitalic),
            'FONTVBI': '%s-%s%s' % (vrealname, vbold, vitalic),
            'FONTF':   '%s%s' % (frealname, freg),
            'FONTFB':  '%s-%s' % (frealname, fbold),
            'FONTFI':  '%s-%s' % (frealname, fitalic),
            'FONTFBI': '%s-%s%s' % (frealname, fbold, fitalic)
            }
        # instantiated font objects
        self.fontobjs = {}
        self.tw_func = None

    def get_font(self):
        """Returns the font nickname and size.

        This is the only place the nickname is computed.
        """
        sz, family, italic, bold = self.font
        nick = "%s%s%s" % (family, bold, italic)
##      utils.debug("get_font(): %s ==> %s\n" % (self.font, (nick, sz)))
        return nick, sz

    def set_font(self, font_tuple):
        """Set the current font to that specified by FONT_TUPLE, which
        is of the form (SIZE, ITALIC?, BOLD?, TT?).  Returns the
        PostScript layer name of the font, and the font size in
        points.  """
        # we *said* we wanted a tuple
        if font_tuple is None: font_tuple = (None, None, None, None)
##      utils.debug("set_font(%s)\n" % (font_tuple,))
        set_sz, set_italic, set_bold, set_tt = font_tuple
        # get the current font and break up the tuple
        cur_sz, cur_family, cur_italic, cur_bold = self.font
        # calculate size
        new_sz = self.font_size(font_tuple)
        # calculate variable vs. fixed base name
        if set_tt: new_family = 'FONTF'
        else: new_family = 'FONTV'

        # add modifiers.  Because of the way fonts are named, always
        # add bold modifier before italics modifier, in case both are
        # present
        if set_bold: new_bold = 'B'
        else: new_bold = ''

        if set_italic: new_italic = 'I'
        else: new_italic = ''

        # save the current font specification
        self.font = (new_sz, new_family, new_italic, new_bold)

        # get the font nickname
        fontnickname, new_sz = self.get_font()

        # make sure the font object is instantiated
        if not self.fontobjs.has_key(fontnickname):
            psfontname = self.docfonts[fontnickname]
            self.fontobjs[fontnickname] = fonts.font_from_name(psfontname)
##      print fontnickname, "==>", self.fontobjs[fontnickname]
        self.tw_func = self.fontobjs[fontnickname].text_width

        self._fontsize = new_sz

        # return the PostScript font definition and the size in points
        return (fontnickname, new_sz)

    def text_width(self, text):
##      width = self.tw_func(self._fontsize, text)
##      utils.debug("%s @ %spt ==> %s" % (`text`, self._fontsize, width),
##                  'charsizing')
##      return width
        return self.tw_func(self._fontsize, text)

    def font_size(self, font_tuple=None):
        """Return the size of the current font, or the font defined by
        optional FONT_TUPLE if present."""
        if not font_tuple:
            return self._fontsize
        tuple_sz = font_tuple[0]
        if type(tuple_sz) is type(1.0):
            return tuple_sz
        try:
            return font_sizes[tuple_sz] * self.base_size
        except KeyError:
            return self.base_size
