"""Framework for allowing flexible access authorization.

To start, this is used by the HTTP api to perform basic access authorization.
"""

from Tkinter import *
import tktools
import string
import urlparse
import base64
import regex

class AuthenticationManager:
    """Handles HTTP access authorization.

    Keeps track of (hostname, realmname) = username:password and hands
    back a set of HTTP headers that should be included in the next
    connection. 

    This handles only basic access authorization at the moment. However,
    the only routine called from outside the module is
    request_credentials, and it is passed a dictionary of http headers
    from the 401 response. This should be flexible enough to
    accomodate other authorization mechanisms.
    """

    def __init__(self, app):
        self.app = app

        # initialize 'basic' storage
        self.basic_realms = {}

    def request_credentials(self, headers):
        # response isa {}

        # first guess the scheme
        if headers.has_key('www-authenticate'):
            # assume it's basic
            headers['realm'] = \
                             self.basic_get_realm(headers['www-authenticate'])
            response = self.basic_credentials(headers)
        else:
            # don't know the scheme
            response = {}

        return response

    def invalidate_credentials(self, headers, credentials):
        if headers.has_key('www-authenticate'):
            # assume it's basic
            headers['realm'] = \
                             self.basic_get_realm(headers['www-authenticate'])
            self.basic_invalidate_credentials(headers, credentials)
        else:
            # don't know about anything other than basic
            pass

    basic_realm = regex.compile('realm="\(.*\)"')

    def basic_get_realm(self,challenge):
        # the actual specification allows for multiple name=value
        # entries seperated by commes, but for basic they don't
        # have any defined value. so don't bother with them.
        if self.basic_realm.search(challenge) < 0:
            return
        realm = self.basic_realm.group(1)
        return realm

    def basic_credentials(self, data):
        response = {}

        if data.has_key('realm') and data.has_key('request-uri'):
            scheme, netloc, path, nil, nil, nil = \
                    urlparse.urlparse(data['request-uri'])
            key = (netloc, data['realm'])
            if self.basic_realms.has_key(key):
                cookie = self.basic_cookie(self.basic_realms[key])
            else:
                passwd = self.basic_user_dialog(data)
                if passwd:
                    self.basic_realms[key] = passwd
                    cookie = self.basic_cookie(passwd)
                else:
                    return {}
            response['Authorization'] = cookie

        return response

    def basic_invalidate_credentials(self, headers, credentials):
        if headers.has_key('realm') and headers.has_key('request-uri'):
            scheme, netloc, path, nil, nil, nil = \
                    urlparse.urlparse(headers['request-uri'])
            key = (netloc, headers['realm'])
            if self.basic_realms.has_key(key):
                test = self.basic_cookie(self.basic_realms[key])
                if test == credentials:
                    del self.basic_realms[key]

    def basic_snoop(self, headers):
        # could watch other requests go by and learn about protection spaces
        pass

    def basic_cookie(self, str):
        return "Basic " + string.strip(base64.encodestring(str))

    def basic_user_dialog(self, data):
        scheme, netloc, path, \
                nil, nil, nil = urlparse.urlparse(data['request-uri'])
        login = LoginDialog(self.app.root, netloc,
                            data['realm'])
        return login.go()
    
    def more_complete_challenge_parse(self):
        # this is Guido's old code from Reader.handle_auth_error
        # it's worth hanging on to in case a future authentication
        # scheme uses more than one field in the challenge
        return

        challenge = headers['www-authenticate']
        # <authscheme> realm="<value>" [, <param>="<value>"] ...
        parts = string.splitfields(challenge, ',')
        p = parts[0]
        i = string.find(p, '=')
        if i < 0: return
        key, value = p[:i], p[i+1:]
        keyparts = string.split(string.lower(key))
        if not(len(keyparts) == 2 and keyparts[1] == 'realm'): return
        authscheme = keyparts[0]
        value = string.strip(value)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '\'"':
            value = value[1:-1]


class LoginDialog:

    def __init__(self, master, netloc, realmvalue):
        self.root = tktools.make_toplevel(master,
                                          title="Authentication Dialog")
        self.prompt = Label(self.root,
                            text="Enter user authentication\nfor %s on %s" %
                            (realmvalue, netloc))
        self.prompt.pack(side=TOP)
        self.user_entry, dummy = tktools.make_form_entry(self.root, "User:")
        self.user_entry.focus_set()
        self.user_entry.bind('<Return>', self.user_return_event)
        self.passwd_entry, dummy = \
                           tktools.make_form_entry(self.root, "Password:")
        self.passwd_entry.config(show="*")
        self.passwd_entry.bind('<Return>', self.ok_command)
        self.ok_button = Button(self.root, text="OK", command=self.ok_command)
        self.ok_button.pack(side=LEFT)
        self.cancel_button = Button(self.root, text="Cancel",
                                    command=self.cancel_command)
        self.cancel_button.pack(side=RIGHT)

        self.user_passwd = None

        tktools.set_transient(self.root, master)

        self.root.grab_set()

    def go(self):
        try:
            self.root.mainloop()
        except SystemExit:
            return self.user_passwd

    def user_return_event(self, event):
        self.passwd_entry.focus_set()

    def ok_command(self, event=None):
        user = string.strip(self.user_entry.get())
        passwd = string.strip(self.passwd_entry.get())
        if not user:
            self.root.bell()
            return
        self.user_passwd = user + ':' + passwd
        self.goaway()

    def cancel_command(self):
        self.user_passwd = None
        self.goaway()

    def goaway(self):
        self.root.destroy()
        raise SystemExit

