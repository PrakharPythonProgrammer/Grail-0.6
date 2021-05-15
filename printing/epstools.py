"""Tools for using Encapsulated PostScript."""

__version__ = '$Revision: 1.5 $'

import os
import string
import sys

import utils


#  Exception which should not propogate outside printing support.
class EPSError:
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class EPSImage:
    __xscale = 1.0
    __yscale = 1.0

    def __init__(self, data, bbox):
        self.data = data
        self.bbox = bbox
        ll_x, ll_y, ur_x, ur_y = bbox
        self.__width = utils.distance(ll_x, ur_x)
        self.__height = utils.distance(ll_y, ur_y)

    def reset(self):
        self.__xscale = self.__yscale = 1.0

    def restrict(self, width=None, height=None):
        w, h = self.get_size()          # current size
        rf = 1.0                        # reduction factor
        if width and width < w:
            rf = width / w
        if height and height < h:
            rf = min(rf, height / h)
        self.__yscale = self.__yscale * rf
        self.__xscale = self.__xscale * rf

    def get_scale(self):
        return self.__xscale, self.__yscale

    def get_size(self):
        return (self.__width * self.__xscale), \
               (self.__height * self.__yscale)

    def set_size(self, width, height):
        self.__xscale = float(width) / self.__width
        self.__yscale = float(height) / self.__height

    def set_width(self, width):
        aspect = self.__yscale / self.__xscale
        self.__xscale = float(width) / self.__width
        self.__yscale = self.__xscale * aspect

    def set_height(self, height):
        aspect = self.__xscale / self.__yscale
        self.__yscale = float(height) / self.__height
        self.__xscale = self.__yscale * aspect


#  Dictionary of image converters from key ==> EPS.
#  The values need to be formatted against a dictionary that contains the
#  values `i' for the input filename and `o' for the output filename.
image_converters = {
    ('gif', 'color') : 'giftopnm %(i)s | pnmtops -noturn >%(o)s',
    ('gif', 'grey') : 'giftopnm %(i)s | ppmtopgm | pnmtops -noturn >%(o)s',
    ('jpeg', 'color') : 'djpeg -pnm %(i)s | pnmtops -noturn >%(o)s',
    ('jpeg', 'grey') : 'djpeg -grayscale -pnm %(i)s | pnmtops -noturn >%(o)s',
    ('pbm', 'grey') : 'pbmtoepsi %(i)s >%(o)s',
    ('pgm', 'grey') : 'pnmtops -noturn %(i)s >%(o)s',
    ('ppm', 'color') : 'pnmtops -noturn %(i)s >%(o)s',
    ('ppm', 'grey') : 'ppmtopgm %(i)s | pnmtops -noturn >%(o)s',
    ('rast', 'color') : 'rasttopnm %(i)s | pnmtops -noturn >%(o)s',
    ('rast', 'grey') : 'rasttopnm %(i)s | ppmtopgm | pnmtops -noturn >%(o)s',
    ('rgb', 'color') : 'rgb3toppm %(i)s | pnmtops -noturn >%(o)s',
    ('rgb', 'grey') : 'rgb3toppm %(i)s | ppmtopgm | pnmtops -noturn >%(o)s',
    ('tiff', 'color') : 'tifftopnm %(i)s | pnmtops -noturn >%(o)s',
    ('tiff', 'grey') : 'tifftopnm %(i)s | ppmtopgm | pnmtops -noturn >%(o)s',
    ('xbm', 'grey') : 'xbmtopbm %(i)s | pbmtoepsi >%(o)s',
    ('xpm', 'color') : 'xpmtoppm %(i)s | pnmtops -noturn >%(o)s',
    ('xpm', 'grey') : 'xpmtoppm %(i)s | ppmtopgm | pnmtops -noturn >%(o)s'
    }


def load_image_file(img_fn, greyscale):
    """Generate EPS and the bounding box for an image stored in a file.

    This function attempts to use the Python Imaging Library if it is
    installed, otherwise it uses a fallback approach using external
    conversion programs.
    """
    import tempfile
    eps_fn = tempfile.mktemp()
    try:
        load_image_pil(img_fn, greyscale, eps_fn)
    except (AttributeError, IOError, ImportError):
        # AttributeError is possible with partial installation of PIL,
        # and IOError can mean a recognition failure.
        load_image_internal(img_fn, greyscale, eps_fn)
    img = load_eps(eps_fn)              # img is (data, bbox)
    os.unlink(eps_fn)
    return img


