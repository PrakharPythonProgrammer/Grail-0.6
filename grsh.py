#! /usr/local/bin/python -i

# use "python -i grsh.py" to get an interactive python with Grail's 'ni' setup,
# or adjust the shell line above to get the right behavior.

import os
import sys

# Get the path munging & general setup from grail.py:
import grail

# Standard Grail imports
import grailutil

d = os.path.join(grailutil.getgraildir(), "user")
if os.path.isdir(d):
    sys.path.insert(0, d)
for d in ('', '.'):
    if d in sys.path:
        sys.path.remove(d)
del d

# print the banner
print sys.version
print sys.copyright
print grail.GRAILVERSION, "debugging shell"
