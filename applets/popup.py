from Tkinter import *

class popup:

    def __init__(self, master,
                 image="images/grailbut.gif",
                 text="Nobody expects the Spanish Inquisition!",
                 cursor="cross"):
        self.master = master
        self.popup_menu = None
        self.master.bind("<Button-1>", self.popup)
        self.master['cursor'] = cursor
        if image:
            self.image = self.master.grail_context.get_async_image(image)
        else:
            self.image = None
        self.text = text

    def popup(self, event):
        if not self.popup_menu:
            self.create_popup_menu()
        self.popup_menu.tk_popup(event.x_root, event.y_root)

    def create_popup_menu(self):
        self.popup_menu = menu = Menu(self.master, tearoff=0)
        if self.image and self.image.loaded:
            menu.add_command(image=self.image)
        else:
            menu.add_command(label=self.text)
