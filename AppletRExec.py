"""Restricted execution for Applets."""


import SafeDialog
import SafeTkinter
import os
from rexec import RExec, RHooks
import string
import sys
import tempfile
import types
import urllib
import urlparse


def is_url(p):
    u = urlparse.urlparse(p)
    #
    # Unfortunately path names on the MAC and Windows parse
    # similarly to URL's.  We currently have to not recognize
    # URL's that have single letter scheme identifiers because
    # they can be confused with the drive letter component
    # of a disk path on these platforms.  
    if u[0] and len(u[0]) > 1:
        return u[0]
    return u[1]


class AppletRHooks(RHooks):

    def path_join(self, p1, p2):
        if is_url(p1) or is_url(p2):
            if '/' not in p2 and '.' not in p2:
                # Assume it's a directory -- needed for package loading
                p2 = p2 + "/"
            return urlparse.urljoin(p1, p2)
        else:
            return RHooks.path_join(self, p1, p2)

    def path_isdir(self, p):
        if is_url(p):
            return p[-1:] == "/"
        else:
            return RHooks.path_isdir(self, p)

    def openfile(self, p, mode='r', buf=-1):
        # Only used to read modules
        if is_url(p):
            # Avoid hitting the remote server with every suffix
            # in the suffix list (.pyc, .so, module.so).
            # We can't strip these from the suffix list, since
            # (at least under certain circumstances) shared libs
            # are okay when found on the local file system.
            if p[-3:] != '.py':
                raise IOError, "Only Python modules may be read remotely"
            return self.openurl(p, mode, buf)
        else:
            return open(p, mode, buf)

    def openurl(self, p, mode='r', buf=-1):
        if mode not in ('r', 'rb'):
            raise IOError, "Can't open URL for writing"
        app = self.rexec.app
        if not app:
            # Fall back for test mode
            return urllib.urlopen(p)
        # Always specify reload since modules are already cached --
        # when we get here it must either be the first time for
        # this module or the user has requested to reload the page.
        api = self.rexec.app.open_url(p, 'GET', {}, reload=1)
        errcode, errmsg, params = api.getmeta()
        if errcode != 200:
            api.close()
            raise IOError, errmsg
        return PseudoFile(api)


class PseudoFile:

    # XXX Is this safe?
    # XXX Is this sufficient?

    def __init__(self, api):
        self.api = api
        self.buf = ''
        self.done = 0

    def close(self):
        api = self.api
        self.api = self.buf = self.done = None
        if api:
            api.close()

    def read(self, n=-1):
        if n < 0:
            n = sys.maxint
        while len(self.buf) < n and not self.done:
            self.fill(min(n - len(self.buf), 1024*8))
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def readlines(self):
        list = []
        while 1:
            line = self.readline()
            if not line: break
            list.append(line)
        return list

    def readline(self):
        while '\n' not in self.buf and not self.done:
            self.fill()
        i = string.find(self.buf, '\n')
        if i < 0:
            i = len(self.buf)
        else:
            i = i+1
        data, self.buf = self.buf[:i], self.buf[i:]
        return data

    def fill(self, n = 512):
        data = self.api.getdata(n)
        if data:
            self.buf = self.buf + data
        else:
            self.done = 1


