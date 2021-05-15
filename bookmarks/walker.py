"""Tree walker for visiting the nodes of a bookmarks tree."""

__version__ = '$Revision: 1.5 $'


class TreeWalker:
    def __init__(self, root=None):
        self.__root = root

    def get_root(self):
        return self.__root

    def set_root(self, root):
        if self.__root is not None:
            raise RuntimeError, "cannot change root node"
        self.__root = root

    def walk(self):
        self.__walk(self.get_root(), {})

    def __walk(self, node, methodmap):
        nodetype = node.get_nodetype()
        try:
            enter, leave = methodmap[nodetype]
        except KeyError:
            enter, leave = self.get_methods(nodetype, methodmap)
        #
        enter(node)
        try:
            children = node.children()
        except AttributeError:
            # doesn't have children()
            pass
        else:
            walk = self.__walk
            for child in children:
                walk(child, methodmap)
        leave(node)

    def get_methods(self, nodetype, methodmap={}):
        try:
            enter_method = getattr(self, "start_" + nodetype)
        except AttributeError:
            # use id() because it's harmless and built-in
            enter_method = id
        try:
            leave_method = getattr(self, "end_" + nodetype)
        except AttributeError:
            leave_method = id
        #
        tuple = (enter_method, leave_method)
        methodmap[nodetype] = tuple
        return tuple
