from Tkinter import Entry
from grailutil import extract_keyword
import string
import urllib

ATTRIBUTES_AS_KEYWORDS = 1

def do_isindex(parser, attrs):
    prompt = extract_keyword(
        'prompt', attrs,
        "This is a searchable index. Enter search keywords:")
    IndexWidget(parser, prompt,
                (extract_keyword('href', attrs)
                 or extract_keyword('action', attrs)
                 or parser.context.get_baseurl()))


class IndexWidget:

    def __init__(self, parser, prompt, url):
        self.query_url = string.joinfields(string.split(url), '')
        formatter = parser.formatter
        viewer = parser.viewer
        self.context = viewer.context
        self.w = Entry(viewer.text,
                       highlightbackground=viewer.text["background"])
        self.w.bind('<Return>', self.submit)
        formatter.add_hor_rule()
        formatter.add_flowing_data(prompt)
        formatter.add_literal_data('  ')
        parser.add_subwindow(self.w)
        formatter.add_line_break()
        formatter.add_hor_rule()

    def submit(self, event):
        data = self.w.get()
        url = self.query_url or self.context.get_baseurl()
        i = string.find(url, '?')
        if i >= 0:
            url = url[:i]
        url = url + '?' + quote(data)
        self.context.load(url)

def quote(s):
    w = string.splitfields(s, ' ')
    w = map(urllib.quote, w)
    return string.joinfields(w, '+')
