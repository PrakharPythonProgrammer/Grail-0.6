"""User interface for mailto: handling.

This implementation supports the extended mailto: url scheme described in
ftp://ds.internic.net/internet-drafts/draft-hoffman-mailto-url-01.txt.  This
document is a work in progress, but reflects a generalization of common
practice in Web user agents.

This class is separated out from the protocols.mailtoAPI module to allow
user-defined handling of the mailto: scheme to subclass this dialog.
"""
__version__ = '$Revision: 2.5 $'

import cgi
import grailutil
import os
import rfc822
import string
import time
import tktools

from Tkinter import *
from urlparse import urlparse, urlunparse
from __main__ import GRAILVERSION
from Context import LAST_CONTEXT


COMMON_HEADERS = (
    (0, "to"),
    (1, "subject"),
    (3, "mime-version"),
    (4, "content-type"),
    (5, "content-transfer-encoding"),
    (20, "x-mailer"),
    (21, "x-url"),
    )

if os.sys.platform[:3] == 'sco': 
    # Use MMDF instead of sendmail
    SENDMAIL = "/usr/mmdf/bin/submit -mtlrxto,cc\'*\'s"
    # submit needs a Date: field or it will not include it
    COMMON_HEADERS = tuple(map(None, COMMON_HEADERS) + [(2, "date")])
    TEMPLATE ="""\
To: %(to)s
Date: %(date)s
Subject: %(subject)s
MIME-Version: 1.0
Content-Type: %(ctype)s
X-Mailer: %(mailer)s
X-URL: %(url)s
"""
else:
    SENDMAIL = "/usr/lib/sendmail -t" # XXX
    TEMPLATE ="""\
To: %(to)s
Subject: %(subject)s
MIME-Version: 1.0
Content-Type: %(ctype)s
X-Mailer: %(mailer)s
X-URL: %(url)s
"""

DISALLOWED_HEADERS = ['from', 'appearantly-to', 'bcc', 'content-length',
                      'content-type', 'mime-version', 'to',
                      'content-transfer-encoding', 'x-mailer', 'x-url']


class MailDialog:

    template = TEMPLATE

    def __init__(self, master, address, data):
        # query semantics may be used to identify header field values
        scheme, netloc, path, params, query, fragment = urlparse(address)
        address = urlunparse((scheme, netloc, path, '', '', ''))
        headers = cgi.parse_qs(query)
        # create widgets
        self.master = master
        self.root = tktools.make_toplevel(self.master,
                                          title="Mail Dialog")
        self.root.protocol("WM_DELETE_WINDOW", self.cancel_command)
        self.root.bind("<Alt-w>", self.cancel_command)
        self.root.bind("<Alt-W>", self.cancel_command)
        fr, top, botframe = tktools.make_double_frame(self.root)
        self.text, fr = tktools.make_text_box(top, 80, 24)
        self.text.tag_config('SUSPICIOUS_HEADER', foreground='red')
        self.send_button = Button(botframe,
                                  text="Send",
                                  command=self.send_command)
        self.send_button.pack(side=LEFT)
        self.cancel_button = Button(botframe,
                                    text="Cancel",
                                    command=self.cancel_command)
        self.cancel_button.pack(side=RIGHT)
        tktools.unify_button_widths(self.send_button, self.cancel_button)
        hinfo = _make_sequence_dict(COMMON_HEADERS)
        variables = {
            'to':       address,
            'subject':  data and 'Form posted from Grail' or '',
            'mime-version': '1.0',
            'x-mailer': GRAILVERSION,
            'x-url':    LAST_CONTEXT and LAST_CONTEXT.get_baseurl() or ''
            }
        if data:
            variables["content-type"] = "application/x-www-form-urlencoded"
        else:
            variables["content-type"] = "text/plain; charset=us-ascii"
            variables["content-transfer-encoding"] = "7bit"
        # move default set of query'd headers into variables
        for header, vlist in headers.items():
            header = string.lower(header)
            if header != 'body':
                if header not in DISALLOWED_HEADERS:
                    variables[header] = vlist[0]        # toss duplicates
                    if not hinfo.has_key(header):
                        hinfo[header] = 15
                del headers[header]
        # insert user-specified extra headers
        variables = self.add_user_headers(variables)
        for header in variables.keys():
            if not hinfo.has_key(header):
                hinfo[header] = 19
        # write the headers into the buffer
        variables['date'] = time.ctime(time.time())
        hseq = _make_dict_sequence(hinfo)
        for x, header in hseq:
            if variables.has_key(header):
                s = "%s: %s\n" \
                    % (string.capwords(header, '-'), variables[header])
                self.text.insert(END, s)
        # insert newline
        self.text.insert(END, '\n', ())
        # insert data
        if data:
            self.text.insert(END, data)
        elif headers.has_key('body'):
            self.text.insert(END, headers['body'][0] + '\n')
        else:
            self.add_user_signature()
        self.text.focus_set()

    def add_user_headers(self, variables):
        # stuff already in `variables' overrides stuff from the file
        headers = self.load_user_headers()
        headers.update(variables)
        return headers

    def add_user_signature(self):
        fn = os.path.join(grailutil.getgraildir(), "mail-signature")
        if os.path.isfile(fn):
            index = self.text.index('end - 1 char')
            self.text.insert(END, open(fn).read())
            self.text.mark_set('insert', index)

    def load_user_headers(self):
        fn = os.path.join(grailutil.getgraildir(), "mail-headers")
        d = {}
        if os.path.isfile(fn):
            msg = rfc822.Message(open(fn))
            for k, v in msg.items():
                d[k] = v
        return d

    def send_command(self):
        message = self.text.get("1.0", END)
        if message:
            self.root['cursor'] = 'watch'
            self.text['cursor'] = 'watch'
            self.root.update_idletasks()
            if message[-1] != '\n': message = message + '\n'
            p = os.popen(SENDMAIL, 'w')
            p.write(message)
            sts = p.close()
            if sts:
                print "*** Sendmail exit status", sts, "***"
        self.root.destroy()

    def cancel_command(self, event=None):
        self.root.destroy()


def _make_sequence_dict(seq):
    dict = {}
    for v, k in seq:
        dict[k] = v
    return dict

def _make_dict_sequence(dict):
    stuff = []
    for k, v in dict.items():
        stuff.append((v, k))
    stuff.sort()
    return stuff
