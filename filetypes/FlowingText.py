"""text/plain variant that implements the format=flowed variant.

This variant is documented in the internet draft draft-gellens-format-01.txt,
dated 30 October 1998 (work in progress).

Future versions of this draft may change substantially, or it may be dropped
completely.

The 'quoted' feature is not implemented at this time.
"""

__version__ = '$Revision: 2.4 $'


import formatter
import string

from formatter import AS_IS


class FlowingTextParser:
    buffer = ''
    flowing = 0
    signature = 0

    def __init__(self, viewer, reload=0):
        self.viewer = viewer
        self.formatter = formatter.AbstractFormatter(viewer)
        self.set_flow(1)

    def feed(self, data):
        data = self.buffer + data
        self.buffer = ''
        if self.signature:
            self.send_data(data)
        else:
            lines = string.split(data, '\n')
            if lines:
                self.buffer = lines[-1]
                for line in lines[:-1]:
                    if line == '-- ':
                        self.signature = 1
                        self.set_flow(0)
                    if self.signature:
                        self.send_data(line + '\n')
                        continue
                    if len(string.rstrip(line)) == (len(line) - 1) \
                       and line[-1] == ' ':
                        self.set_flow(1)
                        self.send_data(line + '\n')
                    else:
                        self.set_flow(0)
                        self.send_data(line + '\n')

    def close(self):
        self.send_data(self.buffer)

    def send_data(self, data):
        if self.flowing:
            self.formatter.add_flowing_data(data)
        else:
            self.formatter.add_literal_data(data)

    def set_flow(self, flow):
        flow = not not flow
        if self.flowing != flow:
            if self.flowing:
                self.formatter.add_line_break()
            self.flowing = flow
            self.viewer.new_font((AS_IS, AS_IS, AS_IS, not flow))
