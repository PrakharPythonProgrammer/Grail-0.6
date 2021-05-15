"""HTML <FORM> tag support (and <INPUT>, etc.)."""

ATTRIBUTES_AS_KEYWORDS = 1

import string
from Tkinter import *
import urllib
import tktools
import ImageWindow

# ------ Forms

URLENCODED = "application/x-www-form-urlencoded"
FORM_DATA = "multipart/form-data"

def start_form(parser, attrs):
    try:
        action = attrs['action']
    except KeyError:
        action = ''
    try:
        method = attrs['method']
    except KeyError:
        method = ''
    try:
        enctype = attrs['enctype']
    except KeyError:
        enctype = URLENCODED
    try:
        target = attrs['target']
    except KeyError:
        target = ''
    form_bgn(parser, action, method, enctype, target)

def end_form(parser):
    form_end(parser)

def do_input(parser, attrs):
    try:
        type = string.lower(attrs['type'])
        del attrs['type']
    except KeyError:
        type = ''
    handle_input(parser, type, attrs)

def start_select(parser, attrs):
    try:
        name = attrs['name']
    except KeyError:
        name = ''
    try:
        size = string.atoi(attrs['size'])
    except (KeyError, string.atoi_error):
        size = 0
    multiple = attrs.has_key('multiple')
    select_bgn(parser, name, size, multiple)

def end_select(parser):
    select_end(parser)

def do_option(parser, attrs):
    try:
        value = attrs['value']
    except KeyError:
        value = ''
    selected = attrs.has_key('selected')
    handle_option(parser, value, selected)

def start_textarea(parser, attrs):
    try:
        name = attrs['name']
    except KeyError:
        name = ''
    try:
        rows = string.atoi(attrs['rows'])
    except (KeyError, string.atoi_error):
        rows = 0
    try:
        cols = string.atoi(attrs['cols'])
    except (KeyError, string.atoi_error):
        cols = 0
    textarea_bgn(parser, name, rows, cols)

def end_textarea(parser):
    textarea_end(parser)

# --- Hooks for forms

def form_bgn(parser, action, method, enctype, target):
    if not hasattr(parser, 'form_stack'):
        parser.form_stack = []
        parser.forms = []
    fi = FormInfo(parser, action, method, enctype, target)
    parser.form_stack.append(fi)

def form_end(parser):
    fi = get_forminfo(parser)
    if fi:
        del parser.form_stack[-1]
        parser.forms.append(fi)
        if not hasattr(parser.context, 'forms'):
            parser.context.forms = []
        parser.context.forms.append(fi)
        fi.done()

def handle_input(parser, type, options):
    fi = get_forminfo(parser)
    if fi: fi.do_input(type, options, parser.viewer.text['background'])

def select_bgn(parser, name, size, multiple):
    fi = get_forminfo(parser)
    if fi: fi.start_select(name, size, multiple)

def select_end(parser):
    fi = get_forminfo(parser)
    if fi: fi.end_select()

def handle_option(parser, value, selected):
    fi = get_forminfo(parser)
    if fi: fi.do_option(value, selected)

def textarea_bgn(parser, name, rows, cols):
    fi = get_forminfo(parser)
    if fi: fi.start_textarea(name, rows, cols)

def textarea_end(parser):
    fi = get_forminfo(parser)
    if fi: fi.end_textarea()

# --- Form state tacked on the parser

def get_forminfo(parser):
    if hasattr(parser, 'form_stack'):
        if parser.form_stack:
            return parser.form_stack[-1]
    return None

