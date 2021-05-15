"""Base class for the Grail Application object.

This provides the preferences initialization if needed as well as the
extension loading mechanisms.  The later are the primary motivation
for this, allowing the html2ps.py script to use extensions intelligently
using the same approaches (and implementation) as the Tk-based browser.
"""
__version__ = '$Revision: 2.17 $'
#  $Source: /projects/cvsroot/grail/dist/src/BaseApplication.py,v $

import keyword
import os
import string

import grailbase.app
import grailbase.mtloader
import grailbase.utils

import sgml.extloader

# make extension packages from these:
import filetypes
import html
import printing.filetypes
import printing.htmltags
import protocols
import protocols.ProtocolAPI


class BaseApplication(grailbase.app.Application):
    def __init__(self, prefs=None):
        grailbase.app.Application.__init__(self, prefs)
        loader = sgml.extloader.TagExtensionLoader(html)
        self.add_loader("html.viewer", loader)
        loader = sgml.extloader.TagExtensionLoader(printing.htmltags)
        self.add_loader("html.postscript", loader)
        loader = grailbase.mtloader.MIMEExtensionLoader(filetypes)
        self.add_loader("filetypes", loader)
        loader = grailbase.mtloader.MIMEExtensionLoader(printing.filetypes)
        self.add_loader("printing.filetypes", loader)
        loader = protocols.ProtocolAPI.ProtocolLoader(protocols)
        self.add_loader("protocols", loader)

        # cache of available extensions
        self.__extensions = {}

    def find_type_extension(self, package, mimetype):
        handler = None
        try:
            loader = self.get_loader(package)
        except KeyError:
            pass
        else:
            try:
                content_type, opts = grailbase.utils.conv_mimetype(mimetype)
            except:
                pass
            else:
                handler = loader.get(content_type)
        return handler

    def find_extension(self, subdir, module):
        try:
            return self.get_loader(subdir).get(module)
        except KeyError:
            return None
