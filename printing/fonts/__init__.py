"""PostScript font metrics package.

This package is used by the html2ps.py standalone script, and Grail's
PostScript printing dialog to gather the correct font metrics for
printing.

Exported functions:

font_from_name(psfontname)
        returns a PSFont derived object for metrics calculation

"""

import regsub

def font_from_name(psfontname):
    # PostScript fonts use dash delimiters, while Python module names
    # use underscores.
    modulename = 'PSFont_' + regsub.gsub('-', '_', psfontname)
    # no need to do any caching since the import mechanism does that
    # for us!
    module = __import__(modulename, globals(), locals())
    return module.font

# Need different code here for ni than for 1.5 packages
try:
    __ # This fails with 1.5 packages, succeeds when using ni
except NameError:
    # 1.5 packages -- nothing more to do
    pass
else:
    # Backward compatible solution for ni
    for name in ['font_from_name', '__doc__']:
        setattr(__, name, vars()[name])