class FormInfo:

    def __init__(self, parser, action, method, enctype, target):
        self.parser = parser
        self.action = action or ''
        self.method = method or 'get'
        self.enctype = enctype
        self.target = target
        self.context = parser.context
        self.viewer = self.context.viewer
        self.inputs = []
        self.radios = {}
        self.select = None
        self.textarea = None
        self.parser.implied_end_p()
        self.parser.formatter.end_paragraph(1)
        # gather cached form data if we've been to this page before
        formdata_list = self.context.get_formdata()
        if formdata_list and len(formdata_list) > len(parser.forms):
            self.formdata = formdata_list[len(parser.forms)]
        else:
            self.formdata = []

    def __del__(self):
        pass                            # XXX

    def get(self):
        state = []
        for i in self.inputs:
            value = i.getstate()
            name = hasattr(i, 'name') and i.name or ''
            class_ = i.__class__
            state.append((class_, name, value))
        return state

    def done(self):                     # Called for </FORM>
        if self.parser:
            self.parser.formatter.end_paragraph(0)
        self.parser = None
        # only restore the form data if it matches, as best as can be
        # determined, the current layout of the form.  Otherwise, just
        # reset the form.
        reset = 1
        if self.formdata and len(self.formdata) == len(self.inputs):
            for i in self.inputs:
                class_, name, value = self.formdata[0]
                iclass = i.__class__
                iname = hasattr(i, 'name') and i.name or ''
                del self.formdata[0]
                if class_ == iclass and name == iname:
                    i.set(value)
                else:
                    break
            else:
                reset = None
        if reset:
            self.reset_command()

    def do_input(self, type, options, bgcolor):
        type = string.lower(type) or 'text'
        classname = 'Input' + string.upper(type[0]) + type[1:]
        if hasattr(self, classname):
            klass = getattr(self, classname)
            instance = klass(self, options, bgcolor)
        else:
            print "*** Form with <INPUT TYPE=%s> not supported ***" % type

    def submit_command(self):
        enctype = string.lower(self.enctype)
        method = string.lower(self.method)
        if method not in ('get', 'post'):
            print "*** Form with unknown method:", `method`
            print "Default to method=GET"
            method = 'get'
        if method == 'get' and enctype == FORM_DATA:
            print "*** Form with method=GET, enctype=form-data not supported"
            print "Default to enctype=urlencoded"
            enctype = URLENCODED
        if enctype not in (URLENCODED, FORM_DATA):
            print "*** Form with unknown enctype:", `enctype`
            print "Default to urlencoded"
            enctype = URLENCODED
        data = ''
        if enctype == URLENCODED:
            data = self.make_urlencoded_data()
        elif enctype == FORM_DATA and method == 'post':
            ctype, data = self.make_form_data()
        if method == 'get':
            url = self.action + '?' + data
            self.context.follow(url, target=self.target)
        elif method == 'post':
            if enctype == FORM_DATA:
                enctype = ctype
            params = {"Content-type": enctype}
            if enctype == URLENCODED:
                params["Content-length"] = `len(data)`
            self.viewer.context.post(self.action, data, params, self.target)

    def make_urlencoded_data(self):
        data = ''
        for i in self.inputs:
            if not i.name: continue
            v = i.get()
            if v:
                ### images need to return two different values
                ### there doesn't seem to be an easy & elegant way to
                ###do this
                if type(v) == type(()):
                    if None in v: continue
                    s = '&' + quote(i.name + '.x') + '=' + quote(str(v[0]))
                    data = data + s
                    s = '&' + quote(i.name + '.y') + '=' + quote(str(v[1]))
                    data = data + s
                else:
                    if type(v) != type([]):
                        v = [v]
                    for vv in v:
                        s = '&' + quote(i.name) + '=' + quote(vv)
                        data = data + s
        return data[1:]

    def make_form_data(self):
        import StringIO
        import MimeWriter
        fp = StringIO.StringIO()
        mw = MimeWriter.MimeWriter(fp)
        mw.startmultipartbody("form-data")
        for i in self.inputs:
            if not i.name: continue
            v = i.get()
            if not v: continue
            if type(v) == type(()):
                # XXX Argh!  Have to do it twice, for each coordinate
                if None in v: continue
                disp = 'form-data; name="%s.x"' % i.name
                sw = mw.nextpart()
                sw.addheader("Content-Disposition", disp)
                body = sw.startbody("text/plain")
                body.write(str(v[0]))
                disp = 'form-data; name="%s.y"' % i.name
                sw = mw.nextpart()
                sw.addheader("Content-Disposition", disp)
                body = sw.startbody("text/plain")
                body.write(str(v[1]))
                continue
            disp = 'form-data; name="%s"' % i.name
            data = None
            if i.__class__.__name__ == 'InputFile':
                try:
                    f = open(v)
                    data = f.read()
                    f.close()
                except IOError, msg:
                    print "IOError:", msg
                else:
                    disp = disp + '; filename="%s"' % v
            sw = mw.nextpart()
            sw.addheader("Content-Disposition", disp)
            if data is not None:
                sw.addheader("Content-Length", str(len(data)))
                body = sw.startbody("text/plain")
                body.write(data)
            else:
                body = sw.startbody("text/plain")
                body.write(v)
        mw.lastpart()
        fp.seek(0)
        import rfc822
        headers = rfc822.Message(fp)
        ctype = headers['content-type']
        ctype = string.join(string.split(ctype)) # Get rid of newlines
        data = fp.read()
        return ctype, data

    def reset_command(self):
        for i in self.inputs:
            i.reset()

    def start_select(self, name, size, multiple):
        self.select = Select(self, name, size, multiple)

    def end_select(self):
        if self.select:
            self.select.done()
            self.select = None

    def do_option(self, value, selected):
        if self.select:
            self.select.do_option(value, selected)

    def start_textarea(self, name, rows, cols):
        self.textarea = Textarea(self, name, rows, cols)

    def end_textarea(self):
        if self.textarea:
            self.textarea.done()
            self.textarea = None

    # The following classes are nested so we can use getattr(self, 'Input...')

    class Input:

        name = ''
        value = ''

        def __init__(self, fi, options, bgcolor):
            self.fi = fi
            self.viewer = fi.viewer
            self.bgcolor = bgcolor
            self.options = options
            self.getopt('name')
            self.getopt('value')
            self.getoptions()
            self.w = None
            self.setup()
            self.reset()
            self.fi.inputs.append(self)
            if self.w:
                self.fi.parser.add_subwindow(self.w)

        def getoptions(self):
            pass

        def setup(self):
            pass

        def reset(self):
            pass

        def get(self):
            return None

        def set(self, value):
            pass

        def getopt(self, key):
            if self.options.has_key(key):
                setattr(self, key, self.options[key])

        def getflagopt(self, key):
            if self.options.has_key(key):
                setattr(self, key, 1)

        def getstate(self):
            # Get raw state for form caching -- default same as get()
            return self.get()

    class InputText(Input):

        size = 0
        maxlength = None
        show = None

        def getoptions(self):
            self.getopt('size')

        def setup(self):
            self.w = self.entry = Entry(self.viewer.text,
                                        highlightbackground=self.bgcolor)
            self.setup_entry()

        def setup_entry(self):
            self.entry.bind('<Return>', self.return_event)
            if self.size:
                size = self.size
                i = string.find(size, ',')
                if i >= 0: size = size[:i]
                try:
                    width = string.atoi(size)
                except string.atoi_error:
                    pass
                else:
                    self.entry['width'] = width
            if self.show:
                self.entry['show'] = self.show

        def reset(self):
            self.entry.delete(0, END)
            self.entry.insert(0, self.value)

        def get(self):
            return self.entry.get()

        def set(self, value):
            text = ''
            if type(value) == type(''):
                text = value
            elif type(value) == type([]) and len(value) > 0:
                text = value[0]
                del value[0]
            self.entry.delete(0, END)
            self.entry.insert(0, text)

        def return_event(self, event):
            self.fi.submit_command()

    class InputPassword(InputText):

        show = '*'

    class InputCheckbox(Input):

        checked = 0
        value = 'on'

        def getoptions(self):
            self.getflagopt('checked')

        def setup(self):
            self.var = StringVar(self.viewer.text)
            self.w = Checkbutton(self.viewer.text, variable=self.var,
                                 offvalue='', onvalue=self.value,
                                 highlightbackground=self.bgcolor)

        def reset(self):
            self.var.set(self.checked and self.value or '')

        def set(self, value):
            self.var.set(value)

        def get(self):
            return self.var.get()

    class InputRadio(InputCheckbox):

        def setup(self):
            if not self.fi.radios.has_key(self.name):
                self.fi.radios[self.name] = StringVar(self.viewer.text)
                self.first = 1
            else:
                self.first = 0
            self.var = self.fi.radios[self.name]
            #
            # N.B. The HTML 2.0 spec is explicit in its description of
            # what user agents should do when no radio elements are
            # CHECKED.  See section 8.1.2.4.  But because Netscape and
            # Mosaic ignore this, many people consider the spec
            # broken.  If you want to be pedantic, uncomment these two
            # lines.  With these lines commented out, Grail uses the
            # same liberal interpretation that those other browsers
            # employ.
            #
            from __main__ import app
            strict = app.prefs.GetBoolean('parsing-html', 'strict')
            if strict and self.first:
                self.var.set(self.value)
            self.w = Radiobutton(self.viewer.text, variable=self.var,
                                 value=self.value, background=self.bgcolor,
                                 activebackground=self.bgcolor,
                                 highlightbackground=self.bgcolor)

        def reset(self):
            from __main__ import app
            strict = app.prefs.GetBoolean('parsing-html', 'strict')
            if not strict and self.first:
                self.var.set('')
            if self.checked:
                self.var.set(self.value)

        def get(self):
            if self.first:
                return self.var.get()
            else:
                return None

        def getstate(self):
            # Get raw state for form caching
            return self.var.get()

    class InputHidden(Input):

        def get(self):
            return self.value

    class InputImage(Input):

        value = "Image"
        src = None
        alt = '(image)'
        width = 0
        height = 0
        border = 2
        align = ''
        value = (None,None)

        def setup(self):
            self.getopt('alt')
            self.getopt('src')
            self.getopt('width')
            self.getopt('height')
            self.getopt('border')
            self.w = InputImageWindow(self.viewer, self.src, self.alt,
                                      self.align, self.width,
                                      self.height, self.border,
                                      self.set_value_and_submit)

        def get(self):
            return self.value

        def set_value_and_submit(self, event):
            self.value = (event.x, event.y)
            self.fi.submit_command()

    class InputSubmit(Input):

        value = "Submit"

        def setup(self):
            self.w = Button(self.viewer.text,
                            text=self.value,
                            command=self.submit_command,
                            highlightbackground=self.bgcolor)
            self.w.bind("<Enter>", self.enter)
            self.w.bind("<Leave>", self.leave)

        def get(self):
            if self.w['state'] == ACTIVE:
                return self.value
            else:
                return None

        def enter(self, event):
            message = self.fi.action or "???"
            if self.fi.target:
                message = message + " in " + self.fi.target
            self.viewer.enter_message(message)

        def leave(self, event):
            self.viewer.leave_message()

        def submit_command(self):
            self.viewer.leave_message()
            self.fi.submit_command()

    class InputReset(Input):

        value = "Reset"

        def setup(self):
            self.w = Button(self.viewer.text,
                            text=self.value,
                            command=self.fi.reset_command,
                            highlightbackground=self.bgcolor)

    class InputFile(InputText):

        def setup(self):
            self.w = Frame(self.viewer.text, background=self.bgcolor)
            self.entry = Entry(self.w, highlightbackground=self.bgcolor)
            self.entry.pack(side=LEFT)
            self.setup_entry()
            self.browse = Button(self.w, text="Browse...",
                                 command=self.browse_command,
                                 highlightbackground=self.bgcolor)
            self.browse.pack(side=RIGHT)

        def reset(self):
            # Ignore the initial value from the HTML form.
            # It is a security hazard.
            self.entry.delete(0, END)

        def browse_command(self):
            import FileDialog
            fd = FileDialog.LoadFileDialog(self.browse)
            filename = fd.go(self.entry.get(), key="load")
            if filename:
                self.set(filename)


