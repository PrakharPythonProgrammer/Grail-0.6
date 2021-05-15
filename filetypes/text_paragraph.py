"""Parser component for text/paragraph documents.

Text/paragraph is for word-wrapped text where each paragraph is a single
'line' in the byte-stream, with EOL being used as a paragraph breaker.

Text/paragraph is described in an Internet Draft; the revision which this
is based on is available at:

    ftp://ftp.ietf.org/internet-drafts/draft-newman-mime-textpara-00.txt

(until it is superseded or otherwise expired).  Note that the
text/paragraph MIME type is only a WORK IN PROGRESS and carries no weight
as an Internet RFC.
"""
__version__ = '$Revision: 2.4 $'

import formatter
import re


class parse_text_paragraph:
    def __init__(self, viewer, reload=0):
        self.__fmt = formatter.AbstractFormatter(viewer)

    __eol_re = re.compile("[\r\n]+")

    def feed(self, data):
        while data:
            m = self.__eol_re.search(data)
            if m:
                self.__fmt.add_flowing_data(data[:m.start()])
                self.__fmt.end_paragraph(1)
                data = data[m.end():]
            else:
                self.__fmt.add_flowing_data(data)
                data = ''

    def close(self):
        self.__fmt = None
