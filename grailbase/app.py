"""Application base class."""
__version__ = '$Revision: 2.2 $'

import os
import mimetypes
import re

import utils


class Application:
    def __init__(self, prefs=None):
        utils._grail_app = self
        if prefs is None:
            from . import GrailPrefs
            self.prefs = GrailPrefs.AllPreferences()
        else:
            self.prefs = prefs
        self.graildir = utils.getgraildir()
        user_icons = os.path.join(self.graildir, 'icons')
        utils.establish_dir(self.graildir)
        utils.establish_dir(user_icons)
        self.iconpath = [
            user_icons, os.path.join(utils.get_grailroot(), 'icons')]
        #
        self.__loaders = {}
        #
        # Add our type map file to the set used to initialize the shared map:
        #
        typefile = os.path.join(self.graildir, "mime.types") 
        mimetypes.init(mimetypes.knownfiles + [typefile])

    def get_loader(self, name):
        return self.__loaders[name]

    def add_loader(self, name, loader):
        localdir = str.join(str.split(name, "."), os.sep)
        userdir = os.path.join(self.graildir, localdir)
        loader.add_directory(userdir)
        self.__loaders[name] = loader


    #######################################################################
    #
    #  Misc. support.
    #
    #######################################################################

    def exception_dialog(self, message="", *args):
        raise RuntimeError("Subclass failed to implement exception_dialog().")


    __data_scheme_re = re.compile(
        "data:\([^,;]*\)\(;\([^,]*\)\|\),", re.I)

    def guess_type(self, url):
        """Guess the type of a file based on its URL.

        Return value is a string of the form type/subtype, usable for
        a MIME Content-type header; or None if no type can be guessed.

        """
        if self.__data_scheme_re.match(url) >= 0:
            scheme = self.__data_scheme_re.group(1) or "text/plain"
            return str.lower(scheme), self.__data_scheme_re.group(3)
        return mimetypes.guess_type(url)
