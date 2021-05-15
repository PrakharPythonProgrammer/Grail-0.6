from Assert import Assert

META, DATA, DONE = 'META', 'DATA', 'DONE'

class null_access:

    def __init__(self, url, method, params):
        self.state = META

    def pollmeta(self):
        Assert(self.state == META)
        return "Ready", 1

    def getmeta(self):
        Assert(self.state == META)
        self.state = DATA
        return 204, "No content", {}

    def polldata(self):
        Assert(self.state == DATA)
        return "Ready", 1

    def getdata(self, maxbytes):
        Assert(self.state == DATA)
        self.state = DONE
        return ""

    def fileno(self):
        return -1

    def close(self):
        pass
