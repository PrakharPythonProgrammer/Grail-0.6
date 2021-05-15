"""A parser for SGML, using the derived class as static DTD."""

__version__ = "$Revision: 1.27 $"

import SGMLLexer
import SGMLHandler
import string

SGMLError = SGMLLexer.SGMLError


# SGML parser class -- find tags and call handler functions.
# Usage: p = SGMLParser(); p.feed(data); ...; p.close().
# The dtd is defined by deriving a class which defines methods
# with special names to handle tags: start_foo and end_foo to handle
# <foo> and </foo>, respectively, or do_foo to handle <foo> by itself.


class SGMLParser(SGMLLexer.SGMLLexer):

    doctype = ''                        # 'html', 'sdl', '...'

    def __init__(self, gatherer=None, verbose=0):
        self.verbose = verbose
        if gatherer is None:
            gatherer = SGMLHandler.BaseSGMLHandler()
        self.push_handler(gatherer)
        SGMLLexer.SGMLLexer.__init__(self)

    def close(self):
        SGMLLexer.SGMLLexer.close(self)

    # This is called by the lexer after the document has been fully processed;
    # needed to clean out circular references and empty the stack.
    def cleanup(self):
        while self.stack:
            self.lex_endtag(self.stack[-1][0].tag)
        self.__taginfo = {}
        self.set_data_handler(_nullfunc)
        SGMLLexer.SGMLLexer.cleanup(self)
        self.__handler = None

    # Interface -- reset this instance.  Loses all unprocessed data.
    def reset(self):
        SGMLLexer.SGMLLexer.reset(self)
        self.normalize(1)               # normalize NAME token to lowercase
        self.restrict(1)                # impose user-agent compatibility
        self.omittag = 1                # default to HTML style
        self.stack = []

    def get_handler(self):
        return self.__handler

    def push_handler(self, handler):
        self.__handler = handler
        self.__taginfo = {}
        self.set_data_handler(handler.handle_data)

    def get_depth(self):
        """Return depth of the element stack."""
        return len(self.stack)

    def get_stack(self):
        """Return current context stack.

        This allows tag implementations to examine their context.
        """
        result = []
        append = result.append
        for ti, handler, ticache, nhandler in self.stack:
            append(ti.tag)
        return result

    def get_context(self, gi):
        """Return the context within the innermost instance of an element
        specified by a General Identifier.

        The `context' is a sequence of General Indentifiers of elements
        opened within the innermost instance of an element whose General
        Identifier is given by `gi'.  If there is no open element with the
        specified General Identifier, returns `None'.

        This example demonstrates the expected return values of this method;
        the document fragment is in HTML:

            <html>
              <title>demonstration of SGMLParser.get_context()</>
              <body>
                <ol>
                  <li> Item one:
                    <ul>
                      <li> Item in nested <em>list....
                        (Call parser.get_context(gi) here...)

            `gi' == 'html' ==> ['body', 'ol', 'li', 'ul', 'li', 'em']
            `gi' == 'title' ==> None
            `gi' == 'li' ==> ['em']
            `gi' == 'ol' ==> ['li', 'ul', 'li', 'em']
            `gi' == 'bogus' ==> None
        """
        stack = self.stack
        depth = len(stack)
        while depth:
            depth = depth - 1
            if stack[depth][0].tag == gi:
                context = stack[depth + 1:]
                break
        else:
            # no such context
            return None
        for i in range(len(context)):
            context[i] = context[i][0].tag
        return context

    def has_context(self, gi):
        for entry in self.stack:
            if entry[0].tag == gi:
                return 1
        return 0

    #  The remaining methods are the internals of the implementation and
    #  interface with the lexer.  Subclasses should rarely need to deal
    #  with these.

    def lex_data(self, data):
        self.__handler.handle_data(data)

    def lex_pi(self, pi_data):
        self.__handler.handle_pi(pi_data)

    def set_data_handler(self, handler):
        self.handle_data = handler
        if hasattr(self, '_l'):
            self._l.data_cb = handler
        self.lex_data = handler

    def lex_starttag(self, tag, attrs):
        #print 'received start tag', `tag`
        if not tag:
            if self.omittag and self.stack:
                tag = self.lasttag
            elif not self.omittag:
                self.lex_endtag('')
                return
            elif not self.stack:
                tag = self.doctype
                if not tag:
                    raise SGMLError, \
                          'Cannot start the document with an empty tag.'
        if self.__taginfo.has_key(tag):
            taginfo = self.__taginfo[tag]
        else:
            taginfo = self.__handler.get_taginfo(tag)
            self.__taginfo[tag] = taginfo
        if not taginfo:
            self.__handler.unknown_starttag(tag, attrs)
        elif taginfo.container:
            self.lasttag = tag
            handler = self.__handler
            ticache = self.__taginfo
            handler.handle_starttag(tag, taginfo.start, attrs)
            self.stack.append((taginfo, handler, ticache, self.__handler))
        else:
            handler = self.__handler
            ticache = self.__taginfo
            handler.handle_starttag(tag, taginfo.start, attrs)
            handler.handle_endtag(tag, taginfo.end)
            self.__handler = handler
            self.__taginfo = ticache

    def lex_endtag(self, tag):
        stack = self.stack
        if tag:
            found = None
            for i in range(len(stack)):
                if stack[i][0].tag == tag:
                    found = i
            if found is None:
                self.__handler.report_unbalanced(tag)
                return
        elif stack:
            found = len(stack) - 1
        else:
            self.__handler.report_unbalanced(tag)
            return
        while len(stack) > found:
            taginfo, handler, ticache, nhandler = stack[-1]
            if handler is not nhandler:
                nhandler.close()
            handler.handle_endtag(taginfo.tag, taginfo.end)
            self.__handler = handler
            self.__taginfo = ticache
            del stack[-1]


    named_characters = {'re' : '\r',
                        'rs' : '\n',
                        'space' : ' '}

    def lex_namedcharref(self, name, terminator):
        if self.named_characters.has_key(name):
            self.__handler.handle_data(self.named_characters[name])
        else:
            self.__handler.unknown_namedcharref(name, terminator)

    def lex_charref(self, ordinal, terminator):
        if 0 < ordinal < 256:
            self.__handler.handle_data(chr(ordinal))
        else:
            self.__handler.unknown_charref(ordinal, terminator)

    def lex_entityref(self, name, terminator):
        self.__handler.handle_entityref(name, terminator)


from types import StringType

class TagInfo:
    as_dict = 1
    container = 1

    def __init__(self, tag, start, do, end):
        self.tag = tag
        if start:
            self.start = start
            self.end = end or _nullfunc
        else:
            self.container = 0
            self.start = do or _nullfunc
            self.end = _nullfunc

    def __cmp__(self, other):
        # why is this needed???
        if type(other) is StringType:
            return cmp(self.tag, other)
        if type(other) is type(self):
            return cmp(self.tag, other.tag)
        raise TypeError, "incomparable values"


def _nullfunc(*args, **kw):
    # Dummy end tag handler for situations where no handler is provided
    # or allowed.
    pass
