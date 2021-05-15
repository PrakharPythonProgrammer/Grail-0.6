"""Conversions between HTTP time formats and system time.

Loosely modelled after the W3C Reference Library at
<URL:http://www.w3.org/pub/WWW/Library/>.
"""
 
import time
import string

try:
        time.timezone
except AttributeError:
        t = time.time()
        time.timezone = int(time.gmtime(t)[3] - time.localtime(t)[3]) * 3600

_months = { 'jan' : 1, 'feb' : 2, 'mar' : 3, 'apr' : 4,
            'may' : 5, 'jun' : 6, 'jul' : 7, 'aug' : 8,
            'sep' : 9, 'oct' : 10, 'nov' : 11, 'dec' : 12 }

def _month_to_num(month):
    m = string.lower(month)
    return _months[m]

def _2dyear_to_4dyear(yy):
    # what do we do with those darn two-digit years?
    # always assuming 19yy seems a little dangerous
    if (yy < 70):
        return yy + 2000
    else:
        return yy + 1900

def parse(str):
    """Parses time in rfc850, rfc1123, and raw seconds formats. Returns
    seconds since the epoch corrected for timezone.

    rfc850:  Weekday, 00-Mon-00 00:00:00 GMT
    rfc1123: Wkd, 00 Mon 0000 00:00:00 GMT 
    raw: [0-9]+ (defined as seconds since current time)

    Raises ValueError if time can't be parsed.
    """

    # first we need to determine the format
    if ',' in str:
        noday = string.strip(str[string.find(str, ',')+1:])
        if '-' in str:
            # Format...... Weekday, 00-Mon-00 00:00:00 GMT (rfc850)
            mday = string.atoi(noday[0:2])
            mon = _month_to_num(noday[3:6])
            year = _2dyear_to_4dyear(string.atoi(noday[7:9]))
            hour = string.atoi(noday[10:12])
            min = string.atoi(noday[13:15])
            sec = string.atoi(noday[16:18])
        else:
            # Format...... Wkd, 00 Mon 0000 00:00:00 GMT (rfc1123)
            mday = string.atoi(noday[0:2])
            mon = _month_to_num(noday[3:6])
            year = string.atoi(noday[7:11])
            hour = string.atoi(noday[12:14])
            min = string.atoi(noday[15:17])
            sec = string.atoi(noday[18:20])

        gmt = (year, mon, mday, hour, min, sec, 0, 0, 0)
        secs = time.mktime(gmt)
        return secs - time.timezone
    else:
        # could be raw digits
        if str[0] in string.digits:
            return time.time() + string.atoi(str)
        else:
            mon = _month_to_num(str[4:7])
            mday = string.atoi(str[8:10])
            year = string.atoi(str[-4:])
            hour = string.atoi(str[11:13])
            min = string.atoi(str[14:16])
            sec = string.atoi(str[17:19])
            
            ### do we assume this is GMT time or not?
            ### let's assume it is
            gmt = (year, mon, mday, hour, min, sec, 0, 0, 0)
            secs = time.mktime(gmt)
            return secs - time.timezone

def unparse(secs):
    """Turns localtime in seconds since epoch to HTTP time.
    """

    str = time.asctime(time.gmtime(secs))
    # puts the string in asctime() format, must convert 
    day = str[0:3]
    mon = str[4:7]
    mday = string.atoi(str[8:10])
    dtime = str[11:19]
    year = str[20:24]
    return "%s, %02d %s %s %s GMT" % (day, mday, mon, year, dtime)
