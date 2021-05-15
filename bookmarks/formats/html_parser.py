"""Parser for Netscape HTML bookmarks format."""

__version__ = '$Revision: 1.3 $'


import bookmarks
import bookmarks.nodes
import html_scraper
import string

import sgml.SGMLParser


class Parser(html_scraper.Parser):
    __store_node = None
    __node = None

    def __init__(self, filename):
        html_scraper.Parser.__init__(self, filename)
        self.sgml_parser = sgml.SGMLParser.SGMLParser(gatherer=self)
        self.__idmap = {}
        self.__missing_ids = {}
        self.__folder = self.get_root()
        self.__context = []

    def new_bookmark(self):
        self.__node = bookmarks.nodes.Bookmark()
        self.__folder.append_child(self.__node)
        return self.__node

    def new_folder(self, attrs={}):
        self.__context.append(self.__folder)
        self.__folder = bookmarks.nodes.Folder()
        if self.__context:
            self.__context[-1].append_child(self.__folder)
        if attrs.has_key("folded"):
            self.__folder.collapse()
        else:
            self.__folder.expand()
        if attrs.has_key('add_date'):
            self.__folder.set_add_date(string.atoi(attrs['add_date']))
        return self.__folder

    def start_h1(self, attrs):
        html_scraper.Parser.start_h1(self, attrs)
        self.__context.append(self.__folder)

    def end_h1(self):
        html_scraper.Parser.end_h1(self)
        self.__store_node = self.get_root()

    def start_h3(self, attrs):
        self.new_folder(attrs)
        self.save_bgn()

    def end_h3(self):
        title = self.save_end()
        if self.__folder is not None:
            self.__store_node = self.__folder
            self.__store_node.set_title(title)

    def do_hr(self, attrs):
        snode = bookmarks.nodes.Separator()
        self.__folder.append_child(snode)

    def end_dl(self):
        self.ddpop()
        if not self.__context:
            lineno = self.sgml_parser.line()
            if lineno is not None:
                extra = " at line " + `lineno`
            else:
                extra = ""
            raise bookmarks.PoppedRootError(self._filename + extra)
        self.__folder = self.__context[-1]
        del self.__context[-1]

    def ddpop(self):
        if self.__store_node:
            self.__store_node.set_description(self.save_end())
            self.__store_node = None

    def do_dd(self, attrs):
        self.save_bgn()

    def do_dt(self, attrs):
        self.ddpop()

    def start_dl(self, attrs):
        self.ddpop()

    def start_a(self, attrs):
        if attrs.has_key("aliasof"):
            idref = attrs["aliasof"]
            try:
                bookmark = self.__idmap[idref]
            except KeyError:
                # bookmark not yet read in:
                alias = bookmarks.nodes.Alias()
                try:
                    self.__missing_ids[idref].append(alias)
                except KeyError:
                    self.__missing_ids[idref] = [alias]
            else:
                alias = bookmarks.nodes.Alias(bookmark)
            self.__folder.append_child(alias)
        else:
            self.new_bookmark()
            node = self.__node          # convenience
            if attrs.has_key('href'):
                node.set_uri(attrs['href'])
            if attrs.has_key('add_date'):
                node.set_add_date(string.atoi(attrs['add_date']))
            if attrs.has_key('last_modified'):
                node.set_last_modified(string.atoi(attrs['last_modified']))
            if attrs.has_key('last_visit'):
                node.set_last_visited(string.atoi(attrs['last_visit']))
            if attrs.has_key('aliasid'):
                id = string.strip(attrs["aliasid"])
                self.__idmap[id] = node
                node.set_id(id)
                if self.__missing_ids.has_key(id):
                    for alias in self.__missing_ids[id]:
                        alias.set_refnode(node)
                    del self.__missing_ids[id]
            self.save_bgn()

    def end_a(self):
        if self.__node is not None:
            self.__node.set_title(self.save_end())
        self.__store_node = self.__node