class Select:

    def __init__(self, fi, name, size, multiple):
        self.fi = fi
        self.viewer = fi.viewer
        self.bgcolor = fi.parser.viewer.text["background"]
        self.parser = fi.parser
        self.name = name
        self.size = size
        self.multiple = multiple
        self.option = None
        self.options = []
        self.parser.save_bgn()

    def done(self):
        self.end_option()
        if not len(self.options):
            self.w = None
            return
        any = wid = 0
        for v, s, t in self.options:
            if s: any = 1
            wid = max(wid, len(t))
        if not any and not self.multiple:
            v, s, t = self.options[0]
            self.options[0] = v, 1, t
        size = self.size
        if size <= 0:
            if self.multiple: size = 4
            else: size = 1
        #size = min(len(self.options), size)
        if size == 1 and not self.multiple:
            self.make_menu(wid)
        else:
            self.make_list(size)

    def make_menu(self, width):
        self.v = StringVar(self.viewer.text)
        self.v.set(self.name)
        values = tuple(map(lambda (v,s,t): t, self.options))
        self.w = apply(OptionMenu,
                       (self.viewer.text, self.v) + values)
        self.w["width"] = width
        self.w["highlightbackground"] = self.bgcolor
        self.reset_menu()
        self.fi.inputs.append(self)
        self.parser.add_subwindow(self.w)

    def make_list(self, size):
        self.v = None
        needvbar = len(self.options) > size
        self.w, self.frame = tktools.make_list_box(self.viewer.text,
                                                   height=size,
                                                   vbar=needvbar, pack=0)
        self.w['exportselection'] = 0
        if self.multiple:
            self.w['selectmode'] = 'extended'
        wid = 0
        for v, s, t in self.options:
            wid = max(wid, len(t))
            self.w.insert(END, t)
        self.reset_list()
        self.w['width'] = wid
        self.fi.inputs.append(self)
        self.parser.add_subwindow(self.frame)

    def reset(self):
        if not self.w: return
        if self.v:
            self.reset_menu()
        else:
            self.reset_list()

    def reset_menu(self):
        for v, s, t in self.options:
            if s:
                self.v.set(t)
                break

    def reset_list(self):
        self.w.select_clear(0, END)
        for i in range(len(self.options)):
            v, s, t = self.options[i]
            if s:
                self.w.select_set(i)

    def get(self):
        # debugging
        if not self.w: return None
        if self.v: return self.get_menu()
        else: return self.get_list()

    def getstate(self):
        return self.get()

    def get_menu(self):
        text = self.v.get()
        for v, s, t in self.options:
            if text == t: return v or t
        return None

    def get_list(self):
        list = []
        for i in range(len(self.options)):
            v, s, t = self.options[i]
            if self.w.select_includes(i):
                list.append(v or t)
        return list

    def set(self, value):
        # debugging
        if not self.w: return
        if self.v: self.set_menu(value)
        else: self.set_list(value)

    def set_menu(self, value):
        for v, s, t in self.options:
            if value == (v or t):
                self.v.set(t)
                break

    def set_list(self, value):
        self.w.select_clear(0, END)
        for i in range(len(self.options)):
            v, s, t = self.options[i]
            if (v or t) in value:
                self.w.select_set(i)

    def do_option(self, value, selected):
        self.end_option()
        self.parser.save_bgn()
        self.option = (value, selected)

    def end_option(self):
        data = string.strip(self.parser.save_end())
        if self.option:
            value, selected = self.option
            self.option = None
            self.options.append((value, selected, data))


