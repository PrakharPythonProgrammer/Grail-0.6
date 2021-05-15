"""Printing interface for HTML documents."""

import printing.PSParser

parse_text_html = printing.PSParser.PrintingHTMLParser


def add_options(dialog, settings, top):
    from Tkinter import X
    import tktools
    htmlfr = tktools.make_group_frame(top, "html", "HTML options:", fill=X)
    #  Image printing controls:
    dialog.__imgchecked = dialog.new_checkbox(
	htmlfr, "Print images", settings.imageflag)
    dialog.__greychecked = dialog.new_checkbox(
	htmlfr, "Reduce images to greyscale", settings.greyscale)
    #  Anchor-handling selections:
    dialog.__footnotechecked = dialog.new_checkbox(
	htmlfr, "Footnotes for anchors", settings.footnoteflag)
    dialog.__underchecked = dialog.new_checkbox(
	htmlfr, "Underline anchors", settings.underflag)


def update_settings(dialog, settings):
    settings.footnoteflag = dialog.__footnotechecked.get()
    settings.greyscale = dialog.__greychecked.get()
    settings.imageflag = dialog.__imgchecked.get()
    settings.underflag = dialog.__underchecked.get()
