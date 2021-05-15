"""TreeWalker subclass that prepares a bookmark tree for export.  This removes
what might be considered private information, such as when nodes were added
or visited."""

__version__ = '$Revision: 1.3 $'


import walker

class ExportWalker(walker.TreeWalker):
    def __init__(self, root, options=None):
        if options is None:
            options = ExportOptions()
        self.__options = options
        walker.TreeWalker.__init__(self, root)

    def get_options(self):
        return self.__options

    def set_options(self, options):
        self.__options = options

    def start_Folder(self, node):
        if self.__options.remove_add_date:
            node.set_add_date(None)

    def start_Bookmark(self, node):
        if self.__options.remove_add_date:
            node.set_add_date(None)
        if self.__options.remove_last_visited:
            node.set_last_visited(None)
        if self.__options.remove_last_modified:
            node.set_last_modified(None)


class ExportOptions:
    remove_add_date = 1
    remove_last_visited = 1
    remove_last_modified = 1

    def __init__(self):
        pass
