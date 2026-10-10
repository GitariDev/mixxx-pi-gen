"""Shared GTK 3 controls for the 800 × 480 Mix Pi touchscreen."""
import cairo
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gtk, Pango

CSS = b"""
* { font-family: 'DejaVu Sans', sans-serif; font-size: 16px; }
window, dialog, messagedialog, menu, popover { background: #101216; color: #f4f6f8; }
label { color: #f4f6f8; }
.title { font-size: 24px; font-weight: bold; }
.track { font-size: 20px; font-weight: bold; }
.eyebrow { font-size: 12px; font-weight: bold; color: #aeb8c4; }
.muted { color: #b7c1cd; font-size: 14px; }
.panel { background: #1b2027; border: 1px solid #46515e; border-radius: 6px; padding: 8px; }
.sheet { background: #101216; border: 1px solid #657383; padding: 12px; }
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
button.segment:checked { background-color: #101216; border-color: #ffbb55;
  box-shadow: inset 0 -3px #ffbb55; }
button.segment:checked label { color: #ffbb55; }
button.tile { min-height: 60px; padding: 6px 12px; }
button.tile label { font-weight: bold; }
button.tile .muted { font-size: 13px; font-weight: normal; }
combobox button { min-height: 44px; }
combobox cellview { color: #f4f6f8; }
menuitem { min-height: 44px; padding: 0 12px; }
menuitem:hover { background: #364251; }
popover { border: 1px solid #657383; }
checkbutton { padding: 0 8px; }
checkbutton:hover { background: #364251; }
checkbutton check { min-width: 22px; min-height: 22px; background: #272e38;
  border: 1px solid #aeb8c4; color: #f4f6f8; }
checkbutton check:checked { background: #ffbb55; color: #101216; border-color: #ffbb55; }
checkbutton:disabled label { color: #85909d; }
progressbar trough { min-height: 10px; background: #303945; border-radius: 3px; }
progressbar progress { min-height: 10px; background: #ffbb55; border-radius: 3px; }
progressbar text { color: #f4f6f8; font-size: 14px; }
scale { min-height: 44px; padding: 0 4px; }
scale trough { min-height: 10px; background: #303945; border: none; border-radius: 3px; }
scale highlight { min-height: 10px; background: #ffbb55; border: none; border-radius: 3px; }
scale slider { min-width: 32px; min-height: 32px; margin: -12px; background: #f4f6f8;
  border: 1px solid #657383; border-radius: 16px; box-shadow: none; }
scale:disabled highlight { background: #657383; }
scale:disabled slider { background: #85909d; }
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


def shell(application, title, section, header_end=None):
    window = Gtk.ApplicationWindow(application=application, title="Mix Pi · " + title)
    window.set_default_size(800, 412)
    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    root.set_border_width(12)
    # The overlay lets backdrop() cover the whole screen behind a sheet.
    overlay = Gtk.Overlay()
    overlay.add(root)
    window.add(overlay)
    header = Gtk.Box(spacing=12)
    header.pack_start(label(title, "title"), True, True, 0)
    header.pack_end(header_end or label("MIX PI  /  " + section, "eyebrow"), False, False, 0)
    root.pack_start(header, False, False, 0)
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    scroller.add(body)
    root.pack_start(scroller, True, True, 0)
    footer = Gtk.Box(spacing=8)
    root.pack_end(footer, False, False, 0)
    return window, body, footer


def backdrop(window):
    """Cover a shell window with a dimmed, blurred picture of itself; destroy the cover to clear it."""
    width, height = window.get_allocated_width(), window.get_allocated_height()
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    window.draw(cairo.Context(surface))
    picture = Gdk.pixbuf_get_from_surface(surface, 0, 0, width, height)
    # Shrinking and enlarging is a blur the Pi does in about 30 ms; repeating
    # it smooths away the grid a single pass leaves.
    for _ in range(3):
        picture = picture.scale_simple(max(1, width // 4), max(1, height // 4), GdkPixbuf.InterpType.BILINEAR)
        picture = picture.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    cover = Gtk.DrawingArea()
    def draw(_, context):
        Gdk.cairo_set_source_pixbuf(context, picture, 0, 0)
        context.paint()
        context.set_source_rgba(16 / 255, 18 / 255, 22 / 255, .45)
        context.paint()
    cover.connect("draw", draw)
    window.get_child().add_overlay(cover)
    cover.show()
    return cover


def message(window, title, detail, confirm=None):
    dialog = Gtk.MessageDialog(transient_for=window, modal=True,
        message_type=Gtk.MessageType.QUESTION if confirm else Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.NONE, text=title)
    dialog.set_application(window.get_application())
    dialog.set_title("Mix Pi · Confirm" if confirm else "Mix Pi · Notice")
    dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
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
