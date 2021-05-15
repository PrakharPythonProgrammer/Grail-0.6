"""HTML 2.0 parser.

See the HTML 2.0 specification:
http://www.w3.org/hypertext/WWW/MarkUp/html-spec/html-spec_toc.html
"""

import sys

if __name__ == '__main__':
    sys.path.insert(0, '../pythonlib')

import htmlentitydefs
import regsub
import string
import SGMLHandler
import SGMLLexer
import SGMLParser

from formatter import AS_IS
from types import DictType, StringType
from utils import *


URL_VALUED_ATTRIBUTES = ['href', 'src', 'codebase', 'data']


class HTMLParser(SGMLHandler.BaseSGMLHandler):

    entitydefs = htmlentitydefs.entitydefs.copy()
    new_entities = {
        "Dstrok": entitydefs["ETH"],
        "apos": "'",
        "ast": "*",
        "brkbar": entitydefs["brvbar"],
        "bsol": "\\",
        "circ": "^",
        "colon": ":",
        "comma": ",",
        "commat": "@",
        "die": entitydefs["uml"],
        "dollar": "$",
        "equals": "=",
        "excl": "!",
        "grave": "`",
        "half": entitydefs["frac12"],
        "hibar": entitydefs["macr"],
        "horbar": "_",
        "hyphen": "-",
        "lcub": "{",
        "ldquo": "``",
        "log": " log ",
        "lowbar": "_",
        "lpar": "(",
        "lsqb": "[",
        "lsquo": "`",
        "minus": "-",
        "num": "#",
        "OElig": "OE",
        "oelig": "oe",
        "percnt": "%",
        "period": ".",
        "plus": "+",
        "quest": "?",
        "rcub": "}",
        "rdquo": "''",
        "rpar": ")",
        "rsqb": "[",
        "rsquo": "'",
        "semi": ";",
        "sin": " sin ",
        "sol": "/",
        "tanh": " tanh ",
        "tilde": "~",
        "verbar": "|",
        "zwj": "",                      # i18n: zero-width joiner
        "zwnj": "",                     # i18n: zero-width non-joiner
        }
    for k, v in new_entities.items():
        entitydefs[k] = v

    doctype = 'html'
    autonumber = None
    savedata = None
    title = base = anchor = nextid = None
    nofill = badhtml = 0
    inhead = 1

    object_aware_tags = ['param', 'script', 'object', 'a', 'param']

    def __init__(self, formatter, verbose=0):
        self.sgml_parser = SGMLParser.SGMLParser(gatherer=self)
        self.sgml_parser.restrict(1)
        self.formatter = formatter
        self.anchor = None
        self.anchorlist = []
        self.list_stack = []
        self.object_stack = []
        self.headernumber = HeaderNumber()

    def feed(self, data):
        self.sgml_parser.feed(data)

    def close(self):
        self.sgml_parser.close()
        self.sgml_parser = None
        self.handle_data = SGMLParser._nullfunc

    # ------ Methods used internally; some may be overridden

    def set_data_handler(self, handler):
        self.handle_data = handler
        self.sgml_parser.set_data_handler(handler)

    # --- Formatter interface, taking care of 'savedata' mode;
    # shouldn't need to be overridden

    def handle_data_head(self, data):
        if self.suppress_output:
            return
        if string.strip(data):
            self.inhead = 0
            self.set_data_handler(self.formatter.add_flowing_data)
            self.handle_data(data)
            self.element_close_maybe('head', 'script', 'style', 'title')

    handle_data = handle_data_head      # always start in head

    def handle_data_save(self, data):
        self.savedata[0] = self.savedata[0] + data

    def get_devicetypes(self):
        """Return sequence of device type names."""
        return ('writer',)

    # --- Hooks to save data; shouldn't need to be overridden

    def save_bgn(self):
        if self.savedata:
            self.savedata.insert(0, '')
        else:
            self.savedata = ['']
        self.set_data_handler(self.handle_data_save)

    def save_end(self):
        if self.savedata:
            data = self.savedata[0]
            del self.savedata[0]
            if not self.savedata:       # deal with cheaters
                self.savedata = None
        else:
            data = ''
        if not self.savedata:
            if self.inhead:
                handler = self.handle_data_head
            elif self.nofill:
                handler = self.formatter.add_literal_data
            else:
                handler = self.formatter.add_flowing_data
            self.set_data_handler(handler)
        if not self.nofill:
            data = string.join(string.split(data))
        return data

    def push_nofill(self):
        self.nofill = self.nofill + 1
        self.set_data_handler(self.formatter.add_literal_data)

    def pop_nofill(self):
        self.nofill = max(0, self.nofill - 1)
        if not self.nofill:
            self.set_data_handler(self.formatter.add_flowing_data)

    # --- Manage the object stack

    suppress_output = 0                 # Length of object_stack at activation

    def push_object(self, tag):
        self.object_stack.append(tag)
        return self.suppress_output

    def set_suppress(self):
        self.suppress_output = len(self.object_stack)
        self.set_data_handler(self.handle_data_noop)

    def handle_data_noop(self, data):
        pass

    def pop_object(self):
        if self.suppress_output == len(self.object_stack):
            self.suppress_output = 0
            if self.nofill:
                handler = self.formatter.add_literal_data
            else:
                handler = self.formatter.add_flowing_data
            self.set_data_handler(handler)
            r = 1
        else:
            r = 0
        del self.object_stack[-1]
        return r

    __object = None
    def get_object(self):
        return self.__object

    def set_object(self, object):
        self.__object = object
        if object:
            self.set_suppress()

    def handle_starttag(self, tag, method, attrs):
        if self.suppress_output and tag not in self.object_aware_tags:
            return
        for k in URL_VALUED_ATTRIBUTES:
            if attrs.has_key(k) and attrs[k]:
                s = string.strip(attrs[k])
                # we really don't want to do this if this is a data: URL
                if len(s) < 5 or string.lower(s[:5]) != "data:":
                    s = string.joinfields(string.split(s), '')
                attrs[k] = s
        method(self, attrs)
        if attrs.has_key('id'):
            self.register_id(attrs['id'])

    def handle_endtag(self, tag, method):
        if self.suppress_output and tag not in self.object_aware_tags:
            return
        method(self)

    def start_object(self, attrs, tag='object'):
        if self.push_object(tag):
            return
        obj = self.handle_object(attrs)
        if obj:
            self.set_object(obj)

    def end_object(self):
        if self.pop_object():
            object = self.get_object()
            self.set_object(None)
            object.end()

    context = None
    def handle_object(self, attrs):
        if not self.context:            # Ugly, but we don't want to duplicate
            return None                 # this method in each subclass!
        #
        codetype = extract_keyword('codetype', attrs, conv=string.strip)
        if not codetype and attrs.has_key('classid'):
            codeurl = attrs['classid']
            codetype, opts = self.context.app.guess_type(codeurl)
        if not codetype and attrs.has_key('codebase'):
            codeurl = attrs['codebase']
            codetype, encoding = self.context.app.guess_type(codeurl)
        embedtype = codetype
        if not embedtype:
            datatype = extract_keyword('type', attrs, conv=string.strip)
            if not datatype and attrs.has_key('data'):
                dataurl = attrs['data']
                datatype, encoding = self.context.app.guess_type(dataurl)
            embedtype = datatype
        if not embedtype:
            return None
        #
        import copy
        message = extract_keyword('standby', attrs, '')
        message = string.join(string.split(message))
        info = self.context.app.find_type_extension(
            "filetypes", embedtype)
        embedder = info and info.embed
        obj = embedder and embedder(self, copy.copy(attrs))
        if obj:
            if message:
                self.context.message(message)
            return obj
        return None

    def do_param(self, attrs):
        if 0 < self.suppress_output == len(self.object_stack):
            name, value = None, None
            if attrs.has_key('name'):
                name = attrs['name']
            if attrs.has_key('value'):
                value = attrs['value']
            if name is not None and value is not None:
                self.get_object().param(name, value)

    # --- Hooks for anchors; should probably be overridden

    def anchor_bgn(self, href, name, type):
        self.anchor = href
        if href:
            self.anchorlist.append(href)
        if name:
            self.register_id(name)

    def anchor_end(self):
        if self.anchor:
            self.handle_data("[%d]" % len(self.anchorlist))
            self.anchor = None

    # --- Hook for images; should probably be overridden

    def handle_image(self, src, alt, *args):
        self.handle_data(alt)

    # --------- Top level elememts

    def start_html(self, attrs): pass
    def end_html(self): pass

    def start_head(self, attrs): pass
    def end_head(self):
        self.inhead = 0

    def start_body(self, attrs):
        self.element_close_maybe('head', 'style', 'script', 'title')
        self.inhead = 0

    def end_body(self): pass

    # ------ Head elements

    def start_title(self, attrs):
        self.save_bgn()

    def end_title(self):
        self.title = self.save_end()

    def do_base(self, attrs):
        if attrs.has_key('href'):
            self.base = attrs['href']

    def do_isindex(self, attrs):
        self.isindex = 1

    def do_link(self, attrs):
        pass

    def do_meta(self, attrs):
        pass

    def do_nextid(self, attrs):         # Deprecated, but maintain the state.
        self.element_close_maybe('style', 'title')
        if attrs.has_key('n'):
            self.nextid = attrs['n']
            self.badhtml = self.badhtml or not self.inhead
        else:
            self.badhtml = 1

    def start_style(self, attrs):
        """Disable display of document data -- this is a style sheet.
        """
        self.save_bgn()

    def end_style(self):
        """Re-enable data display.
        """
        self.save_end()

    def start_marquee(self, attrs):
        self.save_bgn()

    def end_marquee(self):
        self.save_end()

    # New tag: <SCRIPT> -- ignore anything inside it

    def start_script(self, attrs):
        if not self.push_object('script'):
            self.set_object(Embedding())
        self.save_bgn()

    def end_script(self):
        self.pop_object()
        self.save_end()
        self.set_object(None)

    # ------ Body elements

    # --- Headings

    def start_h1(self, attrs):
        self.header_bgn('h1', 0, attrs)

    def end_h1(self):
        self.header_end('h1', 0)

    def start_h2(self, attrs):
        self.header_bgn('h2', 1, attrs)

    def end_h2(self):
        self.header_end('h2', 1)

    def start_h3(self, attrs):
        self.header_bgn('h3', 2, attrs)

    def end_h3(self):
        self.header_end('h3', 2)

    def start_h4(self, attrs):
        self.header_bgn('h4', 3, attrs)

    def end_h4(self):
        self.header_end('h4', 3)

    def start_h5(self, attrs):
        self.header_bgn('h5', 4, attrs)

    def end_h5(self):
        self.header_end('h5', 4)

    def start_h6(self, attrs):
        self.header_bgn('h6', 5, attrs)

    def end_h6(self):
        self.header_end('h6', 5)

    def header_bgn(self, tag, level, attrs):
        self.element_close_maybe('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p')
        if self.sgml_parser.strict_p():
            while self.list_stack:
                self.badhtml = 1
                self.sgml_parser.lex_endtag(self.list_stack[0][0])
        self.formatter.end_paragraph(1)
        align = extract_keyword('align', attrs, conv=conv_normstring)
        self.formatter.push_alignment(align)
        self.formatter.push_font((tag, 0, 1, 0))
        self.header_number(tag, level, attrs)

    def header_end(self, tag, level):
        self.formatter.pop_font()
        self.formatter.end_paragraph(1)
        self.formatter.pop_alignment()

    __dedented_numbers = 0
    def header_number(self, tag, level, attrs):
        if self.autonumber is None:
            if attrs.has_key('seqnum') or attrs.has_key('skip'):
                self.autonumber = 1
        self.headernumber.incr(level, attrs)
        if self.autonumber:
            if self.__dedented_numbers:
                self.formatter.writer.send_label_data(
                    self.headernumber.string(level))
            else:
                self.formatter.add_flowing_data(
                    self.headernumber.string(level))

    # --- Block Structuring Elements

    def start_p(self, attrs):
        self.para_bgn(attrs)

    def end_p(self):
        self.para_end()

    def para_bgn(self, attrs, parbreak=1):
        if self.sgml_parser.has_context('pre'):
            if self.sgml_parser.has_context('p'):
                stack = self.sgml_parser.get_context('p')
                while stack:
                    self.sgml_parser.lex_endtag(stack[0])
                    stack = self.sgml_parser.get_context('p')
                # XXX this is really evil!
                del self.sgml_parser.stack[-1]
            return
        self.element_close_maybe('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6')
        self.formatter.end_paragraph(parbreak)
        align = extract_keyword('align', attrs, conv=conv_normstring)
        if align == "indent":
            align = None
        self.formatter.push_alignment(align)

    def para_end(self, parbreak=1):
        if not self.sgml_parser.has_context('pre'):
            if parbreak and self.list_stack:
                compact = self.list_stack[-1][3]
                parbreak = not compact
            self.formatter.end_paragraph(parbreak)
            self.formatter.pop_alignment()

    def implied_end_p(self):
        if self.sgml_parser.has_context('p'):
            #  Remove all but the <P>
            stack = self.sgml_parser.get_context('p')
            while stack:
                self.sgml_parser.lex_endtag(stack[0])
                stack = self.sgml_parser.get_context('p')
            #  Remove <P> surgically:
            del self.sgml_parser.stack[-1]
            self.para_end(parbreak=0)
        else:
            self.formatter.add_line_break()

    def start_div(self, attrs):
        self.para_bgn(attrs, parbreak=0)

    def end_div(self):
        self.para_end(parbreak=0)

    # New tag: <CENTER> (for Amy)

    def start_center(self, attrs):
        self.implied_end_p()
        self.formatter.add_line_break()
        self.formatter.push_alignment('center')

    def end_center(self):
        self.implied_end_p()
        self.formatter.add_line_break()
        self.formatter.pop_alignment()

    def start_pre(self, attrs):
        self.close_paragraph()
        self.formatter.end_paragraph(1)
        self.formatter.push_font((AS_IS, AS_IS, AS_IS, 1))
        self.formatter.push_alignment('left')
        self.push_nofill()
        self.set_data_handler(NewlineScratcher(self))

    def end_pre(self):
        self.pop_nofill()
        self.formatter.end_paragraph(1)
        self.formatter.pop_font()
        self.formatter.pop_alignment()

    def start_xmp(self, attrs):
        self.start_pre(attrs)
        self.sgml_parser.setliteral('xmp')              # Tell SGML parser

    def end_xmp(self):
        self.end_pre()

    def start_listing(self, attrs):
        self.start_pre(attrs)
        self.sgml_parser.setliteral('listing')  # Tell SGML parser

    def end_listing(self):
        self.end_pre()

    def start_address(self, attrs):
        self.do_br({})
        self.formatter.push_font((AS_IS, 1, AS_IS, AS_IS))

    def end_address(self):
        self.do_br({})
        self.formatter.pop_font()

    def start_blockquote(self, attrs):
        self.close_paragraph()
        self.formatter.end_paragraph(1)
        self.formatter.push_margin('blockquote')
        self.formatter.push_style('blockquote')

    def end_blockquote(self):
        self.close_paragraph()          # may be paragraphs in blockquotes
        self.formatter.end_paragraph(1)
        self.formatter.pop_margin()
        self.formatter.pop_style()

    # --- List Elements

    #   The document's list structure is stored in a stack called
    #   self.list_stack.  Each element of the stack is a list with
    #   the entries:
    #
    #       [element, label, entry_count, compact_p, stack_depth]
    #
    #   Where element can be 'dd', 'dl', 'dir', 'menu', 'ol', 'ul' (no 'dt');
    #         label is the item label (for 'ol', 'ul' only) for
    #           subsequent list items.  If this is a string, it is
    #           handled as a format string, otherwise it must be
    #           interpretable by the add_label_data() method of the
    #           writer;
    #         entry_count is the expected index of the next list
    #           item - 1;
    #         compact_p is a boolean (*must* be 0 or 1) set to true
    #           if COMPACT is set for the list (not implied by being
    #           in Grail) for the current list or an enclosing list;
    #         stack_depth is the depth of the element stack when the
    #           list was opened.  This is used to close all elements
    #           opened within a previous list item without having to
    #           check for specific elements.

    def start_lh(self, attrs):
        margin = None
        if self.list_stack:
            self.list_trim_stack()
            listtype = self.list_stack[-1][0]
            if listtype == 'dl':
                margin = 'lh'
        elif self.sgml_parser.has_context('p'):
            self.badhtml = 1
            self.sgml_parser.lex_endtag('p')
        self.do_br({})
        self.formatter.push_font(('', 1, 1, 0))
        self.formatter.push_margin(margin)
        if not self.list_stack:
            self.badhtml = 1

    def end_lh(self):
        self.formatter.pop_margin()
        self.formatter.pop_font()
        if self.list_stack:
            self.formatter.end_paragraph(not self.list_stack[-1][3])
        else:
            self.formatter.end_paragraph(1)

    def start_ul(self, attrs, tag='ul'):
        self.element_close_maybe('p', 'lh')
        if self.list_stack:
            self.formatter.end_paragraph(0)
            compact = self.list_stack[-1][3]
        else:
            self.formatter.end_paragraph(1)
            compact = 0
        self.formatter.push_margin('ul')
        if attrs.has_key('plain'):
            label = ''
        else:
            if attrs.has_key('type'):
                format = attrs['type']
            else:
                format = ('disc', 'circle', 'square')[len(self.list_stack) % 3]
            label = self.make_format(format, listtype='ul')
        self.list_stack.append([tag, label, 0,
                                #  Propogate COMPACT once set:
                                compact or attrs.has_key('compact'),
                                self.sgml_parser.get_depth() + 1])

    def end_ul(self):
        if self.list_stack:
            del self.list_stack[-1]
        if self.list_stack:
            self.implied_end_p()
            if self.formatter.have_label:
                self.formatter.assert_line_data()
            self.formatter.add_line_break()
        else:
            self.close_paragraph()
            if self.formatter.have_label:
                self.formatter.assert_line_data()
            self.formatter.end_paragraph(1)
        self.formatter.pop_margin()

    def do_li(self, attrs):
        if not self.list_stack:
            self.fake_li(attrs)
            return
        if self.sgml_parser.has_context('p'):   # compact trailing <P>
            self.implied_end_p()        # even though list_trim_stack() will
        self.list_trim_stack()          # close it.
        [listtype, label, counter, compact, depth] = top = self.list_stack[-1]
        if attrs.has_key('type'):
            s = attrs['type']
            if type(s) is StringType:
                label = top[1] = self.make_format(s, label, listtype=listtype)
            elif s:
                label = s
        if listtype == 'ol':
            if attrs.has_key('seqnum'):
                try: top[2] = counter = \
                              string.atoi(string.strip(attrs['seqnum']))
                except: top[2] = counter = counter+1
            elif attrs.has_key('value'):
                try: top[2] = counter = \
                              string.atoi(string.strip(attrs['value']))
                except: top[2] = counter = counter+1
            else:
                top[2] = counter = counter+1
            if attrs.has_key('skip'):
                try: top[2] = counter = counter + string.atoi(attrs['skip'])
                except: pass
        self.formatter.add_label_data(label, counter)

    def fake_li(self, attrs):
        #  Illegal, but let's try not to be ugly:
        self.badhtml = 1
        self.element_close_maybe('p', 'lh')
        self.formatter.end_paragraph(0)
        format = '*'
        if attrs.has_key('type') and (type(attrs['type']) is StringType):
            format = self.make_format(attrs['type'], format)
        else:
            format = self.make_format(format, 'disc', listtype='ul')
        if type(format) is StringType:
            data = self.formatter.format_counter(format, 1) + ' '
            self.formatter.add_flowing_data(data)

    def make_format(self, format, default='*', listtype=None):
        if not format:
            format = default
        if format in ('1', 'a', 'A', 'i', 'I') and listtype == 'ol':
            format = format + '.'
        elif type(format) is not StringType:
            pass
        elif listtype == 'ul':
            format = '*'
        else:
            format = string.strip(format)
        return format

    def start_ol(self, attrs):
        self.close_paragraph()
        if self.list_stack:
            self.formatter.end_paragraph(0)
            compact = self.list_stack[-1][3]
        else:
            self.formatter.end_paragraph(1)
            compact = 0
        self.formatter.push_margin('ol')
        if attrs.has_key('type'):
            label = self.make_format(attrs['type'], '1', listtype='ol')
        else:
            label = '1.'
        start = 0
        if attrs.has_key('seqnum'):
            try: start = string.atoi(attrs['seqnum']) - 1
            except: pass
        elif attrs.has_key('start'):
            try: start = string.atoi(attrs['start']) - 1
            except: pass
        self.list_stack.append(['ol', label, start,
                                compact or attrs.has_key('compact'),
                                self.sgml_parser.get_depth() + 1])

    def end_ol(self):
        self.end_ul()

    def start_menu(self, attrs):
        attrs['plain'] = None
        self.start_ul(attrs, tag='menu')

    def end_menu(self):
        self.end_ul()

    def start_dir(self, attrs):
        attrs['plain'] = None
        attrs['wrap'] = 'horiz'
        self.start_ul(attrs, tag='dir')

    def end_dir(self):
        self.end_ul()

    def start_dl(self, attrs):
        margin = None
        if self.list_stack:
            self.implied_end_p()
            self.formatter.end_paragraph(0)
            if self.list_stack[-1][3]:
                attrs['compact'] = None
            if self.list_stack[-1][0] == 'dl':
                margin = 'dl'
            attrs['compact'] = None
        else:
            self.close_paragraph()
            self.formatter.end_paragraph(1)
        self.formatter.push_margin(margin)
        self.list_stack.append(['dl', '', 0, attrs.has_key('compact'),
                                self.sgml_parser.get_depth() + 1])

    def end_dl(self):
        self.ddpop(not (self.list_stack and self.list_stack[-1][3]))
        if self.list_stack: del self.list_stack[-1]
        self.formatter.pop_margin()

    def do_dt(self, attrs):
        self.ddpop()

    def do_dd(self, attrs):
        self.ddpop()
        self.formatter.push_margin('dd')
        self.formatter.have_label = 1
        compact = self.list_stack and self.list_stack[-1][3]
        self.list_stack.append(['dd', '', 0, compact,
                                self.sgml_parser.get_depth() + 1])

    def ddpop(self, bl=0):
        self.element_close_maybe('lh', 'p')
        self.formatter.end_paragraph(bl)
        if not self.list_stack or self.list_stack[-1][0] not in ('dl', 'dd'):
            # we're not already in a DL, so imply one.
            # this isn't perfect compatibility, but keeps grail from
            # dying a horrible death.
            self.sgml_parser.lex_starttag('dl', {})
            self.badhtml = 1
        if self.list_stack:
            if self.list_stack[-1][0] == 'dd':
                del self.list_stack[-1]
                self.list_trim_stack()
                self.formatter.pop_margin()
            elif self.list_stack[-1][0] == 'dl':
                self.list_trim_stack()

    def list_trim_stack(self):
        if not self.list_stack:
            return
        depth = self.list_stack[-1][4]
        stack = self.sgml_parser.get_stack()
        while len(stack) > depth:
            self.sgml_parser.lex_endtag(stack[depth])
            stack = self.sgml_parser.get_stack()

    # --- Phrase Markup

    # Idiomatic Elements

    def start_cite(self, attrs): self.start_i(attrs)
    def end_cite(self): self.end_i()

    def start_code(self, attrs): self.start_tt(attrs)
    def end_code(self): self.end_tt()

    def start_del(self, attrs):
        self.formatter.push_font((AS_IS, 1, AS_IS, AS_IS))
        self.formatter.push_style('red')
    def end_del(self):
        self.formatter.pop_style()
        self.formatter.pop_font()

    def start_ins(self, attrs):
        self.formatter.push_font((AS_IS, 1, AS_IS, AS_IS))
        self.formatter.push_style('ins')
    def end_ins(self):
        self.formatter.pop_style()
        self.formatter.pop_font()

    def start_dfn(self, attrs): self.start_i(attrs)
    def end_dfn(self): self.end_i()

    def start_em(self, attrs): self.start_i(attrs)
    def end_em(self): self.end_i()

    def start_kbd(self, attrs): self.start_tt(attrs)
    def end_kbd(self): self.end_tt()

    def start_samp(self, attrs): self.start_tt(attrs)
    def end_samp(self): self.end_tt()

    def start_strike(self, attrs):
        self.formatter.push_style('overstrike', 'red')
    def end_strike(self):
        self.formatter.pop_style(2)

    def start_strong(self, attrs): self.start_b(attrs)
    def end_strong(self): self.end_b()

    def start_var(self, attrs): self.start_i(attrs)
    def end_var(self): self.end_i()

    # Typographic Elements

    def start_i(self, attrs):
        self.formatter.push_font((AS_IS, 1, AS_IS, AS_IS))
    def end_i(self):
        self.formatter.pop_font()

    def start_b(self, attrs):
        self.formatter.push_font((AS_IS, AS_IS, 1, AS_IS))
    def end_b(self):
        self.formatter.pop_font()

    def start_tt(self, attrs):
        self.formatter.push_font((AS_IS, AS_IS, AS_IS, 1))
    def end_tt(self):
        self.formatter.pop_font()

    def start_u(self, attrs):
        self.formatter.push_style('underline')
    def end_u(self):
        self.formatter.pop_style()

    def start_s(self, attrs):
        self.formatter.push_style('overstrike')
    def end_s(self):
        self.formatter.pop_style()

    def start_a(self, attrs):
        if self.get_object():
            self.get_object().anchor(attrs)
            return
        href = string.strip(attrs.get('href', ''))
        name = extract_keyword('name', attrs, '', conv=conv_normstring)
        type = extract_keyword('type', attrs, '', conv=conv_normstring)
        self.anchor_bgn(href, name, type)

    def end_a(self):
        self.anchor_end()

    # --- Line Break

    def do_br(self, attrs):
        self.formatter.add_line_break()
        if self.sgml_parser.has_context('pre'):
            self.set_data_handler(NewlineScratcher(self, 1))

    def start_nobr(self, attrs):
        self.formatter.push_style('pre')

    def end_nobr(self):
        self.formatter.pop_style()

    # --- Horizontal Rule

    def do_hr(self, attrs):
        self.implied_end_p()
        if attrs.has_key('width'):
            abswidth, percentwidth = self.parse_width(attrs['width'])
        else:
            abswidth, percentwidth = None, 1.0
        height = None
        align = 'center'
        if attrs.has_key('size'):
            try: height = string.atoi(attrs['size'])
            except: pass
            else: height = max(1, height)
        if attrs.has_key('align'):
            try: align = string.lower(attrs['align'])
            except: pass
        self.formatter.add_hor_rule(abswidth, percentwidth, height, align)

    def parse_width(self, str):
        str = string.strip(str or '')
        if not str:
            return None, None
        wid = percent = None
        if str[-1] == '%':
            try: percent = string.atoi(str[:-1])
            except: pass
            else: percent = min(1.0, max(0.0, (0.01 * percent)))
        elif len(str) > 3 and string.lower(str[-3:]) == "pct":
            try: percent = string.atoi(str[:-3])
            except: pass
            else: percent = min(1.0, max(0.0, (0.01 * percent)))
        else:
            try: wid = max(0, string.atoi(str))
            except: pass
            else: wid = wid or None
        if not (wid or percent):
            percent = 1.0
        return wid, percent

    # --- Image

    def do_img(self, attrs):
        align = ''
        alt = '(image)'
        ismap = ''
        src = ''
        width = 0
        height = 0
        if attrs.has_key('align'):
            align = string.lower(attrs['align'])
        if attrs.has_key('alt'):
            alt = attrs['alt']
        if attrs.has_key('ismap'):
            ismap = 1
        if attrs.has_key('src'):
            src = string.strip(attrs['src'])
        if attrs.has_key('width'):
            try: width = string.atoi(attrs['width'])
            except: pass
        if attrs.has_key('height'):
            try: height = string.atoi(attrs['height'])
            except: pass
        self.handle_image(src, alt, ismap, align, width, height)

    def do_image(self, attrs):
        self.do_img(attrs)

    # --- Really Old Unofficial Deprecated Stuff

    def do_plaintext(self, attrs):
        self.start_pre(attrs)
        self.setnomoretags() # Tell SGML parser

    # --- Grail magic: processing instructions!

    def handle_pi(self, stuff):
        fields = string.split(string.lower(stuff))
        if not fields or fields[0] != 'grail':
            self.unknown_pi(fields)
            return
        fields[0] = 'pi'
        width = len(fields)
        while width >= 2:
            procname = string.joinfields(fields[:width], '_')
            if hasattr(self, procname):
                getattr(self, procname)(fields[width:])
                return
            width = width - 1
        # could not locate handler
        fields[0] = 'grail'
        self.unknown_pi(fields)

    def pi_header_numbers(self, arglist):
        if len(arglist) != 1:
            return
        arg = arglist[0]
        if arg == 'dedent':
            self.__dedented_numbers = self.__dedented_numbers + 1
            self.formatter.push_margin('pi')
        elif arg == 'undent':
            depth = self.__dedented_numbers - 1
            self.__dedented_numbers = max(0, depth)
            self.formatter.pop_margin()

    # --- Unhandled elements:

    def unknown_pi(self, fields):
