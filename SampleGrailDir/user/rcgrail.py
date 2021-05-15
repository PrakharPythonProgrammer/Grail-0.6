#! /usr/bin/env python

# Send a remote control command to Grail.
#
# Example:
#
# You can use this script with Emacs so that clicking on a URL causes
# Grail to load the page instead of W3 or Netscape.  I use this stuff
# in XEmacs 19.13; YMMV if you use a different version.
#
# For VM, use:
# (setq vm-url-browser "~/.grail/user/rcgrail.py")
#
# For GNUS use:
# (defun baw:send-url-to-grail (url)
#   (message "Sending URL to Grail...")
#   (save-excursion
#     (set-buffer (get-buffer-create "*Shell Command Output*"))
#     (erase-buffer)
#     ;; don't worry about this failing...
#     (call-process "~/.grail/user/rcgrail.py" nil 0 nil url)
#     (message "Sending URL to Grail... done")))
#
# (setq gnus-button-url 'baw:send-url-to-grail ; GNUS 5
#       highlight-headers-follow-url-function 'baw:send-url-to-grail) ; GNUS 4


import sys
import getopt
import socket
import tempfile
import os
import regex


# The file structure.  Modeled after X11
RCDIR = '.grail-unix'
GRAILCMD = 'grail'

try:
    FILENAME = os.environ['GRAIL_REMOTE']
except KeyError:
    FILENAME = ''
GRAIL_CMD = '/bin/sh'
GRAIL_ARGS = ('-c', GRAILCMD)

def normalize_display(display):
    # normalize the display name
    cre = regex.compile('\([^:]+\)?:\([0-9]+\)\(\.\([0-9]+\)\)?')
    if cre.match(display):
        host, display, screen = cre.group(1, 2, 4)
        if not host:
            host = socket.gethostname()
        if not screen:
            screen = '0'
        return '%s:%s.%s' % (host, display, screen)

def rc_filename(user=None, display=None):
    tmpdir = tempfile.gettempdir()
    user = os.environ['USER'] or os.environ['LOGNAME']
    if not display:
        display = os.environ['DISPLAY'] or ':0'
    display = normalize_display(display)
    sfile = '%s-%s' % (user, display)
    return os.path.join(tmpdir, os.path.join(RCDIR, sfile))

def usage(progname):
    print 'Usage:', progname, '[-b] [-d display] [-p] [-h] [URI]'
    print '    -b fires up a new browser window'
    print '    -d send URI to Grail on display'
    print '    -p PING only'
    print '    -h prints this message'
    print '    URI is the URI string to tell Grail to load'



def main():
    progname = sys.argv[0]
    filename = FILENAME
    pingonly = None
    #
    # if I have it, try :0.1 first, then :0
    # yeah, this is pretty damn Solaris specific!
    #
    display = None
    if os.path.exists('/dev/fb1'):
        display = socket.gethostname() + ':0.1'
    if not filename:
        filename = rc_filename(display=display)
    cmd = 'LOAD'
    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'bdhp')
        for switch, arg in optlist:
            if switch == '-b' and cmd[-3:] <> 'NEW':
                cmd = cmd + 'NEW'
            elif switch == '-d':
                display = arg
                filename = rc_filename(display=display)
            elif switch == '-h':
                usage(progname)
                sys.exit(0)
            elif switch == '-p':
                pingonly = 1
                cmd = 'PING'
                uri = ''
            else:
                raise getopt.error
        if pingonly:
            pass
        elif not args:
            raise getopt.error
        else:
            uri = args[0]
    except getopt.error:
        usage(progname)
        sys.exit(-1)
    if not os.path.exists(filename):
        # No Grail started yet, try starting it up...
        if os.fork() == 0:
            os.environ['DISPLAY'] = display or ':0'
            os.execvpe(GRAIL_CMD, GRAIL_ARGS + (uri,), os.environ)
        else:
            sys.exit(0)
    # calculate the command
    cmd = cmd + ' ' + uri
    # now do the remote connection and command
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(filename)
        s.send(cmd)
        if pingonly:
            data = s.recv(1024)
            print "Grail's response: `%s'" % data
        s.close()
    except socket.error:
        print 'rcgrail: unable to communicate with Grail'
        sys.exit(1)

main()
