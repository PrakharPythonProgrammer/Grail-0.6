from Assert import Assert
import grailutil
import ht_time
import os

from stat import ST_MTIME, ST_SIZE


META, DATA, DONE = 'META', 'DATA', 'DONE'

LISTING_HEADER = """<HTML>
<HEAD>
<TITLE>Local Directory: %(url)s</TITLE>
</HEAD>
<BODY>
<H1>Local Directory: %(pathname)s</H1>
<PRE>"""

LISTING_TRAILER = """</PRE>
</BODY>
"""

LISTING_PATTERN = """\
^\([-a-z][-a-z][-a-z][-a-z][-a-z][-a-z][-a-z][-a-z][-a-z][-a-z]\)\
\([ \t]+.*[ \t]+\)\([^ \t]+\)$"""

class file_access:

    def __init__(self, url, method, params):
        from urllib import url2pathname, pathname2url
        self.url = url
        self.redirect = None
        pathname = url2pathname(url)
        if not os.path.isabs(pathname):
            try:
                pwd = os.getcwd()
            except os.error:
                pass
            else:
                pathname = os.path.expanduser(pathname)
                pathname = os.path.join(pwd, pathname)
                pathname = os.path.normpath(pathname)
                self.redirect = 1
        self.pathname = pathname
        self.url = "file:" + pathname2url(pathname)
        self.method = method
        self.params = params
        self.headers = {}
        try:
            stats = os.stat(self.pathname)
        except (IOError, os.error, AttributeError):
            pass
        else:
            self.headers['content-length'] = str(stats[ST_SIZE])
            self.headers['last-modified'] = ht_time.unparse(stats[ST_MTIME])
        if os.path.isdir(self.pathname):
            self.format_directory()
        else:
            self.fp = open(self.pathname, 'rb') # May raise IOError!
            app = grailutil.get_grailapp()
            ctype, cencoding = app.guess_type(self.pathname)
            if ctype: self.headers['content-type'] = ctype
            if cencoding: self.headers['content-encoding'] = cencoding
        self.state = META

    def pollmeta(self):
        Assert(self.state == META)
        return "Ready", 1

    def getmeta(self):
        Assert(self.state == META)
        self.state = DATA
        if self.redirect:
            return 301, "Redirect to absolute pathname", {"location": self.url}
        return 200, "OK", self.headers

    def polldata(self):
        Assert(self.state == DATA)
        return "Ready", 1

    def getdata(self, maxbytes):
        Assert(self.state == DATA)
        data = self.fp.read(maxbytes)
        if not data:
            self.state = DONE
        return data
        
    def fileno(self):
        # TODO - Fix sockets under Windows.
        # We fall back to the polling method of ansyc I/O automatically
        # for http requests under windows because dup fails for socket
        # objects and returns -1 to BaseReader which kicks in the
        # checkapi_regularly form of async I/O (Which is a hack, but it
        # works :-) For file URLs however, unfortunately the following
        # small hack is necessary to force the use of checkapi_regularly.
        # This is all because the current version of sockets for winnt
        # (Sam Rushings sockets-09-5) *does* support dups for files,
        # returning a valid new descriptor which, when passed to select,
        # mysteriously causes the select to block :-( -rmasse
        if os.name == 'nt':
            return -1
        try:
            return self.fp.fileno()
        except AttributeError:
            return -1

    def close(self):
        fp = self.fp
        self.fp = None
        if fp:
            fp.close()

    def format_directory(self):
        # XXX Unixism
        if self.url and self.url[-1] != '/':
            self.url = self.url + '/'
        fp = os.popen("ls -l -a %s/. 2>&1" % self.pathname, "r")
        lines = fp.readlines()
        fp.close()
        import StringIO
        import regex
        from urllib import quote
        from urlparse import urljoin
        import regsub
        def escape(s, regsub=regsub):
            if not s: return ""
            s = regsub.gsub('&', '&amp;', s) # Must be done first
            s = regsub.gsub('<', '&lt;', s)
            s = regsub.gsub('>', '&gt;', s)
            return s
        prog = regex.compile(self.listing_pattern)
        data = self.listing_header % {'url': self.url,
                                      'pathname': escape(self.pathname)}
        for line in lines:
            if line[-1] == '\n': line = line[:-1]
            if prog.match(line) < 0:
                line = escape(line) + '\n'
                data = data + line
                continue
            mode, middle, name = prog.group(1, 2, 3)
            rawname = name
            [mode, middle, name] = map(escape, [mode, middle, name])
            href = urljoin(self.url, quote(rawname))
            if len(mode) == 10 and mode[0] == 'd' or name[-1:] == '/':
                if name[-1:] != '/':
                    name = name + '/'
                if href[-1:] != '/':
                    href = href + '/'
            line = '%s%s<A HREF="%s">%s</A>\n' % (
                mode, middle, escape(href), name)
            data = data + line
        data = data + self.listing_trailer
        self.fp = StringIO.StringIO(data)
        self.headers['content-type'] = 'text/html'
        self.headers['content-length'] = str(len(data))

    listing_header = LISTING_HEADER
    listing_trailer = LISTING_TRAILER
    listing_pattern = LISTING_PATTERN
