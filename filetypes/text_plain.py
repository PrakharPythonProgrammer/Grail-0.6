"""Grail parser for text/plain."""
__version__ = '$Revision: 2.8 $'

import formatter
import grailutil
import Reader
import string


def parse_text_plain(*args, **kw):
    headers = args[0].context.get_headers()
    ctype = headers.get('content-type')
    if ctype:
        ctype, opts = grailutil.conv_mimetype(ctype)
        if opts.get('format'):
            how = string.lower(opts['format'])
            if how == "flowed":
                import FlowingText
                return apply(FlowingText.FlowingTextParser, args, kw)
    return apply(Reader.TextParser, args, kw)
