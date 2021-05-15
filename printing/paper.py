"""Paper information & support for printing."""

__version__ = '$Revision: 1.4 $'

from utils import inch_to_pt


class PaperInfo:
    inch = inch_to_pt(1.0)
    TopMargin = inch
    BottomMargin = inch
    LeftMargin = inch
    RightMargin = inch
    TabStop = inch_to_pt(0.5)

    def __init__(self, size, rotation=None, margins=None):
        if type(size) is type(''):
            size = paper_sizes[size]
        paperwidth, paperheight, name = size
        self.PaperHeight = paperheight  # cannonical
        self.PaperWidth = paperwidth    # cannonical
        self.PaperName = name
        self.Rotation = 0.0
        if rotation:
            self.rotate(rotation)
        if margins:
            self.set_margins(margins)

    def rotate(self, angle):
        if type(angle) is type(''):
            angle = paper_rotations[angle]
        if angle % 90.0 != 0:
            raise ValueError, "Illegal page rotation: "  + `angle`
        self.Rotation = angle = angle % 360.0
        if angle % 180.0:
            pw, ph = self.PaperWidth, self.PaperHeight
            self.PaperWidth, self.PaperHeight = ph, pw
        self.__update()

    def set_margins(self, (top, bottom, left, right)):
        self.TopMargin = float(top)
        self.BottomMargin = float(bottom)
        self.LeftMargin = float(left)
        self.RightMargin = float(right)
        self.__update()

    def __update(self):
        # cannonical information has changed;
        # re-compute secondary attributes
        self.ImageWidth = self.PaperWidth \
                          - (self.LeftMargin + self.RightMargin)
        self.ImageHeight = self.PaperHeight \
                           - (self.TopMargin + self.BottomMargin)
        # these are relative to the upper edge of the document image area.
        self.HeaderPos = self.TopMargin / 2.0
        self.FooterPos = -(self.ImageHeight
                           + self.BottomMargin / 2.0)

    def dump(self):
        print "Paper information:"
        print "------------------"
        print "PaperName    =", self.PaperName
        print "Rotation     =", self.Rotation
        print "PaperHeight  =", self.PaperHeight
        print "PaperWidth   =", self.PaperWidth
        print "ImageHeight  =", self.ImageHeight
        print "ImageWidth   =", self.ImageWidth
        print "TopMargin    =", self.TopMargin
        print "BottomMargin =", self.BottomMargin
        print "LeftMargin   =", self.LeftMargin
        print "RightMargin  =", self.RightMargin
        print "HeaderPos    =", self.HeaderPos
        print "FooterPos    =", self.FooterPos
        print "TabStop      =", self.TabStop


paper_sizes = {
    "letter": (inch_to_pt(8.5), inch_to_pt(11.0)),
    "legal": (inch_to_pt(8.5), inch_to_pt(14.0)),
    "executive": (inch_to_pt(7.5), inch_to_pt(10.0)),
    "tabloid": (inch_to_pt(11.0), inch_to_pt(17.0)),
    "ledger": (inch_to_pt(17.0), inch_to_pt(11.0)),
    "statement": (inch_to_pt(5.5), inch_to_pt(8.5)),
    "a3": (842.0, 1190.0),
    "a4": (595.0, 842.0),
    "a5": (420.0, 595.0),
    "b4": (729.0, 1032.0),
    "b5": (516.0, 729.0),
    "folio": (inch_to_pt(8.5), inch_to_pt(13.0)),
    "quarto": (610.0, 780.0),
    "10x14": (inch_to_pt(10.0), inch_to_pt(14.0)),
    }

for size, (pw, ph) in paper_sizes.items():
    paper_sizes[size] = (pw, ph, size)


paper_rotations = {
    "portrait": 0.0,
    "landscape": 90.0,
    "seascape": -90.0,
    "upside-down": 180.0,
    }
