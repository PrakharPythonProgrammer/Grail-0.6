"""Storage handlers for bookmarks in a variety of formats.

Each module in this package contains a parser or writer for some
concrete storage format.  The module names obey the convention:
<format>_<operator>, where <format> is the `short name' of the format
as returned by bookmark.get_short_name(<long_format>), and <operator>
is either `parser' or `writer'.  Each module must define a single
callable object of the same name as <operator>, but with the first
letter capitalized.

The `Parser' callables must accept a single argument, the filename of
the storage object.  The filename should be used to create error
messages for exceptions as appropriate.  The objects returned by the
callable must be parser objects which offer the methods get_root(),
feed(), and close().  feed() is used to provide data to the parser; it
may be called more than once.  After all data has been provided via
feed(), close() will be called to inform the object that there is no
more data available; any additional parsing or structure-building must
be completed.  The get_root() method should return the root of the
resulting bookmarks tree, which should always be a
bookmarks.node.Folder instance.

The `Writer' callables receive no arguments, but must return an object
which supports a method write_tree().  This method must accept two
arguments: a bookmarks.nodes.Folder instance which is the root of the
bookmarks tree, and a file object to which output should be directed.
This method should output a complete storage object which can later be
parsed by using the parser object defined in the sister module for the
same format.

An additional module, html_scraper, provides a Parser callable that
builds a boookmarks structure from a general HTML file.

"""

__version__ = '$Revision: 1.3 $'
