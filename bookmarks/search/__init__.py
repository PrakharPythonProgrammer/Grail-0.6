"""Top-level interface to the search mechanisms."""

__version__ = '$Revision: 1.3 $'

import bookmarks.nodes
import copy


def get_editor(which, frame, options=None):
    klass = __get_component_class(which, "Editor")
    if klass is not None:
        if options is None:
            return klass(frame)
        else:
            return klass(frame, options)


def get_matcher(which, options):
    klass = __get_component_class(which, "Matcher")
    if klass is not None:
        return klass(options)


def find_nodes(folder, matcher, copynodes=1):
    # determine if folder matches,
    # then check to see what children match,
    # calling find_nodes() recursively on
    # nested folders
    if not hasattr(matcher, "match_Folder"):
        return None
    match, recurse = matcher.match_Folder(folder)
    children = []
    if recurse:
        for child in folder.children():
            nodetype = child.get_nodetype()
            if nodetype == "Folder":
                node = find_nodes(child, matcher)
                if node is not None:
                    children.append(node)
            elif hasattr(matcher, "match_" + nodetype):
                method = getattr(matcher, "match_" + nodetype)
                if method(child):
                    if copynodes:
                        children.append(copy.copy(child))
                    else:
                        # This approach is probably broken....
                        children.append(bookmarks.nodes.Alias(child))
    if match or children:
        folder = copy.copy(folder)
        folder.set_children(children)
        if children:
            folder.expand()
        else:
            folder.collapse()
        return folder


# Interfaces that need to be implemented in the specific search modules.
# These classes are defined primarily for documentation purposes; read
# the docstrings!

class EditorInterface:

    def __init__(self, frame, options=None):
        self.__options = options

    def get_options(self):
        """Return the current options object."""
        return self.__options


class MatcherInterface:

    def __init__(self, options):
        pass

    def match_Bookmark(self, bookmark):
        """Determine if a bookmark matches the search specification.

        Returns true iff the bookmark matches the search specification.
        """
        return 0

    def match_Folder(self, folder):
        """Determine if a folder matches the search specification.

        Returns two values: (`match', `recurse'), where `match' indicates
        whether the folder node itself matches, and `recurse' indicates
        whether a recursive search of the children should be performed.
        The default result fails to match the node but does continue to
        search the children.
        """
        return 0, 1

    def match_SomeNodeType(self, somenodetype):
        return 0


# Internal helpers:

def __get_search_module(which):
    d = {}
    s = "from bookmarks.search import %sSearch" % which
    try:
        exec s in d
    except ImportError:
        return None
    try:
        return d[which + "Search"]
    except KeyError:
        return None


def __get_component_class(which, name):
    m = __get_search_module(which)
    if m is not None:
        try:
            return getattr(m, which + name)
        except AttributeError:
            return None