##      print "Could not locate processing instruction handler:"
##      print "   ", fields
        pass

    # We don't implement these, but we want to know that they go in pairs,
    # just in case we're in "strict" mode.  They need to have been defined
    # *somewhere* to get listed here, preferably with documentation
    # available.  These are candidates for subclasses, but we'd like to
    # keep the SGML context stack as well-maintained as possible.
    #
    UNIMPLEMENTED_CONTAINERS = [
        'abbrev', 'acronym', 'applet', 'au', 'author', 'big', 'blink',
        'bq', 'caption', 'cmd', 'comment', 'credit', 'fig', 'fn', 'font',
        'frameset', 'lang', 'math', 'noembed', 'noframes', 'noscript',
        'note', 'person', 'q', 'small', 'span', 'sub', 'sup', 'webcreeper',
        ]

    def unknown_starttag(self, tag, attrs):
        self.badhtml = 1

    def register_id(self, id):
        pass

    def unknown_endtag(self, tag):
        self.badhtml = 1

    def get_taginfo(self, tag):
        override = self.context.app.prefs.GetBoolean(
            'parsing-html', 'override-builtin-tags')
        taginfo = None
        if override:
            # This prefers external definitions over internal definitions:
            taginfo = self.get_extension_taginfo(tag)
            if taginfo:
                return taginfo
        taginfo = SGMLHandler.BaseSGMLHandler.get_taginfo(self, tag)
        if not (taginfo or override):
            taginfo = self.get_extension_taginfo(tag)
        if not taginfo and tag in self.UNIMPLEMENTED_CONTAINERS:
            return DummyTagInfo(tag)
        else:
            return taginfo

    __tagmask = string.maketrans('-.', '__')
    def get_extension_taginfo(self, tag):
        tag = string.translate(tag, self.__tagmask) # ??? why ???
        for dev in self.get_devicetypes():
            try:
                loader = self.context.app.get_loader("html." + dev)
            except KeyError:
                pass
            else:
                taginfo = loader.get(tag)
                if taginfo:
                    return taginfo
        return None

    # a few interesting UNICODE values:
    __charrefs = {
        # these first four are really supposed to be ligatures
        0x008C: "OE",                   # invalid, but compatible w/ Win32
        0x009C: "oe",
        0x0152: "OE",                   # valid versions of the same
        0x0153: "oe",
        #
        0x200C: "",                     # zero-width non-joiner
        0x200D: "",                     # zero-width joiner
        }
    def unknown_charref(self, ordinal, terminator):
        if ordinal == 0x2028:           # line separator
            return self.do_br({})
        if ordinal == 0x2029:           # paragraph separator
            return self.start_p({})
        if self.__charrefs.has_key(ordinal):
            data = self.__charrefs[ordinal]
        else:
            data = "%s%d%s" % (SGMLLexer.CRO, ordinal, terminator)
            self.badhtml = 1
        self.handle_data(data)

    def unknown_entityref(self, entname, terminator):
        # support through a method:
        if hasattr(self, "entref_" + entname):
            getattr(self, "entref_" + entname)(terminator)
            return
        self.badhtml = 1
        # if the name is not all lower case, try a lower case version:
        if entname == string.upper(entname):
            self.handle_entityref(string.lower(entname), terminator)
        else:
            self.handle_data('%s%s%s' % (SGMLLexer.ERO, entname, terminator))

    # remove from the dictionary so the "unknown" handler can call the
    # magic implementation...
    if entitydefs.has_key("nbsp"):
        del entitydefs["nbsp"]

    def entref_nbsp(self, terminator):
        # for non-strict interpretation: really nasty stuff to act more
        # like more popular browsers.  Really just turns &nbsp; into a
        # normal space, so it'll still be breakable, but it will always
        # be pushed to the output device.  This means multiple &nbsp;'s
        # will act as spacers.  Ugh.
        if self.sgml_parser.strict_p():
            self.handle_data(' ')
        else:
            self.formatter.flush_softspace()
            self.formatter.writer.send_literal_data(' ')

    def entref_emsp(self, terminator):
        if self.formatter.softspace:
            self.formatter.flush_softspace()
            self.formatter.add_literal_data(' ')
        else:
            self.formatter.add_literal_data('  ')

    def entref_bull(self, terminator):
        self.unknown_entityref("disc", terminator)

    def report_unbalanced(self, tag):
        self.badhtml = 1

    # --- Utilities:

    def element_close_maybe(self, *elements):
        """Handle any open elements on the stack of the given types.

        `elements' should be a tuple of all element types which must be
        closed if they exist on the stack.  Sequence is not important.
        """
        for elem in elements:
            if self.sgml_parser.has_context(elem):
                self.sgml_parser.lex_endtag(elem)

    def close_paragraph(self):
        if self.sgml_parser.has_context('p'):
            self.sgml_parser.lex_endtag('p')


