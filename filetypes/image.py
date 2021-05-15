"""Handler for inline images expressed using <OBJECT>."""
__version__ = "$Revision: 1.6 $"

import AsyncImage
import HTMLParser
import string
import Tkinter

from grailutil import *

allowed_types = None


def init_types():
    """Load the image type information dictionary based on what form of image
    support we're using."""
    global allowed_types
    allowed_types = {}
    if AsyncImage.isPILAllowed():
        import Image
        for datatype in Image.MIME.values():
            type, subtype = string.splitfields(datatype, '/')
            if type == "image":
                allowed_types[datatype] = datatype
    else:
        # standard Tk is relatively limited:
        for datatype in ("image/gif",
                         "image/x-portable-graymap",
                         "image/x-portable-pixmap"):
            allowed_types[datatype] = datatype


def embed_image(parser, attrs):
    src = extract_keyword('data', attrs)
    if src:
        src = parser.context.get_baseurl(src)
    if not src:
        return None
    if not parser.context.app.prefs.GetBoolean('browser', 'load-images'):
        return None
    typeinfo = extract_keyword('type', attrs, conv=conv_mimetype)
    if typeinfo:
        datatype, typeopts = typeinfo
    else:
        datatype, typeopts = None, None
    if not datatype:
        datatype, typeopts = conv_mimetype(
            parser.context.app.guess_type(src)[0])

    # Make sure allowed_types has been initialized.
    if allowed_types is None:
        init_types()
    if not allowed_types.has_key(datatype):
        return None

    # Image type is supported; get parameters and load it.
    shapes = attrs.has_key('shapes')
    border = extract_keyword('border', attrs, shapes and 2 or 0,
                             conv=string.atoi)
    width = extract_keyword('width', attrs, 0, conv=string.atoi)
    height = extract_keyword('height', attrs, 0, conv=string.atoi)
    hspace = extract_keyword('hspace', attrs, 0, conv=string.atoi)
    vspace = extract_keyword('vspace', attrs, 0, conv=string.atoi)
    return ImageObject(parser, src, shapes=shapes, border=border, width=width,
                       height=height, hspace=hspace, vspace=vspace)


class ImageObject(HTMLParser.Embedding):
    __map = None

    def __init__(self, parser, src, shapes=0, border=0, width=0,
                 height=0, hspace=0, vspace=0):
        if shapes:
            self.__map, thunk = self.__make_map(parser.context)
        else:
            thunk = None
##      print "Creating ImageObject handler", self, "data=" + src
        parser.handle_image(src, '', thunk, 0,
                            Tkinter.BASELINE, width, height, border,
                            parser.reload1, hspace=hspace, vspace=vspace)

    def __make_map(self, context):
        global __map_count
        try:
            __map_count = __map_count + 1
        except NameError:
            __map_count = 0
        name = '<OBJECT-MAP-%d>' % __map_count
        import ImageMap
        map = ImageMap.MapInfo(name)
        context.image_maps[name] = map
        return map, ImageMap.MapThunk(context, name)

    def anchor(self, attrs):
        if not self.__map:
            return
        href = extract_keyword('href', attrs)
        if not href:
            return
        target = extract_keyword('target', attrs, "", conv=conv_normstring)
        shape = extract_keyword('shape', attrs, conv=conv_normstring)
        coords = extract_keyword('coords', attrs, conv=conv_normstring)
        if shape and (coords or shape == 'default'):
            self.__map.add_shape(shape, coords, href, target)
