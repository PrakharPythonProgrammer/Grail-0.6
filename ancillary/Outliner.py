import string

True = 1
False = None


class OutlinerNode:
    _expanded_p = True
    _parent = None
    _depth = 0

    def __init__(self):
        self._children = []

    def __repr__(self):
        tabdepth = self._depth - 1
        if self.leaf_p(): tag = ' '
        elif self.expanded_p(): tag = '+'
        else: tag = '-'
        return (' ' * (tabdepth * 3)) + tag

    def clone(self):
        newnode = OutlinerNode()
        newnode._expanded_p = self._expanded_p
        newnode._depth = self._depth
        for child in self._children:
            newchild = child.clone()
            newchild._parent = newnode
            newnode._children.append(newchild)
        return newnode

    def close(self):
        self._parent = None
        for child in self._children: child.close()

    def _redepthify(self, node):
        depth = node.depth()
        for child in node.children():
            child._depth = depth + 1
            self._redepthify(child)

    def append_child(self, node):
        self._children.append(node)
        node._parent = self
        node._depth = self._depth + 1
        self._redepthify(node)

    def insert_child(self, node, index):
        self._children.insert(index, node)
        node._parent = self
        node._depth = self._depth + 1
        self._redepthify(node)

    def del_child(self, node):
        try:
            child_i = self._children.index(node)
            rtnnode = self._children[child_i]
            del self._children[child_i]
            return rtnnode
        except (ValueError, IndexError):
            return False

    def replace_child(self, node, newnode):
        newnode._depth = self._depth + 1
        try:
            child_i = self._children.index(node)
            rtnnode = self._children[child_i]
            self._children[child_i] = newnode
            return rtnnode
        except (ValueError, IndexError):
            return False

    def expand(self): self._expanded_p = True
    def collapse(self): self._expanded_p = False

    def children(self): return self._children
    def parent(self): return self._parent
    def expanded_p(self): return self._expanded_p
    def leaf_p(self): return not self._children

    def depth(self): return self._depth



class OutlinerViewer:
    def __init__(self, root, follow_all_children=None, shared_root=None):
        """Create a new viewer for a tree of nodes.

        If follow_all_children is true, then child links are followed
        even if the child is collapsed.  If false, then only expanded
        child links are followed.

        If shared_root is true, then the tree is not close()'d when
        the viewer is destroyed.  This can be cause memory leaks if
        misused.

        """
        self._root = root
        self._nodes = []
        self._shared_root = shared_root
        self._follow_all_children_p = follow_all_children

    def __del__(self):
        if not self._shared_root:
            self._root.close()

    ## Derived class specializations

    def _insert(self, node, index=None): pass
    def _delete(self, start, end=None): pass
    def _select(self, index): pass
    def _clear(self): pass

    def _populate(self, node):
        # insert into linear list
        self._nodes.append(node)
        # calculate the string to insert into the list box
        self._insert(node)
        if node.get_nodetype() == "Folder" \
           and (node.expanded_p() or self._follow_all_children_p):
            for child in node.children():
                self._populate(child)

    ## API methods

    def populate(self, showroot=0):
        if showroot:
            self._populate(self._root)
        else:
            for child in self._root.children():
                OutlinerViewer._populate(self, child)

    def clear(self):
        self._clear()
        self._nodes = []

    def insert_nodes(self, at_index, node_list, before_p=0):
        if not before_p: at_index = at_index + 1
        nodecount = len(node_list)
        for node in node_list:
            self._nodes.insert(at_index, node)
            self._insert(node, at_index)
            at_index = at_index + 1

    def delete_nodes(self, start, end):
        self._delete(start, end)
        del self._nodes[start:end+1]

    def update_node(self, node):
        index = self.index(node)
        # TBD: is there a more efficient way of doing this?
        self._delete(index)
        self._insert(node, index)

    def _expand(self, node, at):
        for child in node.children():
            self.insert_nodes(at, [child], True)
            at = at + 1
            if not child.leaf_p() and child.expanded_p():
                self._expand(child)

    def expand_node(self, node):
        self._expand(node, self.index(node)+1)

    def select_node(self, node):
        self._select(self.index(node))

    def node(self, index):
        if 0 <= index < len(self._nodes):
            return self._nodes[index]
        else:
            return None

    def index(self, node):
        try:
            return self._nodes.index(node)
        except ValueError:
            return None

    def count(self):
        return len(self._nodes)


