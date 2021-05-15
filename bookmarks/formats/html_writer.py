"""Writer for Netscape HTML bookmarks."""

__version__ = '$Revision: 1.4 $'


import bookmarks                        # parent
import bookmarks.walker
import string
import sys


class Writer(bookmarks.walker.TreeWalker):
    __depth = 1
    __need_header = 1
    __alias_id = ''
    __id_next = 0

    # public interface

    def get_filetype(self):
        return "html"

    def write_tree(self, fp):
        self.__id_map = {}
        stdout = sys.stdout
        root = self.get_root()
        try:
            sys.stdout = fp
            self.walk()
            print '</DL><p>'
        finally:
            sys.stdout = stdout
            fp.close()

    # node-type handlers

    def start_Separator(self, node):
        print '%s<HR>' % self.__tab()

    def start_Bookmark(self, node):
        alias = self.__compute_alias_info(node)
        modified = node.last_modified() or ''
        if modified:
            modified = ' LAST_MODIFIED="%d"' % modified
        add_date = node.add_date() or ''
        if add_date:
            add_date = ' ADD_DATE="%d"' % add_date
        last_visit = node.last_visited()
        if last_visit:
            last_visit = ' LAST_VISIT="%d"' % last_visit
        print '%s<DT><A HREF="%s"%s%s%s%s>%s</A>' % \
              (self.__tab(), node.uri(), alias, add_date,
               last_visit, modified, bookmarks._prepstring(node.title()))
        self.__write_description(node.description())

    def start_Alias(self, node):
        refnode = node.get_refnode()
        if refnode is None or refnode.get_nodetype() == "Folder":
            return
        idref = node.idref()
        if not self.__id_map.has_key(idref):
            self.__id_map[idref] = self.__id_next
            self.__id_next = self.__id_next + 1
        self.__alias_id = ' ALIASOF="%d"' % self.__id_map[idref]
        self.start_Bookmark(node.get_refnode())

    def start_Folder(self, node):
        if self.__need_header:
            self.__need_header = 0
            self.__write_header(node)
            self.__write_description(node.description())
            print "<DL><p>"
            return
        tab = self.__tab()
        if node.expanded_p(): folded = ''
        else: folded = ' FOLDED'
        add_date = node.add_date() or ''
        if add_date:
            add_date = ' ADD_DATE="%d"' % add_date
        print '%s<DT><H3%s%s>%s</H3>' % \
              (tab, folded, add_date, node.title())
        self.__write_description(node.description())
        print tab + '<DL><p>'
        self.__depth = self.__depth + 1

    def end_Folder(self, node):
        self.__depth = self.__depth - 1
        print self.__tab() + '</DL><p>'

    # support methods

    def __compute_alias_info(self, node):
        alias = self.__alias_id
        if not alias:
            id = node.id()
            if id:
                if not self.__id_map.has_key(id):
                    self.__id_map[id] = self.__id_next
                    self.__id_next = self.__id_next + 1
                alias = ' ALIASID="%d"' % self.__id_map[id]
        self.__alias_id = ''
        return alias

    def __tab(self):
        return "    " * self.__depth

    def __write_description(self, desc):
        if not desc: return
        # write the description, sans leading and trailing whitespace
        print '<DD>%s' % string.strip(bookmarks._prepstring(desc))

    __header = """\
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
    It will be read and overwritten.
    Do Not Edit! -->
<TITLE>%(title)s</TITLE>
<H1>%(title)s</H1>"""

    def __write_header(self, root):
        print self.__header % {'title': root.title()}
