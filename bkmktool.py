#! /usr/bin/env python

__version__ = '$Revision: 2.3 $'


import os
import sys

grail_root = sys.path[0]
for path in 'utils', 'pythonlib', 'ancillary', 'sgml_lex':
    sys.path.insert(0, os.path.normpath(os.path.join(grail_root, path)))


import bookmarks.main

bookmarks.main.main()