class OutlinerController:
    def __init__(self, root=None, viewer=None):
        self._viewer = viewer
        self._root = root
        self._backup = root.clone()
        self._aggressive_p = None
        if not root: self._root = OutlinerNode()
        if not viewer: self._viewer = OutlinerViewer(self._root)

    def root(self): return self._root
    def set_root(self, newroot):
        self._root.close()
        self._backup.close()
        self._root = newroot
        self._backup = newroot.clone()
    def update_backup(self):
        self._backup.close()
        self._backup = self._root.clone()
    def root_redisplay(self):
        self._viewer.clear()
        self._viewer.populate()
    def revert(self):
        self._root.close()
        self._root = self._backup.clone()

    def viewer(self): return self._viewer
    def set_viewer(self, viewer): self._viewer = viewer

    def set_aggressive_collapse(self, flag): self._aggressive_p = flag
    def aggressive_collapse_p(self): return self._aggressive_p

    def _sibi(self, node):
        parent = node.parent()
        if not parent: return (None, None, [])
        sibs = parent.children()
        sibi = sibs.index(node)
        return parent, sibi, sibs

    def collapsable_p(self, node):
        # This node is only collapsable if it is an unexpanded branch
        # node, or the aggressive collapse flag is set.
        if node.leaf_p() or not node.expanded_p(): return False
        else: return True

    def collapse_node(self, node):
        if not self.collapsable_p(node):
            if self.aggressive_collapse_p():
                node = node.parent()
                if not self.collapsable_p(node): return
            else: return
        node.collapse()
        self.root_redisplay()
        return node

    def expand_node(self, node):
        # don't expand a leaf or an already expanded node
        if node.leaf_p() or node.expanded_p(): return
        # now toggle the expanded flag and update the listbox
        node.expand()
        self.root_redisplay()

    def show_node(self, node):
        # travel up tree from this node, making sure all ancestors are
        # expanded (i.e. visible)
        node = node.parent()
        while node:
            node.expand()
            node = node.parent()
        self.root_redisplay()

    def shift_left(self, node):
        # find the index of the node in the sib list.
        parent, sibi, sibs = self._sibi(node)
        if not parent: return
        grandparent, parenti, aunts = self._sibi(parent)
        if not grandparent: return
        # node now becomes a sibling of it's parent, and all of node's
        # later siblings become the node's children
        parent.del_child(node)
        grandparent.insert_child(node, parenti+1)
        if sibi < len(sibs):
            for sib in sibs[sibi:]:
                parent.del_child(sib)
                node.append_child(sib)
        self.root_redisplay()

    def shift_right(self, node):
        # find the index of the node in the sib list.
        parent, sibi, sibs = self._sibi(node)
        # cannot shift right the first child in the sib list
        if sibi == 0: return
        # reparent the node such that it is now the child of the
        # preceding sibling in the sib list
        newparent = sibs[sibi-1]
        # cannot shift right if the above node is a leaf
        if newparent.leaf_p(): return
        parent.del_child(node)
        newparent.append_child(node)
        newparent.expand()
        # update the viewer
        self.root_redisplay()

    def shift_up(self, node):
        # find the viewer index of the node, and get the node just
        # above it.  if it's the first visible node, it cannot be
        # shifted up.
        nodevi = self._viewer.index(node)
        if nodevi == 0: return
        above = self._viewer.node(nodevi-1)
        parent, sibi, sibs = self._sibi(node)
        if not parent: return
        # if node and above are at the same depth, just rearrange.
        if node.depth() == above.depth():
            parent.del_child(node)
            parent.insert_child(node, sibi-1)
        # if node is deeper than above, node becomes a sibling of
        # above and move just above *it*
        elif node.depth() > above.depth():
            aparent, asibi, asibs = self._sibi(above)
            if not aparent: return
            parent.del_child(node)
            aparent.insert_child(node, asibi)
            aparent.expand()
        # if above is deeper than node, then above becomes a sibling
        # of node and gets appended to the end of node's sibling list.
        else:
            aparent, asibi, asibs = self._sibi(above)
            if not aparent: return
            parent.del_child(node)
            aparent.append_child(node)
            aparent.expand()
        self.root_redisplay()

    def shift_down(self, node):
        # find the viewer index of the node, and get the node just
        # below it.  if it's the last visible node, it cannot be
        # shifted down.
        nodevi = self._viewer.index(node)
        if nodevi is None or nodevi >= self._viewer.count()-1: return
        below = self._viewer.node(nodevi+1)
        parent, sibi, sibs = self._sibi(node)
        if not parent: return
        # if below is really node's first child, then what we want to
        # do is try to shift into node's next sibling's child list
        if node.get_nodetype() == "Folder":
            children = node.children()
            if len(children) > 0 and below == children[0]:
                if sibi+1 < len(sibs) and not sibs[sibi+1].leaf_p():
                    below = sibs[sibi+1]
        # if node and below are at the same depth, then what happens
        # depends on the state of below.  If below is an expanded
        # branch, then node becomes it's first sibling, otherwise it
        # just swaps places
        if node.depth() == below.depth():
            if not below.leaf_p() and below.expanded_p():
                parent.del_child(node)
                below.insert_child(node, 0)
            else:
                parent.del_child(node)
                parent.insert_child(node, sibi+1)
        # if node is deeper than below, node becomes a sibling of it's parent
        elif node.depth() > below.depth():
            grandparent, parenti, aunts = self._sibi(parent)
            if not grandparent: return
            parent.del_child(node)
            grandparent.insert_child(node, parenti+1)
        # if below is deeper than node, then node actually swaps
        # places with it's next sibling
        else:
            # if it's the last of the sibling, then it actually shifts left
            if sibi >= len(sibs)-1:
                self.shift_left(node)
                return
            else:
                parent.del_child(node)
                parent.insert_child(node, sibi+1)
        self.root_redisplay()