class Textarea:

    def __init__(self, fi, name, rows, cols):
        self.fi = fi
        self.parser = fi.parser
        self.viewer = fi.viewer
        self.name = name
        self.rows = rows
        self.cols = cols
        self.parser.push_nofill()
        self.parser.save_bgn()

    def done(self):
        data = self.parser.save_end()
        self.parser.pop_nofill()
        if data[:1] == '\n': data = data[1:]
        if data[-1:] == '\n': data = data[:-1]
        self.w, self.frame = tktools.make_text_box(self.viewer.text,
                                                   width=self.cols,
                                                   height=self.rows,
                                                   hbar=1, vbar=1, pack=0)
        self.w['wrap'] = NONE
        self.data = data
        self.reset()
        self.fi.inputs.append(self)
        self.parser.add_subwindow(self.frame)

    def reset(self):
        self.w.delete("1.0", END)
        self.w.insert(END, self.data)

    def get(self):
        return self.w.get("1.0", END)

    def getstate(self):
        return self.get()

    def set(self, value):
        # TBD: Tk text widget `feature' can cause an extra newline to
        # be inserted each time the text is set.
        if value[-1] == '\n': value = value[:-1]
        self.w.delete("1.0", END)
        self.w.insert(END, value)

def quote(s):
    w = string.splitfields(s, ' ')
    w = map(urllib.quote, w)
    return string.joinfields(w, '+')