class DummyTagInfo(SGMLParser.TagInfo):
    def __init__(self, tag):
        SGMLParser.TagInfo.__init__(self, tag, None, None, None)


class NewlineScratcher:
    import regex
    __scratch_re = regex.compile("[ \t]*\n")

    # for new version only:
##     __buffer = ''

    def __init__(self, parser, limit=-1):
        self.__limit = limit
        self.__parser = parser

    def __call__(self, data):
        # new version that works better sometimes but can really die badly:
        # (hopefully fixable!)
##      data = self.__buffer + data
##      while "\n" in data and self.__limit != 0:
##          length = self.__scratch_re.match(data)
##          if length >= 0:
##              data = data[length:]
##              self.__limit = self.__limit - 1
##      if string.strip(data) or self.__limit == 0:
##          self.__parser.formatter.add_literal_data(data)
##          self.__parser.set_data_handler(
##              self.__parser.formatter.add_literal_data)
##          self.__parser = None
##      else:
##          self.__buffer = data
        # old version:
        while data and data[0] == "\n" and self.__limit != 0:
            data = data[1:]
            self.__limit = self.__limit - 1
        if data:
            self.__parser.formatter.add_literal_data(data)
            self.__parser.set_data_handler(
                self.__parser.formatter.add_literal_data)
            del self.__parser


