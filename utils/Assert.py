# Trivial assertion function

class AssertionError:
    def __init__(self, msg):
    	self.msg = msg
    def __str__(self):
    	return str(self.msg)

def Assert(cond, msg="assertion failed (see traceback)"):
    if not cond: raise AssertionError(msg)