class AppletRExec(RExec):

    # Allow importing the ILU Python runtime
    ok_builtin_modules = RExec.ok_builtin_modules + ('iluPr',)

    # Remove posix primitives except
    ok_posix_names = ('error',)

    def __init__(self, hooks=None, verbose=1, app=None, group=None):
        self.app = app
        self.appletgroup = group or "."
        self.backup_modules = {}
        if not hooks: hooks = AppletRHooks(self, verbose)
        RExec.__init__(self, hooks, verbose)
        self.modules['Dialog'] = SafeDialog
        self.modules['Tkinter'] = SafeTkinter
        self.special_modules = self.modules.keys()
        self.save_files()
        self.set_files()
        # Don't give applets the real SystemExit, since it exits Grail!
        self.modules['__builtin__'].SystemExit = "SystemExit"

    # XXX The path manipulations below are not portable to the Mac or PC

    def set_urlpath(self, url):
        self.reset_urlpath()
        path = self.modules['sys'].path
        path.append(url)

    def reset_urlpath(self):
        path = self.modules['sys'].path
        path[:] = self.get_url_free_path()

    def get_url_free_path(self):
        path = self.modules['sys'].path
        return filter(lambda x: not is_url(x), path)

    # XXX It would be cool if make_foo() would be invoked on "import foo"

    def make_initial_modules(self):
        RExec.make_initial_modules(self)
        self.make_al()
        self.make_socket()
        self.make_sunaudiodev()
        self.make_types()
        self.make_iluRt()
        self.make_os()

    def make_os(self):
        from Bastion import Bastion
        s = OSSurrogate(self)
        b = Bastion(s)
        b.path = Bastion(s.path)
        b.name = s.name
        b.curdir = s.curdir
        b.pardir = s.pardir
        b.sep = s.sep
        b.pathsep = s.pathsep
        b.environ = s.environ
        b.error = s.error
        self.modules['os'] = self.modules[os.name] = b
        self.modules['ospath'] = self.modules[os.name + 'path'] = b.path

    def make_osname(self):
        pass

    def make_iluRt(self):
        try:
            import iluRt
        except ImportError:
            return
        m = self.copy_except(iluRt, ())
 
    def make_al(self):
        try:
            import al
        except ImportError:
            return
        m = self.copy_except(al, ())
 
    def make_socket(self):
        try:
            import socket
        except ImportError:
            return
        m = self.copy_except(socket, ('fromfd',))
        # XXX Ought to only allow connections to host from which applet loaded

    def make_sunaudiodev(self):
        try:
            import sunaudiodev
        except ImportError:
            return
        m = self.copy_except(sunaudiodev, ())

    def make_types(self):
        m = self.copy_except(types, ())

    def r_open(self, file, mode='r', buf=-1):
        return self.modules['os'].fopen(file, mode, buf)

    # Cool reload hacks.  XXX I'll explain this some day...

    def set_reload(self):
        for mname, module in self.modules.items():
            if mname not in self.special_modules and \
               mname not in self.ok_builtin_modules and \
               mname not in self.ok_dynamic_modules:
                self.backup_modules[mname] = module
                del self.modules[mname]

    def clear_reload(self):
        self.backup_modules = {}

    def add_module(self, mname):
        if self.modules.has_key(mname):
            return self.modules[mname]
        if self.backup_modules.has_key(mname):
            self.modules[mname] = m = self.backup_modules[mname]
            self.backup_modules[mname]
            return m
        return RExec.add_module(self, mname)


