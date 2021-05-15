"""Several useful routines that isolate some of the weirdness of Grail-based
applications.
"""
__version__ = '$Revision: 1.3 $'

import os
import string

# TBD: hack!  grail.py calculates grail_root, which would be
# convenient to export to extensions, but you can't `import grail' or
# `import __main__'.  grail.py isn't designed for that.  You could
# `from grail import grail_root' but that's kind of gross.  This
# global holds the value of grail_root which can be had with
# grailutil.get_grailroot()
_grail_root = None
_grail_app = None


# XXX Unix specific stuff
# XXX (Actually it limps along just fine for Macintosh, too)

def getgraildir():
    return getenv("GRAILDIR") or os.path.join(gethome(), ".grail")


def get_grailroot():
    return _grail_root


def get_grailapp():
    return _grail_app


def gethome():
    try:
        home = getenv("HOME")
        if not home:
            import pwd
            user = getenv("USER") or getenv("LOGNAME")
            if not user:
                pwent = pwd.getpwuid(os.getuid())
            else:
                pwent = pwd.getpwnam(user)
            home = pwent[6]
        return home
    except (KeyError, ImportError):
        return os.curdir


def getenv(s):
    if os.environ.has_key(s): return os.environ[s]
    return None


def which(filename, searchlist=None):
    if searchlist is None:
        import sys
        searchlist = sys.path
    for dir in searchlist:
        found = os.path.join(dir, filename)
        if os.path.exists(found):
            return found
    return None


def establish_dir(dir):
    """Ensure existence of DIR, creating it if necessary.

    Returns 1 if successful, 0 otherwise."""
    if os.path.isdir(dir):
        return 1
    head, tail = os.path.split(dir)
    if not establish_dir(head):
        return 0
    try:
        os.mkdir(dir, 0777)
        return 1
    except os.error:
        return 0


def conv_mimetype(type):
    """Convert MIME media type specifications to tuples of
    ('type/subtype', {'option': 'value'}).
    """
    if not type:
        return None, {}
    if ';' in type:
        i = string.index(type, ';')
        opts = _parse_mimetypeoptions(type[i + 1:])
        type = type[:i]
    else:
        opts = {}
    fields = string.split(string.lower(type), '/')
    if len(fields) != 2:
        raise ValueError, "Illegal media type specification."
    type = string.join(fields, '/')
    return type, opts


def _parse_mimetypeoptions(options):
    opts = {}
    options = string.strip(options)
    while options:
        if '=' in options:
            pos = string.find(options, '=')
            name = string.lower(string.strip(options[:pos]))
            value = string.strip(options[pos + 1:])
            options = ''
            if ';' in value:
                pos = string.find(value, ';')
                options = string.strip(value[pos + 1:])
                value = string.strip(value[:pos])
            if name:
                opts[name] = value
        else:
            options = None
    return opts
