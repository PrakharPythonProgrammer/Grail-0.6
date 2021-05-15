"""Parser for XML bookmarks using the XBEL DTD."""

__version__ = '$Revision: 1.10 $'


import bookmarks
import bookmarks.iso8601
import bookmarks.nodes
import string


class CaptureError(Exception):
    def __init__(self, msg):
        self.msg = msg
        Exception.__init__(self)


class CaptureMixin:
    def __init__(self):
        pass

    def unknown_starttag(self, tag, attrs):
        if self.__capturing:
            self.capture_starttag(tag, attrs)

    def unknown_endtag(self, tag):
        if self.__capturing:
            self.capture_endtag(tag)

    __capturing = 0

    def capturing(self):
        return self.__capturing and 1

    def capture_bgn(self, tag, attrs):
        if self.__capturing:
            raise CaptureError("capturing already in progress")
        self.__capture = [tag, attrs, []]
        self.__context = [self.__capture[-1]]
        self.__capturing = 1

    def capture_end(self, normalize=0):
        if self.__capturing:
            raise CaptureError("capturing not complete")
        if normalize:
            return normalize_capture(self.__capture)
        else:
            return self.__capture

    def capture_data(self, data):
        if not self.__capturing:
            raise CaptureError("capturing not active")
        # create the smallest number of text nodes possible
        if self.__context[-1] and type(self.__context[-1][-1]) is type(""):
            self.__context[-1][-1] = self.__context[-1][-1] + data
        else:
            self.__context[-1].append(data)

    def capture_starttag(self, tag, attrs):
        if not self.__capturing:
            raise CaptureError("capturing not active")
        element = [tag, attrs, []]
        self.__context[-1].append(element)
        self.__context.append(element[-1])
        self.__capturing = self.__capturing + 1

    def capture_endtag(self, tag):
        if not self.__capturing:
            raise CaptureError("capturing not active")
        self.__capturing = self.__capturing - 1
        del self.__context[-1]
        return self.__capturing


def normalize_capture(data, preserve=0, StringType=type("")):
    queue = [(data, preserve)]
    while queue:
        (tag, attrs, content), preserve = queue[0]
        del queue[0]
        #
        preserve = preserve or attrs.get("xml:space") == "preserve"
        #
        if not preserve:
            # remove leading blanks:
            while (content and type(content[0]) is StringType
                   and string.strip(content[0]) == ""):
                del content[0]
            # remove trailing blanks
            cindexes = range(len(content))
            cindexes.reverse()
            for ci in cindexes:
                citem = content[ci]
                if type(citem) is StringType and not string.strip(citem):
                    del content[ci]
                else:
                    break
            # now, if all remaining strings are blank,
            # assume this is element-only:
            for citem in content:
                if type(citem) is StringType:
                    if string.strip(citem):
                        preserve = 1
        if not preserve:
            # All internal strings are blank; remove them.
            cindexes = range(len(content))
            cindexes.reverse()
            for ci in cindexes:
                if type(content[ci]) is StringType:
                    del content[ci]
        for citem in content:
            if type(citem) is not StringType:
                queue.append((citem, preserve))
    return data


