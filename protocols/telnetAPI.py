"""Telnet protocol handler for URLs of the form telnet://host[:port]

For Unix only; requires xterm in your $PATH.

"""

import os, urllib
from nullAPI import null_access

class telnet_access(null_access):

    def __init__(self, url, method, params):
        null_access.__init__(self, url, method, params)
        host, junk = urllib.splithost(url)
        userpasswd, host = urllib.splituser(host)
        host, port = urllib.splitport(host)
        
        # XXX I tried doing this using os.system(), but the file
        # descriptors that Grail has open seemed to be confusing
        # telnet or xterm.  So we need to close all file descriptors,
        # and this must be done in the child process, so now that
        # we're forking anyway, we might as well use os.exec*.

        # XXX To do: reap child processes after they've died!
        # Use os.waitpid(-1, os.WNOHANG) to do this.
        # But perhaps we should only wait for pids originating in this
        # module.

        cmd = ["xterm", "-e", "telnet", host]
        if port:
            cmd.append(str(port))
        pid = os.fork()
        if pid:
            # Parent process
            return

        # Child process
        try:
            # Close all file descriptors
            # XXX How to know how many there are?
            for i in range(3, 200):
                try:
                    os.close(i)
                except os.error:
                    pass
            # XXX Assume xterm is on $PATH
            os.execvp(cmd[0], cmd)
            # This doesn't return when successful
        except:
            print "Exception in os.execvp() or os.close()"
            # Don't fall back in the the parent's stack!
            os._exit(127)
