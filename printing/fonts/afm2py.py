#! /usr/bin/env python

"""Adobe Font Metric conversion script.

This script extracts character width font metrics from Adobe Font
Metric (AFM) files.  Output is suitable for use with Grail's
PostScript printing tools.

Usage: %(program)s [-h] [-d <dir>] <afmfile>

    -h
    --help      -- print this help message

    -d
    --dir <dir> -- directory to write the output file in

    <afmfile>   -- the filename of the file to convert.

Output goes to a file created from the name of the font.  E.g. if the
FontName of the font is Courier-Bold, the output file is named
PSFont_Courier_Bold.py.

"""

import sys
import os
import getopt
import string



program = sys.argv[0]

def usage(status):
    print __doc__ % globals()
    sys.exit(status)


def splitline(line):
    idx = string.find(line, ' ')
    keyword = line[:idx]
    rest = string.strip(line[idx+1:])
    return string.lower(keyword), rest



# Mappings between character names and their ordinal equivalents.

def read_unicode_mapping(filename, dict=None):
    result = dict or {}
    fp = open(filename)
    while 1:
        line = fp.readline()
        if not line:
            break
        line = string.strip(line)
        if line and line[0] == "#":
            continue
        parts = string.splitfields(line, "#")
        if len(parts) != 3:
            continue
        parts[0:1] = string.split(parts[0])
        if len(parts) != 4:
            continue
        unicode = string.atoi(parts[0], 16)
        adobe_name = string.strip(parts[3])
        if unicode < 256 and not result.has_key(adobe_name):
            result[adobe_name] = unicode
    return result

LATIN_1_MAPPING = {
    'copyright': 169,
    }

# TBD: when we support other character sets, we should generalize
# this.  No need to do so now though.
charset = LATIN_1_MAPPING



TEMPLATE = """\
# Character width information for PostScript font `%(fullname)s'
# generated from the Adobe Font Metric file `%(filename)s'.  Adobe
# copyright notice follows:
#
# %(notice)s
#
import PSFont
font = PSFont.PSFont('%(fontname)s', '%(fullname)s',
"""

FORMAT = string.join(['%4d'] * 8, ', ') + ','


def parse(filename, outdir):
    cwidths = [0] * 256
    tdict = {'fontname': '',
             'fullname': '',
             'filename': filename,
             'notice':   '',
             }

    infp = open(filename, 'r')
    while 1:
        line = infp.readline()
        if line == '':
            print 'No character metrics found in file:', filename
            sys.exit(1)
        keyword, rest = splitline(line)
        if keyword in ('fontname', 'fullname', 'notice'):
            tdict[keyword] = rest
        if keyword == 'startcharmetrics':
            break
    else:
        print 'No character metrics found in file:', filename
        sys.exit(1)

    outfile = os.path.join(
        outdir,
        string.join(['PSFont'] + string.split(tdict['fontname'], '-'),
                    '_') + '.py')

    # read the character metrics into the list
    while 1:
        line = infp.readline()
        if line == '':
            break
        keyword, rest = splitline(line)
        if keyword == 'c':
            info = string.split(rest)
            charnum = string.atoi(info[0])
            charname = info[6]
            width = string.atoi(info[3])
            if charset.has_key(charname):
                cwidths[charset[charname]] = width
            elif 0 <= charnum < 256:
                cwidths[charnum] = width

        if keyword == 'endcharmetrics':
            break

    infp.close()

    outfp = open(outfile, 'w')
    oldstdout = sys.stdout
    sys.stdout = outfp
    try:
        print TEMPLATE % tdict,
        print '[',
        for i in range(0, 256, 8):
            if i <> 0:
                print ' ',
            print FORMAT % tuple(cwidths[i:i+8])
        print '])'
    finally:
        sys.stdout = oldstdout

    outfp.close()



def main():
    help = 0
    status = 0

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hd:m:',
                                   ['dir', 'help', 'map'])
    except getopt.error, msg:
        print msg
        usage(1)

    if len(args) <> 1:
        usage(1)

    filename = args[0]
    outdir = '.'
    mapfile = None
    verbose = 0
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help = 1
        elif opt in ('-d', '--dir'):
            outdir = arg
        elif opt in ('-m', '--map'):
            mapfile = arg

    if help:
        usage(status)

    if mapfile:
        read_unicode_mapping(mapfile, LATIN_1_MAPPING)

    parse(filename, outdir)


if __name__ == '__main__':
    main()
