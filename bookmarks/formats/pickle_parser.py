"""Parser for Grail's pickled bookmarks.  Old-style bookmarks are
automatically converted to the current type."""

__version__ = '$Revision: 1.3 $'

import bookmarks
import bookmarks.nodes
import bookmarks.walker
import re
import string

try:
    import cPickle
except ImportError:
    import pickle
else:
    pickle = cPickle


class Parser:
    __data = ''
    __old_root = None
    __root = None

    __header_rx = re.compile('#.*GRAIL-Bookmark-file-([234])')

    def __init__(self, filename):
        self._filename = filename

    def feed(self, data):
        self.__data = self.__data + data

    def close(self):
        data = self.__data
        # remove leading comment line
        header, data = self.__split_line(data)
        m = self.__header_rx.match(header)
        self.version = m.group(1)
        if self.version == "4":
            orig_fname, data = self.__split_line(data)
            orig_mtime, data = self.__split_line(data)
            self.original_filename = string.strip(orig_fname)
            self.original_mtime = int(string.strip(orig_mtime))
        self.__root = pickle.loads(data)
        if self.version != "4":
            # re-write as new version:
            self.__old_root = self.__root
            walker = CopyWalker(self.__root)
            walker.walk()
            self.__root = walker.get_copy()

    def get_root(self):
        """Return a version 4 root."""
        return self.__root

    def get_old_root(self):
        """Return an old version 2 or 3 root node, if available."""
        return self.__old_root

    def __split_line(self, data):
        if '\n' not in data:
            raise bookmarks.BookmarkFormatError(self._filename,
                                                "incomplete file header")
        pos = string.find(data, '\n') + 1
        header = data[:pos]
        data = data[pos:]
        return header, data



class CopyWalker(bookmarks.walker.TreeWalker):
    """Copy any bookmark tree to a new, version 4 tree."""

    __copy = None

    def __init__(self, root=None):
        bookmarks.walker.TreeWalker.__init__(self, root)
        self.__context = []

    def get_copy(self):
        return self.__copy

    def start_Folder(self, node):
        new = bookmarks.nodes.Folder()
        new.set_id(node.id())
        new.set_title(node.title())
        new.set_description(node.description())
        new.set_add_date(node.add_date())
        if self.__context:
            self.__context[-1].append_child(new)
        else:
            self.__copy = new
        self.__context.append(new)
    def end_Folder(self, node):
        del self.__context[-1]

    def start_Bookmark(self, node):
        new = bookmarks.nodes.Bookmark()
        new.set_uri(node.uri())
        new.set_id(node.id())
        new.set_title(node.title())
        new.set_description(node.description())
        new.set_add_date(node.add_date())
        self.__context[-1].append_child(new)

    def start_Separator(self, node):
        self.__context[-1].append_child(bookmarks.nodes.Separator())
