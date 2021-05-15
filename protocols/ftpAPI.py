"""FTP interface using the new protocol API.

XXX Main deficiencies:

- poll*() always returns ready
- should read the headers more carefully (no blocking)
- (could even *write* the headers more carefully)
- should poll the connection making part too
- no GC of ftp cache entries
- should reuse ftp cache entries for same server by using cdup/cd
- if a file retrieval returns error 550 it is retried as directory listing

"""


import string
import regex
import regsub

import ftplib
from urllib import unquote, splithost, splitport, splituser, \
     splitpasswd, splitattr, splitvalue, quote
from urlparse import urljoin
import mimetools
from Assert import Assert
import grailutil
import socket

app = grailutil.get_grailapp()          # app.guess_type(url)


# Stages
META = 'META'
DATA = 'DATA'
EOF = 'EOF'
DONE = 'DONE'


LISTING_HEADER = """<HTML>
<HEAD><TITLE>FTP Directory: %(url)s</TITLE></HEAD>
<BODY>
<H1>FTP Directory: %(url)s</H1>
<PRE>"""

LISTING_TRAILER = """</PRE>
</BODY>
"""

# pattern catches file names with embedded spaces and correctly chops
# off symbolic links.  assumption is anything after `yyyy' or `hh:mm'
# field and before optional `-> symlink' field is the name of the file
LISTING_PATTERN = (
    "^\("                               # group 1
        "[-a-z]"                        # file type
        "[-a-z][-a-z][-a-z]"            # owner rwx
        "[-a-z][-a-z][-a-z]"            # group rwx
        "[-a-z][-a-z][-a-z]"            # world rwx
    "\)"                                # end group 1
    "\("                                # group 2
        "[ \t]+.*[ \t]+"                # links, owner, grp, sz, mnth, day
        "[0-9][0-9]:?[0-9][0-9]"        # year or hh:mm
        "[ \t]+"                        # spaces
    "\)"                                # end group 2
    "\("                                # group 3
        "\([^-]\|-[^>]\)+"              # lots of chars, but not symlink
    "\)"                                # end group 3
    "\("                                # optional group 5
        "[ \t]+->.*"                    # spaces followed by symlink 
    "\)?"                               # end optional group 5
    "$"                                 # end of string
    )


ftpcache = {}                           # XXX Ouch!  A global!


class ftp_access:

    def __init__(self, url, method, params):
        Assert(method == 'GET')
        netloc, path = splithost(url)
        if not netloc: raise IOError, ('ftp error', 'no host given')
        host, port = splitport(netloc)
        user, host = splituser(host)
        if user: user, passwd = splitpasswd(user)
        else: passwd = None
        host = socket.gethostbyname(host)
        if port:
            try:
                port = string.atoi(port)
            except string.atoi_error:
                raise IOError, ('ftp error', 'bad port')
        else:
            port = ftplib.FTP_PORT
        path, attrs = splitattr(path)
        self.url = "ftp://%s%s" % (netloc, path)
        dirs = string.splitfields(path, '/')
        dirs, file = dirs[:-1], dirs[-1]
        self.content_length = None
        if not file:
            self.content_type, self.content_encoding = None, None
            type = 'd'
        else:
            self.content_type, self.content_encoding = app.guess_type(file)
            if self.content_encoding:
                type = 'i'
            elif self.content_type and self.content_type[:5] == 'text/':
                type = 'a'
            elif file[-1] == '/':
                type = 'd'
            else:
                type = 'i'
        if dirs and not dirs[0]: dirs = dirs[1:]
        key = (user, host, port, string.joinfields(dirs, '/'))
        self.debuglevel = None
        try:
            if not ftpcache.has_key(key):
                ftpcache[key] = []
            for attr in attrs:
                [attr, value] = map(string.lower, splitvalue(attr))
                if attr == 'type' and value in ('a', 'i', 'd'):
                    type = value
                elif attr == 'debug':
                    try:
                        self.debuglevel = string.atoi(value)
                    except string.atoi_error:
                        pass
            candidates = ftpcache[key]
            for cand in candidates:
                if not cand.busy():
                    break
            else:
                cand = ftpwrapper(user, passwd,
                                  host, port, dirs, self.debuglevel)
                candidates.append(cand)
            # XXX Ought to clean the cache every once in a while
            self.cand = cand
            self.sock, self.isdir = cand.retrfile(file, type)
            self.content_length = cand.content_length
        except ftplib.all_errors, msg:
            raise IOError, ('ftp error', msg)
        self.state = META

    def pollmeta(self):
        Assert(self.state == META)
        return "Ready", 1

    def getmeta(self):
        Assert(self.state == META)
        self.state = DATA
        headers = {}
        if self.isdir:
            if self.url and self.url[-1:] != '/':
                self.url = self.url + '/'
            self.content_type = 'text/html'
            self.content_encoding = None
        if self.content_type:
            headers['content-type'] = self.content_type
        if self.content_encoding:
            headers['content-encoding'] = self.content_encoding
        if self.content_length:
            headers['content-length'] = `self.content_length`
        self.lines = []                 # Only used of self.isdir
        return 200, "OK", headers

    def polldata(self):
        Assert(self.state in (EOF, DATA))
        return "Ready", 1

    def getdata(self, maxbytes):
        if self.state == EOF:
            self.state = DONE
            return ""
        Assert(self.state == DATA)
        data = self.sock.recv(maxbytes)
        if self.debuglevel > 4: print "*data*", `data`
        if not data:
            self.state = DONE
        if self.isdir:
            self.addlistingdata(data)
            data = self.getlistingdata()
            if self.state == DONE and data:
                self.state = EOF        # Allow one more call
        return data

    def addlistingdata(self, data):
        if not data:
            if self.lines:
                while self.lines and self.lines[-1] == "":
                    del self.lines[-1]
                self.lines.append(None) # Mark the end
        else:
            lines = string.splitfields(data, '\n')
            if self.debuglevel > 3:
                for line in lines: print "*addl*", `line`
            if self.lines:
                lines[0] = self.lines[-1] + lines[0]
                self.lines[-1:] = lines
            else:
                lines.insert(0, None)   # Mark the start
                self.lines = lines

    def getlistingdata(self):
        if not self.lines:
            return ""
        lines, self.lines = self.lines[:-1], self.lines[-1:]
        data = ""
        prog = regex.compile(self.listing_pattern)
        for line in lines:
            if self.debuglevel > 2:
                print "*getl*", `line`
            if line is None:
                data = data + self.listing_header % {'url':
                                                     self.escape(self.url)}
                continue
            if line[-1:] == '\r': line = line[:-1]
            if prog.match(line) < 0:
                line = self.escape(line) + '\n'
                data = data + line
                continue
            mode, middle, name, symlink = prog.group(1, 2, 3, 5)
            rawname = name
            [mode, middle, name] = map(self.escape, [mode, middle, name])
            href = urljoin(self.url, quote(rawname))
            if len(mode) == 10 and mode[0] == 'd' or name[-1:] == '/':
                if name[-1:] != '/':
                    name = name + '/'
                if href[-1:] != '/':
                    href = href + '/'
            line = '%s%s<A HREF="%s">%s</A>%s\n' % (
                mode, middle, self.escape(href), name,
                (symlink and symlink or ''))
            data = data + line
        if self.lines == [None]:
            data = data + self.listing_trailer
            self.lines = []
        return data

    listing_header = LISTING_HEADER
    listing_trailer = LISTING_TRAILER
    listing_pattern = LISTING_PATTERN

    def escape(self, s):
        if not s: return ""
        s = regsub.gsub('&', '&amp;', s) # Must be done first
        s = regsub.gsub('<', '&lt;', s)
        s = regsub.gsub('>', '&gt;', s)
        return s

    def fileno(self):
        return self.sock.fileno()

    def close(self):
        sock = self.sock
        cand = self.cand
        self.sock = None
        self.cand = None
        if sock:
            sock.close()
        if cand:
            cand.done()


