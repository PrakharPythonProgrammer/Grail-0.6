"""HTML to PostScript translator.

This module uses the AbstractWriter class interface defined by in the
standard formatter module to generate PostScript corresponding to a
stream of HTML text.  The HTMLParser class scans the HTML stream,
generating high-level calls to an AbstractWriter object.

Note that this module can be run as a standalone script for command
line conversion of HTML files to PostScript.  Use the '-h' option to
see information about all-too-many command-line options.

"""

import os
import sys
import posixpath
import string
import traceback
import urllib
import urlparse

from types import TupleType

# local modules:
import epstools
import fonts                            # nested package
import utils
import PSParser
import PSWriter

from grailbase.uricontext import URIContext


MULTI_DO_PAGE_BREAK = 1                 # changing this breaks stuff




#  The main program.  Really needs to be broken up a bit!


def run(app):
    global logfile
    import getopt
    import paper
    import settings
    settings = settings.get_settings(app.prefs)
    # do this after loading the settings so the user can just call
    # get_settings() w/out an arg to get a usable object.
    load_rcscript()
    context = None
    help = None
    error = 0
    logfile = None
    title = ''
    url = ''
    tabstop = None
    multi = 0
    verbose = 0
    printer = None
    copies = 1
    levels = None
    outfile = None
    #
    try:
        options, args = getopt.getopt(sys.argv[1:],
                                      'mvhdcaUl:u:t:sp:o:f:C:P:T:',
                                      ['color',
                                       'copies=',
                                       'debug',
                                       'fontsize=',
                                       'footnote-anchors',
                                       'help',
                                       'images',
                                       'logfile=',
                                       'multi',
                                       'orientation=',
                                       'output=',
                                       'papersize=',
                                       'paragraph-indent=',
                                       'paragraph-skip=',
                                       'printer=',
                                       'strict-parsing',
                                       'tab-width=',
                                       'tags=',
                                       'title=',
                                       'underline-anchors',
                                       'url=',
                                       'verbose',
                                       ])
    except getopt.error, err:
        error = 1
        help = 1
        options = ()
        sys.stderr.write("option failure: %s\n" % err)
    for opt, arg in options:
        if opt in ('-h', '--help'):
            help = 1
        elif opt in ('-a', '--footnote-anchors'):
            settings.footnoteflag = not settings.footnoteflag
        elif opt in ('-i', '--images'):
            settings.imageflag = not settings.imageflag
        elif opt in ('-d', '--debug'):
            utils.set_debugging(1)
        elif opt in ('-l', '--logfile'):
            logfile = arg
        elif opt in ('-o', '--orientation'):
            settings.orientation = arg
        elif opt in ('-f', '--fontsize'):
            settings.set_fontsize(arg)
        elif opt in ('-t', '--title'):
            title = arg
        elif opt in ('-u', '--url'):
            url = arg
        elif opt in ('-U', '--underline-anchors'):
            settings.underflag = not settings.underflag
        elif opt in ('-c', '--color'):
            settings.greyscale = not settings.greyscale
        elif opt in ('-p', '--papersize'):
            settings.papersize = arg
        elif opt in ('-s', '--strict-parsing'):
            settings.strict_parsing = not settings.strict_parsing
        elif opt in ('-C', '--copies'):
            copies = string.atoi(arg)
        elif opt in ('-P', '--printer'):
            printer = arg
        elif opt in ('-T', '--tab-width'):
            tabstop = string.atof(arg)
        elif opt in ('-m', '--multi'):
            multi = 1
        elif opt in ('-v', '--verbose'):
            verbose = verbose + 1
        elif opt == '--output':
            outfile = arg
        elif opt == '--tags':
            if not load_tag_handler(app, arg):
                error = 2
                help = 1
        elif opt == '--paragraph-indent':
            # negative indents should indicate hanging indents, but we don't
            # do those yet, so force to normal interpretation
            settings.paragraph_indent = max(string.atof(arg), 0.0)
        elif opt == '--paragraph-skip':
            settings.paragraph_skip = max(string.atof(arg), 0.0)
    if help:
        usage(settings)
        sys.exit(error)
    # crack open log file if given
    stderr = sys.stderr
    if logfile:
        try: sys.stderr = open(logfile, 'a')
        except IOError: sys.stderr = stderr
    utils.debug("Using Python version " + sys.version)
    # crack open the input file, or stdin
    outfp = None
    if printer:
        if copies < 1:
            copies = 1
        outfile = "|lpr -#%d -P%s" % (copies, printer)
    if args:
        infile = args[0]
        if args[1:]:
            multi = 1
        infp, outfn = open_source(infile)
        if not outfile:
            outfile = (os.path.splitext(outfn)[0] or 'index') + '.ps'
    else:
        infile = None
        infp = sys.stdin
        outfile = '-'
    #
    # open the output file
    #
    if outfile[0] == '|':
        cmd = string.strip(outfile[1:])
        outfile = '|' + cmd
        outfp = os.popen(cmd, 'w')
    elif outfile == '-':
        outfp = sys.stdout
    else:
        outfp = open(outfile, 'w')
    if outfile != '-':
        print 'Outputting PostScript to', outfile

    if url:
        context = URIContext(url)
    elif infile:
        url = infile
        context = URIContext(url)
    else:
        # BOGOSITY: reading from stdin
        context = URIContext("file:/index.html")
    context.app = app
    paper = printing.paper.PaperInfo(settings.papersize,
                                     margins=settings.margins,
                                     rotation=settings.orientation)
    if tabstop and tabstop > 0:
        paper.TabStop = tabstop
    if utils.get_debugging('paper'):
        paper.dump()
    # create the writer & parser
    fontsize, leading = settings.get_fontsize()
    w = PSWriter.PSWriter(outfp, title or None, url or '',
                          #varifamily='Palatino',
                          paper=paper, settings=settings)
    ctype = "text/html"
    mod = app.find_type_extension("printing.filetypes", ctype)
    if not mod.parse:
        sys.exit("cannot load printing support for " + ctype)
    p = mod.parse(w, settings, context)
    if multi:
        if args[1:]:
            xform = explicit_multi_transform(args[1:])
        else:
            xform = multi_transform(context, levels)
        p.add_anchor_transform(xform)
        p.feed(infp.read())
        docs = [(context.get_url(), 1, w.ps.get_title(), 1)]
        #
        # This relies on xform.get_subdocs() returning the list used
        # internally to accumulate subdocs.  Make a copy to go only one
        # level deep.
        #
        for url in xform.get_subdocs():
            xform.set_basedoc(url)
            while p.sgml_parser.get_depth():
                p.sgml_parser.lex_endtag(p.sgml_parser.get_stack()[0])
            try:
                infp, fn = open_source(url)
            except IOError, err:
                if verbose and outfp is not sys.stdout:
                    print "Error opening subdocument", url
                    print "   ", err
            else:
                new_ctype = get_ctype(app, url, infp)
                if new_ctype != ctype:
                    if verbose:
                        print "skipping", url
                        print "  wrong content type:", new_ctype
                    continue
                if verbose and outfp is not sys.stdout:
                    print "Subdocument", url
                w.ps.close_line()
                if MULTI_DO_PAGE_BREAK: # must be true for now, not sure why
                    pageend = w.ps.push_page_end()
                    context.set_url(url)
                    w.ps.set_pageno(w.ps.get_pageno() + 1)
                    w.ps.set_url(url)
                    w.ps.push_page_start(pageend)
                else:
                    context.set_url(url)
                    w.ps.set_url(url)
                pageno = w.ps.get_pageno()
                p.feed(infp.read())
                infp.close()
                title = w.ps.get_title()
                p._set_docinfo(url, pageno, title)
                spec = (url, pageno, title, xform.get_level(url))
                docs.append(spec)
    else:
        p.feed(infp.read())
    p.close()
    w.close()



