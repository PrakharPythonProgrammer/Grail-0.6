"""Support for client-side image maps."""

import string

class Shape:
    """shaped regions for client-side image maps."""

    def __init__(self, kind, coords, url, target=""):
        self.kind = kind
        self.coords = coords
        self.url = url
        self.target = target

    def pointin(self, x, y):
        """predicate: Are x,y coordinates within region?"""
        isin = 0
        if self.kind == 'rect':
            if self.coords[0][0] <= x <= self.coords[1][0] and \
               self.coords[0][1] <= y <= self.coords[1][1]:
                isin = 1

        elif self.kind == 'circle':
            # is the distance from the point to the center of the
            # circle less than the radius? 
            distance_squared = pow((self.coords[0][0] - x), 2) + \
                               pow((self.coords[0][1] - y), 2)  
            if distance_squared <= pow(self.coords[1], 2):
                isin = 1

        elif self.kind == 'poly':
            isin = self.poly_pointin(x, y)

        elif self.kind == 'default':
            isin = 1

        return isin

    def poly_pointin(self, x, y):
        """Is point (x,y) inside polygon with vertices coords?

        From C code by Paul Bourke at
        <http://www.auckland.ac.nz/arch/pdbourke/geometry/insidepoly.html>
        Determining whether or not a point lies on the interior of a polygon.

        The algorithm is a little pesky because a point on an edge of the
        polygon doesn't appear to be treated as *in* the polygon. Not doing
        anything about this at the moment.
        """

        counter = 0
        p1 = self.coords[0]
        for i in range(1,len(self.coords)):
            p2 = self.coords[i]
            if y > min(p1[1], p2[1]):
                if y <= max(p1[1], p2[1]):
                    if x <= max (p1[0], p2[0]):
                        if p1[1] != p2[1]:
                            xintersect = \
                              (y-p1[1])*(p2[0]-p1[0])/(p2[1]-p1[1])+p1[0]
                            if p1[0] == p2[0] or x <= xintersect:
                                counter = counter + 1
            p1 = p2
    
        return counter % 2

class MapInfo:
    """Holds shapes during parsing.

    The shapes are copied into a MapThunk object when the map is used.
    """

    def __init__(self, name):
        self.name = name
        self.shapes = []

    def add_shape(self, kind, coords, url, target=""):
        self.shapes.append(Shape(kind, coords, url, target))


class MapThunk:
    """Map interface for an ImageWindow, will wait for MAP to be parsed.

    The <MAP> tag may not have been parsed by the time the user clicks
    on the image, particularly if the USEMAP attribute specifies a MAP
    in a different page. Initially, the map has no shapes and it waits
    until the method url() is called, which calls force to load the
    shapes from the parser. If force() fails, then url returns None
    and the next call to url() will also invoke force().

    get_shape() memoizes the shape object at a particular (x,y)
    coordinate because the lookup could be slow when there are many
    shapes. not sure if this is necessary/desirable.
    """

    def __init__(self, context, name):
        """Link MapThunk to the context containing the map."""

        self.context = context
        self.name = name
        self.shapes = []
        self.waiting = 1
        self.memo = {}

    def force(self):
        """Try to load shapes from the context."""

        try:
            map = self.context.image_maps[self.name]
        except KeyError:
            pass
        else:
            self.shapes = map.shapes
            self.waiting = 0
    
    def url(self, x, y):
        """Get url associated with shape at (x,y)."""

        # first check to see if the map has been parsed
        if self.waiting == 1:
            self.force()
            if self.waiting == 1:
                return None, None

        # get the shape and return url
        shape = self.get_shape(x, y)
        if shape:
            return shape.url, shape.target
        else:
            return None, None

    def get_shape(self, x, y):
        """Get shape at coords (x,y)."""
        try:
            # memoize good for lots of shapes
            return self.memo[(x,y)]
        except KeyError:
            # does this iterate through in order?
            # it should so that overlapping shapes are handled properly
            for shape in self.shapes:
                if shape.pointin(x, y) == 1:
                    self.memo[(x,y)] = shape
                    return shape
            return None