class OSSurrogate:

    """Public methods of this class are functions in module 'os'.

    Methods whose name begins with '_' and all class and instance
    variables are private (thanks to bastionization), except those
    variables explicitly copied by make_os() above.

    """

    # Class variables (these become public by explicit assignment in
    # make_os()).

    name = os.name
    curdir = os.curdir
    pardir = os.pardir
    sep = os.sep
    pathsep = os.pathsep
    error = os.error

    # Private methods

    def __init__(self, rexec):
        self.rexec = rexec
        self.app = rexec.app
        self.appletsdir = os.path.join(self.app.graildir, "applets")
        self.home = os.path.normcase(
            os.path.join(self.appletsdir,
                         group2dirname(self.rexec.appletgroup)))
        self.home_made = 0
        self.pwd = self.home
        # Self environ is public
        self.environ = {
            'HOME': self.home,
            'LOGNAME': 'nobody',
            'PWD': self.pwd,
            'TMPDIR': self.home,
            'USER': 'nobody',
            }
        self.path = OSPathSurrogate(self)

    def _path(self, path, writing=0, error=os.error):
        """Convert and check a pathname.

        This method implements the policy of which files an applet
        group is allowed to read or write.

        Current policy:

        - all files are readable except if their name starts with "."
        - only files inside the applet's home directory are writable

        """
        path = os.path.join(self._pwd(), path)
        path = os.path.normpath(path)
        if writing:
            n = len(self.home)
            if not(path[:n] == self.home and path[n:n+1] == os.sep):
                raise error, "can't write outside applet's own directory"
            head, tail = os.path.split(path)
            if tail[:1] == "." and tail not in (os.curdir, os.pardir):
                raise error, "can't write filenames beginning with '.'"
        return path

    def _pwd(self):
        """Return the current working directory, call _home() if necessary."""
        if self.pwd == self.home:
            return self._home()
        return self.pwd

    def _home(self):
        """Make sure self.home exists."""
        if not self.home_made:
            if not os.path.exists(self.home):
                if not os.path.exists(self.appletsdir):
                    os.mkdir(self.appletsdir, 0777)
                os.mkdir(self.home, 0777)
            self.home_made = 1
        return self.home

    # Public, applet visible methods (as functions in module os).
    # IN ALPHABETICAL ORDER, PLEASE!

    def fopen(self, path, mode='r', bufsize=-1):
        """Substitute for __builtin__.open()."""
        path = self._path(path, writing=(mode[:1] != 'r'), error=IOError)
        return open(path, mode, bufsize)

    def getcwd(self):
        return self._pwd()

    def getpid(self):
        """Return a fake pid for tempfile etc.

        Since TMPDIR is set to the applet's home dir anyway, there's
        no need for this to be randomly changing.

        """
        return 666

    def listdir(self, path):
        return os.listdir(self._path(path))

    def unlink(self, path):
        path = self._path(path, 1)
        os.unlink(path)


TEMPLATE1 = """
def %(name)s(self, arg):
    return os.path.%(name)s(arg)
"""
TEMPLATE2 = """
def %(name)s(self, a1, a2):
    return os.path.%(name)s(a1, a2)
"""
TEMPLATE3 = """
def %(name)s(self, path):
    return os.path.%(name)s(self.os._path(path))
"""

class OSPathSurrogate:

    def __init__(self, ossurrogate):
        self.os = ossurrogate

    for name in ('normcase', 'isabs', 'split', 'splitext',
                 'splitdrive', 'basename', 'dirname', 'normpath'):
        exec TEMPLATE1 % {'name': name}

    for name in ('commonprefix', 'samestat'):
        exec TEMPLATE2 % {'name': name}

    def join(self, *args):
        return apply(os.path.join, args)

    for name in ('exists', 'isdir', 'isfile', 'islink', 'ismount'):
        exec TEMPLATE3 % {'name': name}

    def samefile(self, p1, p2):
        return os.path.samefile(self.os._path(p1), self.os._path(p2))

    def walk(self, top, func, arg):
        return os.path.walk(self.os._path(top), func, arg)

    def expanduser(self, path):
        if path[:1] == '~' and path[1:2] == os.sep:
            path = self.os.environ['HOME'] + path[1:]
        return path


def group2dirname(group):
    """Convert an applet group name to an acceptable unique directory name.

    We take up to 15 characters from the group name, truncated in the
    middle if it's longer, and substituting '_' for certain
    characters; then we append 16 hex bytes which are the first 8
    bytes of the MD5 checksum of the original group name.  This
    guarantees sufficient uniqueness, while it's still possible to
    guess which group a particular directory belongs to.  (A log file
    should probably be maintained making the mapping explicit.)

    """
    import regsub, md5
    sum = md5.new(group).digest()
    path = regsub.gsub('[:/\\]+', '_', group)
    if len(path) > 15:
        path = path[:7] + '_' + path[-7:]
    path = path + hexstring(sum[:8])
    return path


def hexstring(s):
    """Convert a string to hex bytes.  Obfuscated for maximum speed."""
    return "%02x"*len(s) % tuple(map(ord, s))
