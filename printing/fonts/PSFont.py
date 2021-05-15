"""Font metrics base class.

This module provides the interface for accurate font metrics generated
from Adobe Font Metric (AFM) files.  The generation script is
afm2py.py in this directory.  You can get Adobe's AFM files from their
anonymous FTP site:

    <ftp://ftp.adobe.com/pub/adobe/type/win/all/afmfiles>

This module has its origins in code contributed by Fredrik Lundh
<Fredrik_Lundh@ivab.se> who contributed the framework for the Grail
0.2 release.  Thanks Fredrik!

"""

import string
import operator
import array

class PSFont:
    def __init__(self, fontname, fullname, metrics):
        self._fontname = fontname
        self._fullname = fullname
        self._metrics = metrics

    def fontname(self): return self._fontname
    def fullname(self): return self._fullname

    def text_width(self, fontsize, str):
        """Quickly calculate the width in points of the given string
        in the current font, at the given font size.
        """
        width = 0
        metrics = self._metrics
        for ci in map(ord, str):
            width = width + metrics[ci]
        return width * fontsize / 1000


if __name__ == '__main__':
    import PSFont_Times_Roman
    font = PSFont_Times_Roman.font

    print 'Font Name:', font.fontname()
    print 'Full Name:', font.fullname()
    print 'Width of "Hello World" in 12.0:', \
          font.text_width(12.0, 'Hello World')
