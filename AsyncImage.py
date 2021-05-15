from FileReader import TempFileReader
from Tkinter import *
import grailutil
import os
import string

TkPhotoImage = PhotoImage


class ImageTempFileReader(TempFileReader):

    def __init__(self, context, api, image):
        self.image = image
        self.url = self.image.url
        TempFileReader.__init__(self, context, api)

    def handle_meta(self, errcode, errmsg, headers):
        TempFileReader.handle_meta(self, errcode, errmsg, headers)
        if errcode == 200:
            try:
                ctype = headers['content-type']
            except KeyError:
                return # Hope for the best
            if self.image_filters.has_key(ctype) and not isPILAllowed():
                self.set_pipeline(self.image_filters[ctype])

    # List of image type filters
    image_filters = {
        'image/gif': '',
        'image/jpeg': 'djpeg -gif',
        'image/x-xbitmap':
            'xbmtopbm | ppmtogif -transparent "#FFFFFF" 2>/dev/null',
        'image/tiff':
            """(T=${TMPDIR-/usr/tmp}/@$$.tiff; cat >$T;
                tifftopnm $T 2>/dev/null; rm -f $T)""",
        'image/png':
            # This requires pngtopnm which isn't standard netpbm yet
            'pngtopnm | ppmtogif -transparent "#FFFFFF" 2>/dev/null',
        }

    def handle_done(self):
        self.image.set_file(self.getfilename())
        self.cleanup()

    def handle_error(self, errcode, errmsg, headers):
        if errcode == 401:
            if headers.has_key('www-authenticate'):
                cred_headers = {}
                for k in headers.keys():
                    cred_headers[string.lower(k)] = headers[k]
                cred_headers['request-uri'] = self.image.url
                self.stop()
                credentials = self.image.context.app.auth.request_credentials(
                    cred_headers)
                if credentials.has_key('Authorization'):
                    for k,v in credentials.items():
                        self.image.headers[k] = v
                    # self.image.restart(self.image.url)
                    self.image.start_loading(self.image.context)
        self.image.set_error(errcode, errmsg, headers)
        self.cleanup()

    def stop(self):
        TempFileReader.stop(self)
        if self.image:
            self.image.reader = None

    def cleanup(self):
        self.image = None
        import os
        try:
            os.unlink(self.getfilename())
        except os.error:
            pass




class BaseAsyncImage:

    def setup(self, context, url, reload):
        self.context = context
        self.url = url
        self.reader = None
        self.loaded = 0
        self.headers = {}
        if reload:
            self.reload = 1
        else:
            self.reload = 0

    def load_synchronously(self, context=None):
        if not self.loaded:
            self.start_loading(context)
            if self.reader:
                self.reader.geteverything()
        return self.loaded

    def start_loading(self, context=None, reload=0):
        # seems that the reload=1 when you click on an image that
        # you had stopped loading
        if context: self.context = context
        if self.reader:
            return
        try:
            api = self.context.app.open_url(self.url, 'GET', self.headers,
                                            self.reload or reload) 
        except IOError, msg:
            self.show_bad()
            return
        cached_file, content_type = api.tk_img_access()
        if cached_file \
           and ImageTempFileReader.image_filters.has_key(content_type) \
           and ImageTempFileReader.image_filters[content_type] == '':
            api.close()
            self.set_file(cached_file)
        else:
            self.show_busy()
            # even if the item is in the cache, use the ImageTempFile
            # to handle the proper type coercion
            self.reader = ImageTempFileReader(self.context, api, self)

    def stop_loading(self):
        if not self.reader:
            return
        self.reader.kill()
        self.show_bad()

    def set_file(self, filename):
        self.blank()
        self.do_color_magic()
        try:
            self['file'] = filename
        except TclError:
            self.show_bad()
        else:
            self.loaded = 1

    def do_color_magic(self):
        self.context.root.tk.setvar("TRANSPARENT_GIF_COLOR",
                                    self.context.viewer.text["background"])

    def set_error(self, errcode, errmsg, headers):
        self.loaded = 0
        if errcode in (301, 302) and headers.has_key('location'):
            self.url = headers['location']
            self.start_loading()

    def is_reloading(self):
        return self.reload and not self.loaded

    def get_load_status(self):
        if self.reader:
            return 'loading'
        else:
            return 'idle'

    def show_bad(self):
        self.blank()
        try:
            self['file'] = grailutil.which(
                os.path.join("icons", "sadsmiley.gif")) or ""
        except TclError:
            pass

    def show_busy(self):
        self.blank()
        try:
            self['file'] = grailutil.which(
                os.path.join("icons", "image.gif")) or ""
        except TclError:
            pass


class TkAsyncImage(BaseAsyncImage, TkPhotoImage):

    def __init__(self, context, url, reload=0, **kw):
        apply(TkPhotoImage.__init__, (self,), kw)
        self.setup(context, url, reload)

    def get_cache_key(self):
        return self.url, 0, 0