#  Lots of helper functions....


def load_tag_handler(app, arg):
    loader = app.get_loader("html.postscript")
    narg = os.path.join(os.getcwd(), arg)
    if os.path.isdir(narg):
        loader.add_directory(narg)
    elif os.path.isfile(narg):
        basename, ext = os.path.splitext(narg)
        if ext != ".py":
            sys.stdout = sys.stderr
            print ("Extra tags must be defined in a"
                   " Python source file with '.py' extension.")
            print
            return 0
        dirname, modname = os.path.split(basename)
        oldpath = sys.path
        try:
            sys.path = [dirname] + oldpath
            exec "import %s ; mod = %s" % (modname, modname)
            loader.load_tag_handlers(mod)
        finally:
            sys.path = oldpath
    else:
        sys.stdout = sys.stderr
        print "Could not locate tag handler", arg
        print
        print "Argument to --tags must be a directory to be added to the html"
        print "package or a file containing tag handler functions.  The tag"
        print "handlers defined in the directory or file will take precedence"
        print "over any defined in other extensions."
        print
        return 0
    return 1


def get_ctype(app, url, infp):
    """Attempt to determine the MIME content-type as best as possible."""
    try:
        return infp.info()["content-type"]
    except (AttributeError, KeyError):
        return app.guess_type(url)[0]


def load_rcscript():
    try:
        import grailutil
    except ImportError:
        return
    graildir = grailutil.getgraildir()
    userdir = os.path.join(graildir, "user")
    if os.path.isdir(userdir):
        sys.path.insert(0, userdir)
        try:
            import html2psrc
        except ImportError:
            pass
        except:
            traceback.print_exc()
            sys.stderr.write("[Traceback generated in html2psrc module.]\n")


def open_source(infile):
    try:
        infp = open(infile, 'r')
    except IOError:
        # derive file object via URL; still needs to be HTML.
        infp = urllib.urlopen(infile)
        # use posixpath since URLs are expected to be POSIX-like; don't risk
        # that we're running on NT and os.path.basename() doesn't "do the
        # right thing."
        fn = posixpath.basename(urlparse.urlparse(infile)[2])
    else:
        fn = infile
    return infp, fn


