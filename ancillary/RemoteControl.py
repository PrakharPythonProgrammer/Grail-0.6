"""Remote control of Grail.

NOTE NOTE NOTE: See <http://monty.cnri.reston.va.us/grail-0.3/help/rc.html>
for details on this interface.

On Unix systems with the DISPLAY environment variable set, the socket
file name will typically be /tmp/.grail-unix/$USER-$DISPLAY, and the
directory will be protected with mode 0700.  The DISPLAY value will be
normalized to `socket.gethostname():<DISPNUM>.<SCREENNUM>'.

You can also define what file to use by setting the environment
variable GRAIL_REMOTE.  TBD: this should also be made a preference.

This module essentially opens the socket and registers it with Tk so
when data is readable on it, registered callbacks are executed.  This
is a really simple minded string based protocol, with a synchronous
server model.  Commands are limited to 1024 bytes.

TBD: Port this to non-Unix systems, use CCI and ILU.

Exported functions:

start()
        starts the remote controller

stop()
        stops the remote controller

register(cmdstr, callback)
        registers a callback function for handling cmdstr commands.
        The callback has the following form:

        callback(cmdstr, cmdargs)

        where cmdargs is the remainder of the string read from the
        socket.  Note that you can register more than one callback for
        a particular command string; they are invoked in the order
        they were registered.

unregister(cmdstr, callback=None)
        unregisters the callback for the given command string.  If
        callback is not specified, all callbacks for the cmdstr are
        unregistered.

register_loads()
        registers a callback for the command string 'LOAD' which loads
        a given URL into the latest browser window.  The URL to load
        is the cmdargs for the command.  This also registers the
        'LOADNEW' command string which pops up a new browser and loads
        the URL into that browser window.

unregister_loads()
        unregisters the built-in LOAD and LOADNEW callbacks.


Exported exceptions:

InitError       - the socket couldn't be initialized
ClashError      - another Grail is already being remote controlled
BadCommandError - a badly formatted command was received
NoHandlerError  - no handler for the received command has been registered


Example (put this in your grailrc.py file):

# Turn on remote control.  Ignore error that get's raised if some
# other Grail is being remote controlled.
import RemoteControl
RemoteControl.register_loads()
try:
    RemoteControl.start()
except RemoteControl.ClashError:
    pass

"""


# errors
InitError = 'RemoteControl.InitError'
ClashError = 'RemoteControl.ClashError'
BadCommandError = 'RemoteControl.BadCommandError'
NoHandlerError = 'RemoteControl.NoHandlerError'

_controller = None
_filename = None
_loads_registered = None

def _create():
    global _controller
    if not _controller:
        _controller = Controller()

def start():
    _create()
    _controller.start()

def stop():
    if _controller:
        _controller.stop()

def register(cmdstr, callback):
    _create()
    _controller.register(cmdstr, callback)

def unregister(cmdstr, callback):
    _create()
    _controller.unregister(cmdstr, callback)

def register_loads():
    _create()
    global _loads_registered
    if not _loads_registered:
        _controller.register('LOAD', _controller.load_cmd)
        _controller.register('LOADNEW', _controller.load_new_cmd)
        _loads_registered = 1

def unregister_loads():
    global _loads_registered
    if _loads_registered:
        _controller.unregister('LOAD', _controller.load_cmd)
        _controller.unregister('LOADNEW', _controller.load_new_cmd)
        _loads_registered = None



import tempfile
import os
import socket
import regex
import string
from Tkinter import tkinter
from grailutil import *

# The file structure.  Modeled after X11
_filename = getenv('GRAIL_REMOTE')
if not _filename:
    TMPDIR = tempfile.gettempdir()
    USER = getenv('USER') or getenv('LOGNAME')
    XDISPLAY = getenv('DISPLAY') or ':0'
    # normalize the display name
    cre = regex.compile('\([^:]+\)?:\([0-9]+\)\(\.\([0-9]+\)\)?')
    if cre.match(XDISPLAY):
        host, display, screen = cre.group(1, 2, 4)
        if not host:
            host = socket.gethostname()
        if not screen:
            screen = '0'
        XDISPLAY = '%s:%s.%s' % (host, display, screen)
    _filename = os.path.join(TMPDIR,
                             os.path.join('.grail-unix',
                                          '%s-%s' % (USER, XDISPLAY)))