class PILAsyncImageSupport(BaseAsyncImage):
    #
    # We can't actually inherit from the PIL PhotoImage, so we'll be a mixin
    # that really takes over.  A new class will be created from this & the
    # PIL PhotoImage which forms the actual implementation class iff PIL is
    # both available and enabled.
    #
    __width = 0
    __height = 0

    def __init__(self, context, url, reload=0, width=None, height=None, **kw):
        import ImageTk
        self.setup(context, url, reload)
        master = kw.get("master")
        if master is None:
            ImageTk.PhotoImage.__init__(self, "RGB", (width or 1, height or 1))
        else:
            ImageTk.PhotoImage.__init__(self, "RGB", (width or 1, height or 1),
                                        master=kw.get("master"))
        if not hasattr(self, 'image'):
            # Steal a private variable from ImageTk
            self.image = self._PhotoImage__photo
        # Make sure these are integers
        self.__width = width or 0
        self.__height = height or 0

    def blank(self):
        self.image.blank()

    def get_cache_key(self):
        #
        # Note that two different cache keys may be generated for an image
        # depending on how they are specified.  In particular, the keys
        # (URL, 0, 0) and (URL, WIDTH, HEIGHT) may be generated for the same
        # real image (not Image object) if WIDTH and HEIGHT are the default
        # dimensions of the image and the image is specified both with and
        # without size hints.  This still generates no more than two distinct
        # keys for otherwise identical image objects.
        #
        return self.url, self.__width, self.__height

    def set_file(self, filename):
        import Image
        try:
            im = Image.open(filename)
            im.load()                   # force loading to catch IOError
        except (IOError, ValueError):
            # either of these may occur during decoding...
            return self.show_bad()
        if im.format == "XBM":
            im = xbm_to_rgba(im)
        real_size = im.size
        # determine desired size:
        if self.__width and not self.__height and self.__width != im.size[0]:
            # scale horizontally
            self.__height = int(1.0 * im.size[1] * self.__width / im.size[0])
        elif self.__height and not self.__width \
             and self.__height != im.size[1]:
            # scale vertically
            self.__width = int(1.0 * im.size[0] * self.__height / im.size[1])
        else:
            self.__width = self.__width or im.size[0]
            self.__height = self.__height or im.size[1]
        # transparency stuff
        if im.mode == "RGBA" \
           or (im.mode == "P" and im.info.has_key("transparency")):
            r, g, b = self.context.viewer.text.winfo_rgb(
                self.context.viewer.text["background"])
            r = r / 256                 # convert these to 8-bit versions
            g = g / 256
            b = b / 256
            if im.mode == "P":
                im = p_to_rgb(im, (r, g, b))
            else:
                im = rgba_to_rgb(im, (r, g, b))
        #
        if real_size != (self.__width, self.__height):
            w, h = real_size
            if w != self.__width or h != self.__height:
                im = im.resize((self.__width, self.__height))
        # This appears to be absolutely necessary, but I'm not sure why....
        self._PhotoImage__size = im.size
        self.blank()
        self.paste(im)
        w, h = im.size
        self.image['width'] = w
        self.image['height'] = h

    def width(self):
        return self.__width

    def height(self):
        return self.__height

    def __setitem__(self, key, value):
        if key == "file":
            self.do_color_magic()
        self.image[key] = value


def p_to_rgb(im, rgb):
    """Translate a P-mode image with transparency to an RGB image. 

    im
        The transparent image.

    rgb
        The RGB-value to use for the transparent areas.  This should be
        a 3-tuple of integers, 8 bits for each band.
    """
    import Image
    new_im = Image.new("RGB", im.size, rgb)
    point_mask = [0xff] * 256
    point_mask[im.info['transparency']] = 0
    new_im.paste(im, None, im.point(point_mask, '1'))
    return new_im


def rgba_to_rgb(im, rgb):
    """Translate an RGBA-mode image to an RGB image. 

    im
        The transparent image.

    rgb
        The RGB-value to use for the transparent areas.  This should be
        a 3-tuple of integers, 8 bits for each band.
    """
    import Image
    new_im = Image.new("RGB", im.size, rgb)
    new_im.paste(im, None, im)
    return new_im


def xbm_to_rgba(im):
    """Translate a XBM image to an RGBA image. 

    im
        The XBM image.
    """
    import Image
    # invert & mask so we get transparency
    mapping = [255] * 256
    mapping[255] = 0
    mask = im.point(mapping)
    return Image.merge("RGBA", (mask, mask, mask, im))


def pil_installed():
    # Determine if the Python Imaging Library is available.
    #
    # Note that "import Image" is not sufficient to test the availability of
    # the image loading capability.  Image can be imported without _imaging
    # and still supports identification of file types.  Grail requires _imaging
    # to support image loading.
    #
    try:
        import _imaging
        import Image
        import ImageTk
    except ImportError:
        return 0
    # Now check the integration with Tk:
    try:
        ImageTk.PhotoImage(Image.new("L", (1, 1)))
    except TclError:
        return 0
    return 1


_pil_allowed = None

def isPILAllowed():
    """Return true iff PIL should be used by the caller."""
    global _pil_allowed
    if _pil_allowed is None:
        app = grailutil.get_grailapp()
        _pil_allowed = (app.prefs.GetBoolean("browser", "enable-pil")
                        and pil_installed())
    return _pil_allowed


def AsyncImage(context, url, reload=0, **kw):
    # Check the enable-pil preference and replace this function
    # with the appropriate implementation in the module namespace:
    #
    global AsyncImage
    if isPILAllowed():
        import ImageTk
        class PILAsyncImage(PILAsyncImageSupport, ImageTk.PhotoImage):
            pass
        AsyncImage = PILAsyncImage
    else:
        AsyncImage = TkAsyncImage
    return apply(AsyncImage, (context, url, reload), kw)
