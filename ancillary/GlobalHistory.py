"""Global History.

The Global History is a record of every URL you've visited.  It's used
primarily to decide how to color links in the Browser windows, and to
maintain this history in a file.  It knows how to find and read
Netscape 1.x history files, as well as Grail 0.x history files.
Netscape 2.x history files are not parsable ASCII text (they're db
files), which probably makes long-term sense for Grail as well, but
aren't currently supported.

There is only one GlobalHistory object per Application object, which
is where you'll find it.  The Context object inserts new entries into
the Global History, while GrailHTMLParser objects query the history.

TBD:

        1) Read Netscape 2 history files
        2) Use db to manage the on-disk history mechanism

"""

import os
import regex
import string
import sys
import time
from grailutil import *

GRAIL_RE = regex.compile('\([^ \t]+\)[ \t]+\([^ \t]+\)[ \t]+?\(.*\)?')
DEFAULT_NETSCAPE_HIST_FILE = os.path.join(gethome(), '.netscape-history')
DEFAULT_GRAIL_HIST_FILE = os.path.join(getgraildir(), 'grail-history')

# TBD: this should be an option.
# An expiration of zero means no expiration
GLOBAL_HISTORY_EXPIRATION_DAYS = 0
EXPIRATION_SECS = GLOBAL_HISTORY_EXPIRATION_DAYS * 60 * 60 * 24


def now():
    return int(time.time() % (1L<<31))



class HistoryLineReader:
    def _error(self, line):
        sys.stderr.write('WARNING: ignoring ill-formed history file line:\n')
        sys.stderr.write('WARNING: %s\n' % line)

class NetscapeHistoryReader(HistoryLineReader):
    def parse_line(self, line):
        try:
            fields = string.splitfields(line, '\t')
            url = string.strip(fields[0])
            timestamp = string.atoi(string.strip(fields[1]))
            return (url, '', timestamp or now())
        except (ValueError, IndexError, TypeError):
            self._error(line)
            return None

class GrailHistoryReader(HistoryLineReader):
    def parse_line(self, line):
        url = timestamp = title = ''
        try:
            if GRAIL_RE.match(line) >= 0:
                url, ts, title = GRAIL_RE.group(1, 2, 3)
                timestamp = string.atoi(string.strip(ts))
                return url, title, timestamp or now()
        except (ValueError, TypeError):
            self._error(line)
            return None

class HistoryReader:
    def read_file(self, fp, histobj):
        pass
        # read the first line, to determine what type of history file
        # we're looking at
        ghist = []
        line = fp.readline()
        if regex.match('GRAIL-global-history-file-1', line) >= 0:
            linereader = GrailHistoryReader()
        elif regex.match('MCOM-Global-history-file-1', line) >= 0:
            linereader = NetscapeHistoryReader()
        else:
            return
        while line:
            line = fp.readline()
            if line:
                infonode = linereader.parse_line(line)
                if infonode:
                    ghist.append(infonode)
        # now mass update the history object
        histobj.mass_append(ghist)



class GlobalHistory:
    """Global History simply remembers URLs, knows how to read and
    write history files, and can be queried to see if a particular URL
    is on the history.

    Public Interface:

        remember_url(url, title='')
                Adds the URL to the GlobalHistory and, if TITLE is
                provided, associates this TITLE with the URL.  Any
                previous TITLE associated with the URL is discarded.

        lookup_url(url)
                If the URL is on the GlobalHistory, this returns a
                tuple of the form: (TITLE, TIMESTAMP) where TITLE is a
                string previous associated with remember_url(), and
                TIMESTAMP is an seconds integer.  If the URL is not on
                the GlobalHistory, the tuple (None, None) is returned.

        inhistory_p(url)
                Returns true if the URL is in the Global History,
                otherwise false.

        urls()
                Return a list, in order of all URLs on the GlobalHistory.
    """
    def __init__(self, app, readonly=0):
        self._app = app
        self._urlmap = {}               # for fast lookup
        self._history = []              # to maintain order
        # first try to load the Grail global history file
        fp = None
        try:
            try: fp = open(DEFAULT_GRAIL_HIST_FILE)
            except IOError:
                try: fp = open(DEFAULT_NETSCAPE_HIST_FILE)
                except IOError: pass
            if fp:
                HistoryReader().read_file(fp, self)
        finally:
            if fp: fp.close()
        if not readonly:
            app.register_on_exit(self.on_app_exit)

    def mass_append(self, histlist):
        histlist.reverse()
        for url, title, timestamp in histlist:
            self._urlmap[url] = (title, timestamp)
            self._history.append(url)

    def remember_url(self, url, title=''):
        if not self._urlmap.has_key(url):
            self._history.append(url)
        elif not title:
            title, oldts = self._urlmap[url]
        self._urlmap[url] = (title, now())
        # Debugging...
#       print 'remember_url:', url, self._urlmap[url]

    def set_title(self, url, title):
        if self._urlmap.has_key(url):
            old_title, when = self._urlmap[url]
        else:
            when = now()
        self._urlmap[url] = (title, when)

    def lookup_url(self, url):
        if self._urlmap.has_key(url): return self._urlmap[url]
        else: return None, None

    def inhistory_p(self, url):
        return self._urlmap.has_key(url)

    def urls(self):
        return self._history[:]

    def on_app_exit(self):
        stdout = sys.stdout
        try:
            fp = open(DEFAULT_GRAIL_HIST_FILE, 'w')
            sys.stdout = fp
            print 'GRAIL-global-history-file-1'
            urls = self.urls()
            urls.reverse()
            expiration = EXPIRATION_SECS and (now() - EXPIRATION_SECS)
            for url in urls:
                title, timestamp = self._urlmap[url]
                # weed out expired links
                if expiration and expiration > timestamp:
                    continue
                if not title or title == url:
                    print '%s\t%d' % (url, timestamp)
                else:
                    print '%s\t%d\t%s' % (url, timestamp, title)
        finally:
            sys.stdout = stdout
            fp.close()
        self._app.unregister_on_exit(self.on_app_exit)
