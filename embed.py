#! /usr/bin/env python

import grail

def setup(display=None):
    if display:
        grail.main(["--display", display])
    else:
        grail.main([])

def getBrowser(**kw):
    try:
        if grail.app.browsers:
            return grail.app.browsers[0]
    except AttributeError:		# grail.app doesn't exist yet
        return None
    prefs = grail.GrailPrefs.AllPreferences()
    geometry = prefs.Get('browser', 'initial-geometry')
    from grail import Browser
    return Browser.Browser(grail.app.root, grail.app, geometry=geometry) 

if __name__ == '__main__':
    setup()
    b = getBrowser()
    b.load('grail:data/about.html')
    grail.app.go()
