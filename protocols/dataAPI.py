from Assert import Assert
import nullAPI
import string


class data_access(nullAPI.null_access):
    def __init__(self, url, method, params):
        if method != "GET":
            raise IOError, \
                  "'data:' scheme does not support the %s method" % method
        self.state = nullAPI.META
        self.__ctype, self.__data = parse(url)

    def getmeta(self):
        Assert(self.state == nullAPI.META)
        self.state = nullAPI.DATA
        headers = {"content-type": self.__ctype,
                   "content-length": `len(self.__data)`,
                   }
        if self.__data:
            return 200, "Ready", headers
        return 204, "No content", headers

    def polldata(self):
        Assert(self.state in (nullAPI.META, nullAPI.DATA))
        return "Ready", 1

    def getdata(self, maxbytes):
        Assert(self.state == nullAPI.DATA)
        split_pos = min(maxbytes, len(self.__data))
        data = self.__data[:split_pos]
        self.__data = self.__data[split_pos:]
        if not data:
            self.state = nullAPI.DONE
        return data


def parse(url):
    ctype, data, encoding = None, "", "raw"
    pos = string.find(url, ';')
    if pos >= 0:
        ctype = string.lower(string.strip(url[:pos]))
        if ctype:
            ctype = ctype
        url = url[pos + 1:]
    pos = string.find(url, ',')
    if pos >= 0:
        encoding = string.lower(string.strip(url[:pos]))
        url = url[pos + 1:]
    data = url
    if data and encoding == "base64":
        import base64
        data = base64.decodestring(data)
    return (ctype or "text/plain"), data
