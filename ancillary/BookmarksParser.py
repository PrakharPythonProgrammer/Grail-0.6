import Outliner
import string

from bookmarks.nodes import norm_uri


class BookmarkNode(Outliner.OutlinerNode):
    """Bookmarks are represented internally as a tree of nodes containing
    relevent information.

    Methods:

      title()         -- return title
      uri()           -- return URI string
      add_date()      -- return bookmark add timestamp
      last_modified() -- return last modified timestamp
      last_visited()  -- return last visited timestamp
      description()   -- return description string
      id()	      -- return ID of node
      idref()	      -- return ID of referenced node

        [[self explanatory??]]

      set_title(title)
      set_uri(uri_string)
      set_add_date(seconds)
      set_last_modified(seconds)
      set_last_visited(seconds)
      set_description(string)
      set_id(id)
      set_idref(id)

    Instance variables:

      No Public Ivars
    """
    _uri = ''
    _islink_p = 0
    _isseparator_p = 0
    _last_checked = None
    _response = None

    def __init__(self, title='', uri_string = None,
                 add_date=None, last_visited=None,
                 last_modified=None, description=''):
        self._children = []             # performance hack; should call base
        self._title = title
        if uri_string:
            self._uri = norm_uri(uri_string)
            self._islink_p = 1
        self._desc = description
        self._add_date = add_date
        self._visited = last_visited
        self._modified = last_modified
        self._leaf_p = uri_string or last_visited

    def __repr__(self):
        return Outliner.OutlinerNode.__repr__(self) + ' ' + self.title()
    def leaf_p(self): return self._leaf_p
    def alias_p(self): return self._idref and 1 or 0

    def clone(self):
        # subclasses really should override this method!
        newnode = BookmarkNode(self._title, self._uri, self._add_date,
                               self._visited, self._desc)
        # TBD: no good way to do this
        newnode._expanded_p = self._expanded_p
        newnode._depth = self._depth
        for child in self._children:
            newchild = child.clone()
            newchild._parent = newnode
            newnode._children.append(newchild)
        # set derived class attributes
        newnode._islink_p = self._islink_p
        newnode._isseparator_p = self._isseparator_p
        newnode._leaf_p = self._leaf_p
        newnode._last_checked = self._last_checked
        newnode._response = self._response
        newnode._id = None
        newnode._idref = self._idref
        return newnode

    def append_child(self, node):
        Outliner.OutlinerNode.append_child(self, node)
        self._leaf_p = 0
    def insert_child(self, node, index):
        Outliner.OutlinerNode.insert_child(self, node, index)
        self._leaf_p = 0
    def del_child(self, node):
        rtnnode = Outliner.OutlinerNode.del_child(self, node)
        if self._islink_p and len(self._children) == 0:
            self._leaf_p = 1
        return rtnnode

    def title(self): return self._title
    def uri(self): return self._uri
    def add_date(self): return self._add_date
    def last_modified(self): return self._modified
    def last_visited(self): return self._visited
    def description(self): return self._desc
    def islink_p(self): return self._islink_p
    def isseparator_p(self): return self._isseparator_p

    def set_separator(self):
        self._isseparator_p = 1
        self._leaf_p = 1
        self._title = '------------------------------'

    def set_title(self, title=''):
        self._title = string.strip(title)
    def set_add_date(self, add_date=None):
        self._add_date = add_date
    def set_last_visited(self, lastv):
        self._visited = lastv
        self._leaf_p = 1
    def set_last_modified(self, lastm):
        self._modified = lastm
        self._leaf_p = 1
    def set_last_checked(self, checked=None, response=None):
        self._last_checked = checked
        self._response = response

    _id = None
    _idref = None
    def id(self):
        return self._id
    def idref(self):
        return self._idref
    def set_id(self, id):
        self._id = id
    def set_idref(self, id):
        self._idref = id

    def set_description(self, description=''):
        self._desc = string.strip(description)
    def set_uri(self, uri_string=''):
        self._uri = norm_uri(uri_string)
        if self._uri:
            self._islink_p = 1
            self._leaf_p = 1

    # the rest of these are only needed until there's a better way to do
    # it, to support the old-style pickle formats

    __info = None
    def info(self):
        return self.__info
    def set_info(self, info):
        self.__info = info

    def set_children(self, children):
        self._children = map(None, children)

    def get_nodetype(self):
        """Return the type of information represented by the node.

        This is needed so the XBEL writer can handle these reasonably."""
        if self.isseparator_p():
            return "Separator"
        if self.islink_p():
            return "Bookmark"
        return "Folder"