class DocumentHandler:
    __folder = None
    __store_node = None

    def __init__(self, filename):
        self.__filename = filename
        self.__context = []
        self.__idmap = {}
        self.__missing_ids = {}
        self.__root = self.new_folder()

    def get_root(self):
        return self.__root

    def start_xbel(self, attrs):
        root = self.get_root()
        self.__store_date(root, attrs, "added", "set_add_date")
        self.handle_id(root, attrs)
    def end_xbel(self):
        pass

    def start_folder(self, attrs):
        self.new_folder(attrs)
    def end_folder(self):
        self.__store_node = None
        self.__folder = self.__context[-1]
        del self.__context[-1]

    def start_title(self, attrs):
        self.save_bgn()
    def end_title(self):
        self.__store_node.set_title(self.save_end())

    __node = None
    def start_bookmark(self, attrs):
        self.new_bookmark(attrs)
        node = self.__node
        self.handle_id(node, attrs)
        node.set_uri(string.strip(attrs.get("href", "")))
        self.__store_date(node, attrs, "added",    "set_add_date")
        self.__store_date(node, attrs, "visited",  "set_last_visited")
        self.__store_date(node, attrs, "modified", "set_last_modified")
    def end_bookmark(self):
        self.__node = None
        self.__store_node = None

    def start_desc(self, attrs):
        self.save_bgn()
    def end_desc(self):
        desc = string.strip(self.save_end())
        if desc:
            if self.__node:
                self.__node.set_description(desc)
            else:
                self.__folder.set_description(desc)

    def start_alias(self, attrs):
        alias = bookmarks.nodes.Alias()
        self.handle_idref(alias, attrs)
        self.__folder.append_child(alias)
    def end_alias(self):
        pass

    def start_separator(self, attrs):
        self.__folder.append_child(bookmarks.nodes.Separator())
    def end_separator(self):
        pass

    # metadata methods:

    def start_info(self, attrs):
        pass
    def end_info(self):
        pass

    def start_metadata(self, attrs):
        self.capture_bgn("metadata", attrs)
    def end_metadata(self):
        metadata = self.capture_end(normalize=1)
        if not metadata[-1]:
            return
        info = self.__node.info()
        if info is None:
            info = []
            self.__node.set_info(info)
        info.append(metadata)

    # support methods:

    def new_bookmark(self, attrs):
        self.__node = bookmarks.nodes.Bookmark()
        self.__store_node = self.__node
        self.__folder.append_child(self.__node)
        return self.__node

    def new_folder(self, attrs={}):
        if self.__folder is not None:
            self.__context.append(self.__folder)
        folded = string.lower(attrs.get("folded", "no")) == "yes"
        self.__folder = bookmarks.nodes.Folder()
        self.__store_node = self.__folder
        if self.__context:
            self.__context[-1].append_child(self.__folder)
        if folded:
            self.__folder.collapse()
        else:
            self.__folder.expand()
        added = attrs.get("added")
        if added:
            try:
                added = bookmarks.iso8601.parse(added)
            except ValueError:
                pass
            else:
                self.__folder.set_add_date(added)
        self.handle_id(self.__folder, attrs)
        return self.__folder

    def handle_id(self, node, attrs, attrname="id", required=0):
        id = attrs.get(attrname)
        if id:
            node.set_id(id)
            self.__idmap[id] = node
            if self.__missing_ids.has_key(id):
                for n in self.__missing_ids[id]:
                    n.set_idref(node)
                del self.__missing_ids[id]
        elif required:
            raise BookmarkFormatError(self.__filename,
                                      "missing %s attribute" % attrname)

    def handle_idref(self, node, attrs, attrname="ref", required=1):
        idref = attrs.get(attrname)
        if idref:
            if self.__idmap.has_key(idref):
                node.set_refnode(self.__idmap[idref])
            else:
                try:
                    self.__missing_ids[idref].append(node)
                except KeyError:
                    self.__missing_ids[idref] = [node]
        elif required:
            raise BookmarkFormatError(self.__filename,
                                      "missing %s attribute" % attrname)

    def __store_date(self, node, attrs, attrname, nodefuncname):
        date = attrs.get(attrname)
        if date:
            func = getattr(node, nodefuncname)
            try:
                date = bookmarks.iso8601.parse(date)
            except ValueError:
                return
            func(date)

    def __normalize_metadata(self, metadata):
        self.__normalize_thing(metadata)
        return metadata

    __buffer = ""
    def save_bgn(self):
        self.__buffer = ""

    def save_end(self):
        s, self.__buffer = self.__buffer, ""
        return string.join(string.split(s))

    def handle_data(self, data):
        if self.capturing():
            self.capture_data(data)
        else:
            self.__buffer = self.__buffer + data

    def handle_starttag(self, tag, method, attrs):
        if self.capturing():
            self.capture_starttag(tag, attrs)
            return
        method(attrs)

    def handle_endtag(self, tag, method):
        if self.capturing() and self.capture_endtag(tag):
            return
        method()


try:
    from xml.parsers.xmllib import XMLParser
except ImportError:
    from xmllib import XMLParser


class Parser(DocumentHandler, CaptureMixin, XMLParser):
    def __init__(self, filename):
        DocumentHandler.__init__(self, filename)
        CaptureMixin.__init__(self)
        XMLParser.__init__(self)