def load_image_internal(img_fn, greyscale, eps_fn):
    """Use external converters to generate EPS."""
    from imghdr import what
    imgtype = what(img_fn)
    if not imgtype:
        os.unlink(img_fn)
        raise EPSError('Could not identify image type.')
    cnv_key = (imgtype, (greyscale and 'grey') or 'color')
    if not image_converters.has_key(cnv_key):
        cnv_key = (imgtype, 'grey')
    if not image_converters.has_key(cnv_key):
        os.unlink(img_fn)
        raise EPSError('No converter defined for %s images.' % imgtype)
    img_command = image_converters[cnv_key]
    img_command = img_command % {'i':img_fn, 'o':eps_fn}
    try:
        if os.system(img_command + ' 2>/dev/null'):
            os.unlink(img_fn)
            if os.path.exists(eps_fn):
                os.unlink(eps_fn)
            raise EPSError('Error converting image to EPS.')
    except:
        if os.path.exists(img_fn):
            os.unlink(img_fn)
        if os.path.exists(eps_fn):
            os.unlink(eps_fn)
        raise EPSError('Could not run conversion process.')
    if os.path.exists(img_fn):
        os.unlink(img_fn)


def load_image_pil(img_fn, greyscale, eps_fn):
    """Use PIL to generate EPS."""
    import Image, _imaging              # _imaging to make sure we have a
    import traceback                    # full PIL installation.
    try:
        im = Image.open(img_fn)
        format = im.format
        if greyscale and im.mode not in ("1", "L"):
            im = im.convert("L")
        if not greyscale and im.mode == "P":
            im = im.convert("RGB")
        im.save(eps_fn, "EPS")
    except:
        e, v, tb = sys.exc_type, sys.exc_value, sys.exc_traceback
        stdout = sys.stdout
        try:
            sys.stdout = sys.stderr
            traceback.print_exc()
            print "Exception printed from printing.epstools.load_image_pil()"
        finally:
            sys.stdout = stdout
        raise e, v, tb


def load_eps(eps_fn):
    """Load an EPS image.

    The bounding box is extracted and stored together with the data in an
    EPSImage object.  If a PostScript `showpage' command is obvious in the
    file, it is removed.
    """
    fp = open(eps_fn)
    lines = fp.readlines()
    fp.close()
    try: lines.remove('showpage\n')
    except: pass                        # o.k. if not found
    bbox = load_bounding_box(lines)
    return EPSImage(string.joinfields(lines, ''), bbox)


def load_bounding_box(lines):
    """Determine bounding box for EPS image given as sequence of text lines.
    """
    from string import lower
    bbox = None
    for line in lines:
        if len(line) > 21 and lower(line[:15]) == '%%boundingbox: ':
            bbox = tuple(map(string.atoi, string.split(line[15:])))
            break
    if not bbox:
        raise EPSError('Bounding box not specified.')
    return bbox


def convert_gif_to_eps(cog, giffile, epsfile):
    """Convert GIF to EPS using specified conversion.

    The EPS image is stored in `epsfile' if possible, otherwise a temporary
    file is created.  The name of the file created is returned.
    """
    if not image_converters.has_key(('gif', cog)):
        raise EPSError("No conversion defined for %s GIFs." % cog)
    try:
        fp = open(epsfile, 'w')
    except IOError:
        import tempfile
        filename = tempfile.mktemp()
    else:
        filename = epsfile
        fp.close()
    img_command = image_converters[('gif', cog)]
    img_command = img_command % {'i':giffile, 'o':filename}
    try:
        if os.system(img_command + ' 2>/dev/null'):
            if os.path.exists(filename):
                os.unlink(filename)
            raise EPSError('Error converting image to EPS.')
    except:
        if os.path.exists(filename):
            os.unlink(filename)
        raise EPSError('Could not run conversion process: %s.'
                       % sys.exc_type)
    return filename
