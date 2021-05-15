"""File reader class -- read from a URL to a file in the background."""

from BaseReader import BaseReader

class FileReader(BaseReader):

    """File reader class -- read from a URL to a file in the background.

    Derived classes are supposed to override handle_error() and
    handle_done() to specify what should happen next, and possibly
    handle_meta() to decide whether to continue based on the data
    type.

    The methods handle_data() and handle_eof() are implemented at this
    level and should normally be left alone (or extended, not
    overridden).

    Class or instance variable filemode may be set to override the
    file writing mode (default 'wb' -- make sure it's a writing
    mode!).

    """

    filemode = "wb"

    def __init__(self, context, api, filename):
        self.filename = filename
        self.fp = None
        BaseReader.__init__(self, context, api)

    def handle_data(self, data):
        try:
            if self.fp is None:
                self.fp = self.open_file()
            self.fp.write(data)
        except IOError, msg:
            self.stop()
            self.handle_error(-1, "IOError", {'detail': msg})
            return
 
    def open_file(self):
        return open(self.filename, "wb")

    def handle_eof(self):
        if self.fp:
            self.fp.close()
        self.handle_done()

    def handle_done(self):
        pass


class TempFileReader(FileReader):

    """Derived class of FileReader that chooses a temporary file.

    This also supports inserting a filtering pipeline.
    """

    def __init__(self, context, api):
        self.pipeline = None
        import tempfile
        filename = tempfile.mktemp()
        FileReader.__init__(self, context, api, filename)

    def set_pipeline(self, pipeline):
        """New method to select the filter pipeline."""
        self.pipeline = pipeline

    def getfilename(self):
        """New method to return the file name chosen."""
        return self.filename

    def open_file(self):
        if not self.pipeline:
            return FileReader.open_file(self)
        else:
            import os, sys
            if not hasattr(os, 'popen'):
                raise IOError, "pipelines not supported"
            try:
                return os.popen(self.pipeline + ">" + self.filename, "wb")
            except os.error, msg:
                raise IOError, msg, sys.exc_traceback