class HeaderNumber:
    formats = ['',
               '%(h2)d. ',
               '%(h2)d.%(h3)d. ',
               '%(h2)d.%(h3)d.%(h4)d. ',
               '%(h2)d.%(h3)d.%(h4)d.%(h5)d. ',
               '%(h2)d.%(h3)d.%(h4)d.%(h5)d.%(h6)d. ']

    def __init__(self, formats=None):
        self.numbers = [0, 0, 0, 0, 0, 0]
        if formats and len(formats) >= 6:
            self.formats = map(None, formats)
        else:
            self.formats = map(None, self.formats)

    def incr(self, level, attrs):
        numbers = self.numbers
        i = level
        while i < 5:
            i = i + 1
            numbers[i] = 0
        if attrs.has_key('skip'):
            try: skip = string.atoi(attrs['skip'])
            except: skip = 0
        else:
            skip = 0
        if attrs.has_key('seqnum'):
            try: numbers[level] = string.atoi(attrs['seqnum'])
            except: pass
            else: return
        numbers[level] = numbers[level] + 1 + skip

    def string(self, level, format = None):
        if format is None:
            format = self.formats[level]
        numbers = self.numbers
        numdict = {'h1': numbers[0],
                   'h2': numbers[1],
                   'h3': numbers[2],
                   'h4': numbers[3],
                   'h5': numbers[4],
                   'h6': numbers[5]}
        return format % numdict

    def get_format(self, level):
        return self.formats[level]

    def get_all_formats(self):
        return tuple(self.formats)

    def set_format(self, level, s):
        self.formats[level] = s

    def set_default_format(self, level, s):
        HeaderNumber.formats[level] = s

HeaderNumber.set_default_format = HeaderNumber().set_default_format


class Embedding:
    def __init__(self):
        pass

    def anchor(self, attrs):
        # allow use for image maps
        pass

    def param(self, name, value):
        # pass in parameter values
        pass

    def end(self):
        # </object>
        pass


def test():
    import sys
    file = 'test.html'
    if sys.argv[1:]: file = sys.argv[1]
    fp = open(file, 'r')
    data = fp.read()
    fp.close()
    from formatter import NullWriter, AbstractFormatter
    w = NullWriter()
    f = AbstractFormatter(w)
    p = HTMLParser(f)
    p.feed(data)
    p.close()


if __name__ == '__main__':
    test()