class InputImageWindow(Frame):
    """A simple image window that never is an imagemap.

    This is mostly a stripped-down version of ImageWindow used for the
    <IMG> tag. I'm assuming that class can't be gotten at here. Am I
    right? 

    The last argument is a function to bind ButtonRelease-{1,3} to.
    """

    def __init__(self, viewer,
                 src, alt, align, width, height, borderwidth, bind_func):
        self.viewer = viewer
        self.context = self.viewer.context
        self.src, self.alt, self.align = src, alt, align
        bg = viewer.text['background']
        borderwidth = borderwidth and int(borderwidth) or 0
        Frame.__init__(self, viewer.text, borderwidth=borderwidth,
                       background=bg)
        self.label = Label(self, text=self.alt, background=bg)
        self.label.pack(fill=BOTH, expand=1)
##      self.pack()
        self.image_loaded = 0
        height = height and int(height) or 0
        width = width and int(width) or 0
        if width > 0 and height > 0:
            self.propagate(0)
            self.config(width=width + 2*borderwidth,
                        height=height + 2*borderwidth)
        self.label.bind('<ButtonRelease-1>', bind_func)
        self.label.bind('<ButtonRelease-3>', bind_func)
        self.image = self.context.get_async_image(self.src)
        if self.image:
            self.label['image'] = self.image

    # may be able to delete this
    def toggle_loading_image(self, event=None):
        if self.image:
            if hasattr(self.image, 'get_load_status'):
                status = self.image.get_load_status()
                if status == 'loading':
                    self.image.stop_loading()
                else:
                    self.image.start_loading(reload=1)
        else:
            print "[no image]"
