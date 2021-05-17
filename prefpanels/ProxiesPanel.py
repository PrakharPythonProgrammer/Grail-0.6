"""Grail proxy preferences panel."""

__version__ = "$Revision: 1.13 $"

# Base class for the dialog:
import PrefsPanels

from tkinter import *
import grailutil

class ProxiesPanel(PrefsPanels.Framework):
    """Network preferences related to redirection of URL streams."""
    
    # Class var for help button - relative to grail-home-page.
    HELP_URL = "help/prefs/proxies.html"

    def CreateLayout(self, name, frame):
        """create a bunch of widgets that look like a prefs panel."""

        #
        # Set up some frames
        proxy_frame = Frame(frame)
        manual_frame = Frame(proxy_frame)
        manual_right_frame = Frame(manual_frame)
        manual_left_frame = Frame(manual_frame)
        no_proxy_frame = Frame(proxy_frame)

        #
        # Establish some booleans to represent the button states
        self.no_proxy_enabled = IntVar(frame)
        self.manual_proxy_enabled = IntVar(frame)

        #
        # Create top level widgets
        l = Label(proxy_frame, pady=15,
               text="A proxy allows your browser to access the Internet through a Firewall.")

        self.no = Checkbutton(proxy_frame,
               text="Proxy Exceptions List            ",
               variable=self.no_proxy_enabled,
               padx=200, pady=15,
               font='-*-helvetica-bold-o-normal-*-*-120-*-*-*-*-*-*' ,
               command=self.no_switch)
        manual = Checkbutton(proxy_frame,
               text="Manual Proxy Configuration ",
               variable=self.manual_proxy_enabled,
               padx=200, pady=15,
               font='-*-helvetica-bold-o-normal-*-*-120-*-*-*-*-*-*',
               command=self.manual_switch)
        
        self.he = Entry(manual_right_frame, relief=SUNKEN, width=38)
        self.hl = Label(manual_left_frame, relief=FLAT,
               text="HTTP Proxy (http://server:port):")
        self.fe = Entry(manual_right_frame, relief=SUNKEN, width=38)
        self.fl = Label(manual_left_frame, relief=FLAT,
               text=" FTP Proxy (http://server:port):",)

        self.nl = Label(no_proxy_frame, relief=FLAT,
               text="Servers that need no proxy to be reached (www.python.org, .dlib.org):",)
        self.ne = Entry(no_proxy_frame, relief=SUNKEN, width=75)

        #
        # Pack the widgets
        frame.pack(expand=1, fill=X)
        proxy_frame.pack(expand=1, fill=X)
        l.pack(side=TOP)
        manual.pack(side=TOP, expand=1, anchor=CENTER, fill=X)
        manual_frame.pack(side=TOP, expand=1, fill=X)
        self.no.pack(side=TOP, expand=1, anchor=CENTER, fill=X)
        no_proxy_frame.pack(side=TOP, expand=1, fill=X)
        manual_right_frame.pack(side=RIGHT, expand=1, fill=X)
        manual_left_frame.pack(side=LEFT, expand=1, fill=X)
        self.nl.pack(side=TOP, expand=1, fill=X)
        self.ne.pack(side=BOTTOM, expand=1, fill=X)
        self.he.pack(side=TOP, expand=1, fill=X)
        self.hl.pack(side=TOP, expand=1, fill=X)
        self.fe.pack(side=TOP, expand=1, fill=X)
        self.fl.pack(side=TOP, expand=1, fill=X)

        #
        # Set the initial GUI state based on prefs
        self.register_prefs_UI()
        manual_proxy_enabled = grailutil.pref_or_getenv('manual_proxy_enabled',
                                                        type_name='int')
        if manual_proxy_enabled == 1:
            self.manual_proxy_enabled.set(1)
        else:
            self.manual_proxy_enabled.set(0)
        no_proxy_enabled = grailutil.pref_or_getenv('no_proxy_enabled', type_name='int')
        if no_proxy_enabled == 1:
            self.no_proxy_enabled.set(1)
        else:
            self.no_proxy_enabled.set(0)
        self.UpdateLayout()

    def UpdateLayout(self):
        """This method gets called by the prefs framework when
        (for example) ' Factory Defaults'  or 'Revert' get pressed.
        It allows updates to the Panel to reflect state changed by
        the framework."""
        
        if self.manual_proxy_enabled.get() == -1:
            self.manual_proxy_enabled.set(0)
        if self.no_proxy_enabled.get() == -1:
            self.no_proxy_enabled.set(0)

        self.manual_switch()
        

    def register_prefs_UI(self):
        """Associate the UI widgets with the Preferences variables."""

        self.RegisterUI('proxies', 'no_proxy_enabled', 'int',
                        self.no_proxy_enabled.get,
                        self.no_proxy_enabled.set)

        self.RegisterUI('proxies', 'manual_proxy_enabled', 'int',
                        self.manual_proxy_enabled.get,
                        self.manual_proxy_enabled.set)

        self.RegisterUI('proxies', 'no_proxy', 'string',
                        self.ne.get, self.widget_set_func(self.ne))
        self.RegisterUI('proxies', 'ftp_proxy', 'string',
                        self.fe.get, self.widget_set_func(self.fe))
        self.RegisterUI('proxies', 'http_proxy', 'string',
                        self.he.get, self.widget_set_func(self.he))


    def no_switch(self):
        """ Set the state of the No Proxy Configuration controls
        to DISABLED if the Checkbutton is not set."""

        if self.no_proxy_enabled.get():
            self.nl.config(foreground='black')
            self.ne.config(state=NORMAL)
        else:
            self.nl.config(foreground='grey')
            self.ne.config(state=DISABLED)
        
    def manual_switch(self):
        """ Set the state of the Manual Proxy Configuration controls
        to DISABLED if the Checkbutton is no set."""

        if self.manual_proxy_enabled.get():
            self.hl.config(foreground='black')
            self.fl.config(foreground='black')
            self.he.config(state=NORMAL)
            self.fe.config(state=NORMAL)
            self.no.config(state=NORMAL)
            self.no_switch()
        else:
            self.hl.config(foreground='grey')
            self.fl.config(foreground='grey')
            self.he.config(state=DISABLED)
            self.fe.config(state=DISABLED)
            #
            # We also disable No Proxy
            self.no_proxy_enabled.set(0)
            self.nl.config(foreground='grey')
            self.ne.config(state=DISABLED)
            self.no.config(state=DISABLED)
            
            
