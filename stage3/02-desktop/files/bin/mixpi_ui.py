"""Shared GTK 3 controls for the 800 × 480 Mix Pi touchscreen."""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

CSS = b"""
* { font-family: 'DejaVu Sans', sans-serif; font-size: 16px; }
window, dialog, menu { background: #101216; color: #f4f6f8; }
label { color: #f4f6f8; }
.title { font-size: 24px; font-weight: bold; }
.eyebrow { font-size: 12px; font-weight: bold; color: #aeb8c4; }
.muted { color: #b7c1cd; font-size: 14px; }
.panel { background: #1b2027; border: 1px solid #46515e; border-radius: 6px; padding: 8px; }
.status { color: #ffbb55; font-weight: bold; }
.success { color: #79dfac; }
.error { color: #ffaaaa; }
button { background-image: none; background-color: #272e38; color: #f4f6f8;
  border: 1px solid #657383; border-radius: 5px; box-shadow: none;
  text-shadow: none; min-height: 44px; padding: 0 12px; }
button:hover { background-color: #364251; }
button:active { background-color: #445367; }
button:focus { outline: 2px solid #75cfff; outline-offset: -4px; }
button.primary { background-color: #ffbb55; color: #101216; border-color: #ffbb55; font-weight: bold; }
button.primary label { color: #101216; }
button.primary:hover { background-color: #ffd08a; }
button:disabled { background-color: #1b2027; border-color: #3c4550; color: #85909d; }
button:disabled label { color: #85909d; }
button.tile { min-height: 60px; padding: 6px 12px; }
button.tile label { font-weight: bold; }
button.tile .muted { font-size: 13px; font-weight: normal; }
combobox button { min-height: 44px; }
combobox cellview { color: #f4f6f8; }
menuitem { min-height: 44px; padding: 0 12px; }
menuitem:hover { background: #364251; }
progressbar trough { min-height: 10px; background: #303945; border-radius: 3px; }
progressbar progress { min-height: 10px; background: #ffbb55; border-radius: 3px; }
progressbar text { color: #f4f6f8; font-size: 14px; }
scrollbar slider { min-width: 14px; min-height: 32px; background: #657383; }
separator { background: #46515e; min-height: 1px; }
"""


def style(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def label(text="", kind=None, wrap=False):
    widget = Gtk.Label(label=text, xalign=0)
    if kind:
        style(widget, kind)
    if wrap:
        widget.set_line_wrap(True)
        widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        widget.set_max_width_chars(1)
        widget.set_hexpand(True)
    return widget


def compact_label(text="", kind=None):
    widget = label(text, kind)
    widget.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    widget.set_max_width_chars(1)
    widget.set_hexpand(True)
    return widget


def button(text, callback, primary=False):
    widget = Gtk.Button(label=text)
    widget.set_size_request(-1, 48)
    widget.connect("clicked", callback)
    if primary:
        style(widget, "primary")
    return widget


def tile(title, description, callback):
    widget = style(button("", callback), "tile")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.pack_start(label(title), False, False, 0)
    box.pack_start(label(description, "muted", wrap=True), False, False, 0)
    child = widget.get_child()
    if child is not None:
        widget.remove(child)
    widget.add(box)
    widget.get_accessible().set_name(title)
    return widget


def panel():
    return style(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4), "panel")


def shell(application, title, section):
    window = Gtk.ApplicationWindow(application=application, title="Mix Pi · " + title)
    window.set_default_size(800, 412)
    window.set_border_width(12)
    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    window.add(root)
    header = Gtk.Box(spacing=12)
    header.pack_start(label(title, "title"), True, True, 0)
    header.pack_end(label("MIX PI  /  " + section, "eyebrow"), False, False, 0)
    root.pack_start(header, False, False, 0)
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    scroller.add(body)
    root.pack_start(scroller, True, True, 0)
    footer = Gtk.Box(spacing=8)
    root.pack_end(footer, False, False, 0)
    return window, body, footer


def message(window, title, detail, confirm=None):
    dialog = Gtk.MessageDialog(transient_for=window, modal=True,
        message_type=Gtk.MessageType.QUESTION if confirm else Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.NONE, text=title)
    dialog.set_default_size(620, -1)
    dialog.format_secondary_text(detail)
    if confirm:
        dialog.add_button("Keep playing", Gtk.ResponseType.CANCEL)
        style(dialog.add_button(confirm, Gtk.ResponseType.OK), "primary")
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
    else:
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
    response = dialog.run()
    dialog.destroy()
    return response == Gtk.ResponseType.OK