class multi_transform:
    def __init__(self, context, levels=None):
        self.__app = context.app
        baseurl = context.get_baseurl()
        scheme, netloc, path, params, query, frag = urlparse.urlparse(baseurl)
        self.__scheme = scheme
        self.__netloc = string.lower(netloc)
        self.__path = os.path.dirname(path)
        self.__subdocs = []
        self.__max_levels = levels
        self.__level = 0
        self.__docs = {baseurl: 0}

    def __call__(self, url, attrs):
        scheme, netloc, path, params, query, frag = urlparse.urlparse(url)
        if params or query:             # safety restraint
            return url
        netloc = string.lower(netloc)
        if scheme != self.__scheme or netloc != self.__netloc:
            return url
        # check the paths:
        stored_url = urlparse.urlunparse((scheme, netloc, path, '', '', ''))
        if self.__docs.has_key(stored_url):
            return url
        if len(path) < len(self.__path):
            return url
        if path[:len(self.__path)] != self.__path:
            return url
        if (not self.__max_levels) \
           or (self.__max_levels and self.__level < self.__max_levels):
            self.__docs[stored_url] = self.__level + 1
            self.insert(stored_url)
        return url

    def get_subdocs(self):
        return self.__subdocs

    __base_index = None
    def set_basedoc(self, url):
        level = 1
        if self.__docs.has_key(url):
            level = self.__docs[url]
        self.__level = level
        self.__current_base = url
        try:
            self.__base_index = self.__subdocs.index(url)
        except ValueError:
            self.__base_index = None

    def insert(self, url):
        if self.__base_index is not None:
            i = self.__base_index + 1
            scheme, netloc, path, x, y, z = urlparse.urlparse(url)
            basepath = os.path.dirname(path)
            while i < len(self.__subdocs):
                scheme, netloc, path, x, y, z = urlparse.urlparse(
                    self.__subdocs[i])
                path = os.path.dirname(path)
                i = i + 1
                if path != basepath:
                    break
            self.__subdocs.insert(i, url)
            return
        self.__subdocs.append(url)

    def get_level(self, url):
        return self.__docs[url]


class explicit_multi_transform:
    def __init__(self, subdocs):
        self.__subdocs = map(None, subdocs)

    def __call__(self, url, attrs):
        return url

    def get_subdocs(self):
        return map(None, self.__subdocs)

    def set_basedoc(self, url):
        pass

    def get_level(self, url):
        return 1


def usage(settings):
    import printing.paper
    #
    progname = os.path.basename(sys.argv[0])
    print 'Usage:', progname, '[options] [file-or-url]'
    print '    -u: URL for footer'
    print '    -t: title for header'
    print '    -a: toggle anchor footnotes (default is %s)' \
          % _onoff(settings.footnoteflag)
    print '    -U: toggle anchor underlining (default is %s)' \
          % _onoff(settings.underflag)
    print '    -o: orientation; portrait, landscape, or seascape'
    print '    -p: paper size; letter, legal, a4, etc.',
    print '(default is %s)' % settings.papersize
    print '    -f: font size, in points (default is %s/%s)' \
          % settings.get_fontsize()
    print '    -d: turn on debugging'
    print '    -l: logfile for debugging, otherwise stderr'
    print '    -s: toggle "advanced" SGML recognition (default is %s)'\
          % _onoff(settings.strict_parsing)
    print '    -T: size of tab stop in points (default is %s)' \
          % printing.paper.PaperInfo.TabStop
    print '    -P: specify output printer'
    print '    -m: descend tree starting from specified document,'
    print '        printing all HTML documents found'
    print '    -h: this help message'
    print '[file]: file to convert, otherwise from stdin'


def _onoff(bool):
    return bool and "ON" or "OFF"


#  main() & relations....


import BaseApplication


class Application(BaseApplication.BaseApplication):
    def __init__(self, prefs=None):
        BaseApplication.BaseApplication.__init__(self, prefs)
        import GlobalHistory
        self.global_history = GlobalHistory.GlobalHistory(self, readonly=1)

    def exception_dialog(self, message='', *args):
        traceback.print_exc()
        if message:
            sys.stderr.write(message + "\n")


def main():
    app = Application()
    try:
        run(app)
    except KeyboardInterrupt:
        if utils.get_debugging():
            app.exception_dialog()
        sys.exit(1)


def profile_main(n=18):
    import profile, pstats
    print "Running under profiler...."
    profiler = profile.Profile()
    try:
        profiler.runctx('main()', globals(), locals())
    finally:
        sys.stdout = logfile
        profiler.dump_stats('@html2ps.prof')
        p = pstats.Stats('@html2ps.prof')
        p.strip_dirs().sort_stats('time').print_stats(n)
        p.print_callers(n)
        p.sort_stats('cum').print_stats(n)
