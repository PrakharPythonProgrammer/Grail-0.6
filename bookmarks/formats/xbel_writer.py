"""XBEL writer."""

__version__ = '$Revision: 1.12 $'

import bookmarks
import bookmarks.iso8601
import bookmarks.walker
import string
import sys


class Writer(bookmarks.walker.TreeWalker):
    _depth = 0
    __header = '''\
<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE %s
  PUBLIC "%s"
         "%s">
'''

    PUBLIC_ID = bookmarks.XBEL_1_0_PUBLIC_ID
    SYSTEM_ID = bookmarks.XBEL_1_0_SYSTEM_ID

    def __init__(self, root=None):
        bookmarks.walker.TreeWalker.__init__(self, root)
        self.__close_folders = []

    def write_tree(self, fp):
        root = self.get_root()
        root_type = string.lower(root.get_nodetype())
        if root_type == "folder":
            root_type = "xbel"
        fp.write(self.__header % (root_type, self.PUBLIC_ID, self.SYSTEM_ID))
        self.__fp = fp
        self.write = fp.write
        self.walk()

    def get_filetype(self):
        return "xbel"

    def start_Folder(self, node):
        info = node.info()
        title = node.title()
        desc = node.description()
        tab = "  " * self._depth
        attrs = ''
        added = node.add_date()
        if added:
            attrs = '\n      added="%s"' % bookmarks.iso8601.ctime(added)
        if node.id():
            if not attrs:
                attrs = "\n     "
            attrs = '%s id="%s"' % (attrs, node.id())
        #
        if not self._depth:
            self.write('<xbel%s>\n' % attrs)
            if title:
                self.write("%s  <title>%s</title>\n"
                           % (tab, bookmarks._prepstring(title)))
            if info:
                self.__write_info(info)
            if desc:
                self.__write_description(desc, tab)
            self._depth = 1
            self.__close_folders.append(0)
            return
        #
        if node.expanded_p():
            attrs = attrs + ' folded="no"'
        else:
            attrs = attrs + ' folded="yes"'
        if title or info or desc or node.children():
            self.write(tab + '<folder%s>\n' % attrs)
            if title:
                self.write("%s  <title>%s</title>\n"
                           % (tab, bookmarks._prepstring(title)))
            if info:
                self.__write_info(info)
            if desc:
                self.__write_description(desc, tab)
            self._depth = self._depth + 1
            self.__close_folders.append(1)
            # children are handled through the walker
        else:
            self.write(tab + '<folder%s/>\n' % attrs)
            self.__close_folders.append(0)

    def end_Folder(self, node):
        depth = self._depth = self._depth - 1
        if self.__close_folders.pop():
            self.write("  " * depth + "</folder>\n")
        else:
            self.write("</xbel>\n")

    def start_Separator(self, node):
        tab = "  " * self._depth
        self.write(tab + "<separator/>\n")

    def start_Alias(self, node):
        idref = node.idref()
        if idref is None:
            sys.stderr.write("Alias node has no referent; dropping.\n")
        else:
            self.write('%s<alias ref="%s"/>\n'
                       % ("  " * self._depth, idref))

    def start_Bookmark(self, node):
        date_attr = _fmt_date_attr
        added = date_attr(node.add_date(), "added")
        modified = date_attr(node.last_modified(), "modified")
        visited = date_attr(node.last_visited(), "visited")
        desc = string.strip(node.description() or '')
        idref = node.id() or ''
        if idref:
            idref = 'id="%s"' % idref
        title = bookmarks._prepstring(node.title() or '')
        uri = bookmarks._prepstring(node.uri() or '')
        attrs = filter(None, (idref, added, modified, visited))
        #
        tab = "  " * self._depth
        if attrs:
            sep = "\n%s          " % tab
            attrs = " " + string.join(attrs, sep)
        else:
            sep = " "
            attrs = ""
        self.write('%s<bookmark%s%shref="%s">\n' % (tab, attrs, sep, uri))
        if title:
            self.write("%s  <title>%s</title>\n" % (tab, title))
        if node.info():
            self.__write_info(node.info())
        if desc:
            self.__write_description(desc, tab)
        self.write(tab + "  </bookmark>\n")

    # support methods

    def __write_description(self, desc, tab):
        w = 60 - len(tab)
        desc = bookmarks._prepstring(desc)
        if len(desc) > w:
            desc = _wrap_lines(desc, 70 - len(tab), indentation=len(tab) + 4)
            desc = "%s\n%s    " % (desc, tab)
        self.write("%s  <desc>%s</desc>\n" % (tab, desc))

    def __write_info(self, info):
        tab = "  " * (self._depth + 1)
        L = [tab, "<info>\n"]
        append = L.append
        for tag, attrs, content in info:
            append(tab)
            append("  ")
            self.__dump_xml(["metadata", attrs, content], L, tab + "    ")
            append("\n")
        append(tab)
        append("  </info>\n")
        self.write(string.join(L, ""))

    def __dump_xml(self, stuff, L, tab):
        tag, attrs, content = stuff
        has_text = 0
        append = L.append
        append("<")
        append(tag)
        space = " "
        for attr, value in attrs.items():
            append('%s%s="%s"' % (space, attr, bookmarks._prepstring(value)))
            space = "\n%s%s" % (tab, " "*len(tag))
        if not content:
            append("/>")
            return
        has_text = (tab is None) or (attrs.get("xml:space") == "preserve")
        if not has_text:
            for citem in content:
                if type(citem) is type(""):
                    has_text = 1
                    break
        if has_text:
            # some plain text in the data; assume significant:
            append(">")
            for citem in content:
                if type(citem) is type(""):
                    append(bookmarks._prepstring(citem))
                else:
                    # element
                    self.__dump_xml(citem, L, None)
        else:
            append(">\n")
            for citem in content:
                append(tab)
                self.__dump_xml(citem, L, tab + "  ")
                append("\n")
            append(tab)
        append("</%s>" % tag)


def _fmt_date_attr(date, attrname):
    if date:
        return '%s="%s"' % (attrname, bookmarks.iso8601.ctime(date))
    return ''


def _wrap_lines(s, width, indentation=0):
    words = string.split(s)
    lines = []
    buffer = ''
    for w in words:
        if buffer:
            nbuffer = "%s %s" % (buffer, w)
            if len(nbuffer) > width:
                lines.append(buffer)
                buffer = w
            else:
                buffer = nbuffer
        else:
            buffer = w
    if buffer:
        lines.append(buffer)
    if len(lines) > 1:
        lines.insert(0, '')
    return string.join(lines, "\n" + " "*indentation)
