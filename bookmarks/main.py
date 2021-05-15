"""%(program)s -- Bookmark management utility.

usage:  %(program)s [options] infile [outfile]
        %(program)s -g|--guess-type [files...]

Options:
    -h, --help	        Display this help message.
    -g, --guess-type    Guess type of one or more bookmark files, or stdin.
    -f, --format        Specify bookmark output format ('html' or 'xbel');
                        default is 'html'.
    -x                  Strip all personal information fields from output.
    --export fields     Strip specified personal fields from the output;
                        'fields' is a comma-separated list of fields.  The
                        field names are 'added', 'modified' and 'visited'.
    --scrape            Attempt to parse the input file as HTML and extract
                        links into a new bookmark file (preliminary).  The
                        input may be a URL instead of a file name.
    --search keywords   Search the input for bookmarks and folders which
                        match any of the comma-separated keywords.  Search
                        is case-insensitive.  The entire hierarchical
                        structure above the match node is returned.  If
                        there are no matches, an error is printed to stderr
                        and %(program)s exits with a non-zero return code.

A hyphen (-) may be used as either the input file or the output file to
indicate standard input or standard output, respectively.  If a file is
omitted, the appropriate standard stream is used.
"""


__version__ = '$Revision: 1.5 $'

import bookmarks
import errno
import getopt
import os
import string
import sys


SCRIPT_PREFIX = "bkmk2"


class Options:
    guess_type = 0
    output_format = "html"
    scrape_links = 0
    export = 0
    export_fields = []
    info = 0
    search = 0
    keywords = []
    __export_field_map = {
        "modified": "last_modified",
        "visited": "last_visited",
        "added": "add_date",
        }

    def __init__(self, args):
        s = os.path.splitext(os.path.basename(sys.argv[0]))
        if s[:len(SCRIPT_PREFIX)] == SCRIPT_PREFIX:
            s = s[len(SCRIPT_PREFIX):]
            if valid_output_format(s):
                self.output_format = s
        opts, self.args = getopt.getopt(
            sys.argv[1:], "f:ghisx",
            ["export=", "format=", "guess-type", "help", "info",
             "scrape", "search="])
        for opt, arg in opts:
            if opt in ("-h", "--help"):
                usage()
            elif opt in ("-g", "--guess-type"):
                self.guess_type = 1
            elif opt in ("-f", "--format"):
                if not valid_output_format(arg):
                    usage(2, "unknown output format: " + arg)
                self.output_format = arg
            elif opt in ("-i", "--info"):
                self.info = self.info + 1
            elif opt in ("-s", "--scrape"):
                self.scrape_links = 1
            elif opt == "-x":
                self.export = 1
            elif opt == "--export":
                self.export = 1
                fields = string.split(arg, ",")
                print fields
                for f in fields:
                    fname = self.__export_field_map[f]
                    if not fname in self.export_fields:
                        self.export_fields.append(fname)
            elif opt == "--search":
                map(self.keywords.append, string.split(arg, ","))
                self.search = 1


def valid_output_format(format):
    try:
        bookmarks.get_writer_class(format)
    except ImportError:
        return 0
    else:
        return 1


def main():
    try:
        options = Options(sys.argv[1:])
    except getopt.error, message:
        usage(2, message)
    args = options.args
    if options.guess_type:
        if not args:
            args = ["-"]
        for filename in args:
            guess_bookmarks_type(filename, len(args) != 1)
        return
    if len(args) > 2:
        usage(2, "too many command line arguments")
    while len(args) < 2:
        args.append('-')
    [ifn, ofn] = args
    if ifn == '-':
        infile = sys.stdin
    else:
        try:
            infile = open(ifn, 'rb')    # binary in case it's a binary pickle
        except IOError, (err, message):
            if options.scrape_links:
                # try to open as URL
                import urllib
                infile = urllib.urlopen(ifn)
                baseurl = infile.url
            else:
                error(1, "could not open %s: %s" % (ifn, message))
        else:
            baseurl = "file:" + os.path.join(os.getcwd(), ifn)
    #
    # get the parser class, bypassing completely if the formats are the same
    #
    if options.scrape_links:
        import formats.html_scraper
        parser = formats.html_scraper.Parser(ifn)
        parser.set_baseurl(baseurl)
    else:
        format = bookmarks.get_format(infile)
        if not format:
            error(1, "could not identify input file format")
        parser_class = bookmarks.get_parser_class(format)
        parser = parser_class(ifn)
    #
    # do the real work
    #
    writer_class = bookmarks.get_writer_class(options.output_format)
    parser.feed(infile.read())
    parser.close()
    infile.close()
    root = parser.get_root()
    if options.search:
        import search
        import search.KeywordSearch
        search_options = search.KeywordSearch.KeywordOptions()
        search_options.set_keywords(string.join(options.keywords))
        matcher = search.get_matcher("Keyword", search_options)
        root = search.find_nodes(root, matcher)
        if root is None:
            sys.stderr.write("No matches.\n")
            sys.exit(1)
    writer = writer_class(root)
    if options.export:
        import exporter
        export_options = exporter.ExportOptions()
        for s in options.export_fields:
            setattr(export_options, "remove_" + s, 0)
        walker = exporter.ExportWalker(root, export_options)
        walker.walk()
    if options.info:
        report_info(root)
    else:
        try:
            writer.write_tree(get_outfile(ofn))
        except IOError, (err, msg):
            # Ignore the error if we lost a pipe into another process.
            if err != errno.EPIPE:
                raise


def report_info(root):
    import collection
    coll = collection.Collection(root)
    items = coll.get_type_counts().items()
    items.sort()
    total = 0
    for type, count in items:
        total = total + count
        print "%12s: %5d" % (type, count)
    print "%12s  -----" % ''
    print "%12s: %5d" % ("Total", total)


def guess_bookmarks_type(filename, verbose=0):
    if filename == "-":
        fp = sys.stdin
    else:
        fp = open(filename)
    type = bookmarks.get_format(fp)
    if verbose:
        print "%s: %s" % (filename, type)
    else:
        print type


def get_outfile(ofn):
    if ofn == '-':
        outfile = sys.stdout
    else:
        try:
            outfile = open(ofn, 'w')
        except IOError, (errno, message):
            error(1, "could not open %s: %s" % (ofn, message))
        print "Writing output to", ofn
    return outfile


def usage(err=0, message=''):
    if err:
        sys.stdout = sys.stderr
    program = os.path.basename(sys.argv[0])
    if message:
        print "%s: %s" % (program, message)
        print
    print __doc__ % {"program": program}
    sys.exit(err)


def error(err, message):
    program = os.path.basename(sys.argv[0])
    sys.stderr.write("%s: %s\n" % (program, message))
    sys.exit(err)
