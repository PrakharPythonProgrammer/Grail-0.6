#! /usr/bin/env python

"""HTML to PostScript translator.

This is a standalone script for command line conversion of HTML documents
to PostScript.  Use the '-h' option to see information about all too many
command-line options.

"""

import os
import sys

# Always figure the script_dir; this is used to initialize the module
# (see loading of PostScript templates at the end).
script_name = sys.argv[0]
while 1:
    script_dir = os.path.dirname(script_name)
    if not os.path.islink(script_name):
        break
    script_name = os.path.join(script_dir, os.readlink(script_name))
script_dir = os.path.join(os.getcwd(), script_dir)
script_dir = os.path.normpath(script_dir)

if __name__ == '__main__':
    for path in 'pythonlib', 'utils', 'ancillary', 'sgml_lex', script_dir:
        sys.path.insert(0, os.path.join(script_dir, path))
    # don't load this twice when used as a script:
    sys.modules['html2ps'] = sys.modules['__main__']

if sys.version < "1.5":
    import ni

import grailutil
grailutil._grail_root = script_dir

import printing.main
import printing.utils


if __name__ == '__main__':
    if sys.argv[1:] and sys.argv[1] == "--profile":
        del sys.argv[1]
        printing.main.profile_main()
    else:
        printing.main.main()