class Controller:
    def __init__(self, path=_filename):
        # register a destruction handler with the Grail Application object
        app = get_grailapp()
        self._app = app
        app.register_on_exit(self._close)
        # calculate the socket's filename
        self._path = path
        self._fileno = None
        self._socket = None
        self._enabled = None
        # Don't create the socket now, because we want to allow
        # clients of this class to register callbacks for commands
        # first.
        self._cbdict = {}
        self._cmdre = regex.compile('\([^ \t]+\)\(.*\)')

    def start(self):
        """Begin listening for remote control commands."""
        # initialize the socket
        if self._fileno is None:
            # for security, create the file structure
            head, self._filename = os.path.split(self._path)
            dirhier = []
            while head and not os.path.isdir(head):
                head, t = os.path.split(head)
                dirhier.insert(0, t)
            for dir in dirhier:
                head = os.path.join(head, dir)
                os.mkdir(head, 0700)
            self._filename = self._path
            # TBD: What do we do with multiple Grail processes?  Which
            # one do we remote control?
            if os.path.exists(self._filename):
                # first make sure that the socket is connected to a
                # live Grail process.  E.g. if Python core dumped, the
                # exit handler won't run so you'd be dead in the
                # water.
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    s.connect(self._filename)
                    s.send('PING NOACK')
                    s.close()
                    raise ClashError
                except socket.error, (errno, msg):
                    os.unlink(self._filename)
                    s.close()
            # create the FIFO object
            s = self._socket = socket.socket(socket.AF_UNIX,
                                             socket.SOCK_STREAM)
            s.bind(self._filename)
            s.listen(1)
            # register with Tk
            self._fileno = s.fileno()
            if self._fileno < 0:
                self._fileno = None
                raise InitError
        if not self._enabled:
            self._enabled = 1
            tkinter.createfilehandler(
                self._fileno, tkinter.READABLE, self._dispatch)
            self.register('PING', self.ping_cmd)

    def stop(self):
        """Stop listening for remote control commands."""
        if self._enabled:
            self._enabled = None
            tkinter.deletefilehandler(self._fileno)

    def register(self, cmdstr, callback):
        """Register command string, callback function pairs.

        Command format is 'CMDSTR ARGS' where CMDSTR is some command
        string as defined by the client of this class.  ARGS is
        anything that follows, and is command specific.

        Format of the callback method is: callback(cmdstr, argstr).
        More than one callback can be defined for a command, and they
        are called in the order they are registered in.  Note that any
        exceptions raised in the callback are passed straight up
        through to Grail.
        """
        if self._cbdict.has_key(cmdstr):
            cblist = self._cbdict[cmdstr]
            cblist.append(callback)
        else:
            self._cbdict[cmdstr] = [callback]

    def unregister(self, cmdstr, callback=None):
        """Unregister a command string, callback mapping.

        If callback is None (the default), this unregisters all
        callbacks associated with a command.
        """
        if self._cbdict.has_key(cmdstr):
            cblist = self._cbdict[cmdstr]
            if callback and callback in cblist:
                cblist.remove(callback)
            else:
                del self._cbdict[cmdstr]

    # private methods

    def _close(self):
        self.stop()
        if self._filename:
            try:
                os.unlink(self._filename)
            except os.error:
                pass

    def _dispatch(self, *args):
        conn, addr = self._socket.accept()
        rawdata = conn.recv(1024)
        # strip off the command string
        string.strip(rawdata)
        if self._cmdre.match(rawdata) < 0:
            print 'Remote Control: Ignoring badly formatted command:', rawdata
            return
        # extract the command and args strings
        command = string.strip(self._cmdre.group(1))
        argstr = string.strip(self._cmdre.group(2))
        # look up the command string
        if not self._cbdict.has_key(command):
            print 'Remote Control: Ignoring unrecognized command:', command
            return
        cblist = self._cbdict[command]
        # call all callbacks in list
        for cb in cblist:
            cb(command, argstr, conn)

    # convenience methods

    def _do_load(self, uri, in_new_window=None):
        target = ""
        def _new_browser(b):
            from Browser import Browser
            return Browser(b.master)

        if " " in uri:
            [uri, target] = string.split(uri)

        browsers = self._app.browsers[:]
        if not len(browsers):
            return

        b = None
        if not in_new_window:
            browsers.reverse()
            # find the last browser who's context is not showing
            # source
            for b in browsers:
                if not b.context.show_source:
                    break
            else:
                b = None
        if not b:
            b = _new_browser(browsers[-1])
        b.context.load(uri, target=target)

    def load_cmd(self, cmdstr, argstr, conn):
        self._do_load(argstr)

    def load_new_cmd(self, cmdstr, argstr, conn):
        self._do_load(argstr, in_new_window=1)

    def ping_cmd(self, cmdstr, argstr, conn):
        try:
            if argstr <> 'NOACK':
                conn.send('ACK')
        except socket.error:
            print 'RemoteControl: unable to acknowledge PING'
