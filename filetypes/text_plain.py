"""Grail parser for text/plain."""
__version__ = '$Revision: 2.8 $'

import formatter
from utils import grailutil
import Reader



def parse_text_plain(*args, **kw):
    headers = args[0].context.get_headers()
    ctype = headers.get('content-type')
    if ctype:
        ctype, opts = grailutil.conv_mimetype(ctype)
        if opts.get('format'):
            how = str.lower(opts['format'])
            if how == "flowed":
                from filetypes import FlowingText
                return FlowingText.FlowingTextParser(args, kw)
    return Reader.TextParser(args, kw)