class ftpwrapper:

    """Helper class for cache of open FTP connections"""

    def __init__(self, user, passwd, host, port, dirs, debuglevel=None):
        self.user = unquote(user or '')
        self.passwd = unquote(passwd or '')
        self.host = host
        self.port = port
        self.dirs = []
        self.content_length = None
        for dir in dirs:
            self.dirs.append(unquote(dir))
        self.debuglevel = debuglevel
        self.reset()

    def __del__(self):
        self.done()
        self.ftp.quit()

    def reset(self):
        self.conn = None
        self.ftp = GrailFTP()
        if self.debuglevel is not None:
            self.ftp.set_debuglevel(self.debuglevel)
        self.ftp.connect(self.host, self.port)
        self.ftp.login(self.user, self.passwd)
        for dir in self.dirs:
            self.ftp.cwd(dir)

    def busy(self):
        return self.conn and 1

    def done(self):
        conn = self.conn
        self.conn = None
        if conn:
            conn.close()
            try:
                self.ftp.voidresp()
            except ftplib.all_errors:
                print "[ftp.voidresp() failed]"

    def retrfile(self, file, type):
        if type == 'd': cmd = 'TYPE A'; isdir = 1
        else: cmd = 'TYPE ' + string.upper(type); isdir = 0
        try:
            self.ftp.voidcmd(cmd)
        except ftplib.all_errors:
            self.reset()
            self.ftp.voidcmd(cmd)
        conn = None
        if file and not isdir:
            try:
                cmd = 'RETR ' + unquote(file)
                conn = self.ftp.transfercmd(cmd)
            except ftplib.error_perm, reason:
                if reason[:3] != '550':
                    raise IOError, ('ftp error', reason)
            else:
                self.content_length = self.ftp._xfer_size
        if not conn:
            # Try a directory listing
            isdir = 1
            if file: cmd = 'LIST ' + file
            else: cmd = 'LIST'
            conn = self.ftp.transfercmd(cmd)
        self.conn = conn
        return conn, isdir


class GrailFTP(ftplib.FTP):
    #
    #  Hackish subclass of ftplib.FTP to allow the transfer size to be
    #  available for the creation of a content-length header.
    #
    import regex
    _size_re = regex.compile("(\([0-9][0-9]*\) bytes)", regex.casefold)

    _xfer_size = None

    def getresp(self):
        resp = ftplib.FTP.getresp(self)
        if len(resp) >= 3 and resp[:3] == "150" \
           and self._size_re.search(resp) >= 0:
                self._xfer_size = string.atoi(self._size_re.group(1))
        return resp


# To test this, use ProtocolAPI.test()
