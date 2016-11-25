#!/usr/bin/env python


# This file is part of Ridinghood.
#
# Ridinghood is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ridinghood is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ridinghood.  If not, see <http://www.gnu.org/licenses/>.


import json
import gi
from gi.repository import Gtk, GObject
from universe import Universe, IpcListener


class TabLabel(Gtk.Button):
    def __init__(self):
        Gtk.Button.__init__(self)
        self.set_relief(2)
        self.focused = False
        
        self.box = Gtk.HBox()
        self.add(self.box)
        
        self.label = Gtk.Label()
        self.label.set_ellipsize(3)
        self.label.set_xalign(0)
        
        self.icon = Gtk.Image()
        self.icon.set_from_stock("gtk-remove", 1)
        self.button = Gtk.Button()
        self.button.set_relief(2)
        self.button.add(self.icon)
        
        self.box.pack_start(self.label, True, True, 0)
        self.box.pack_start(self.button, False, False, 0)
        self.show_all()
        self.button.set_visible(False)
        
        self.set_text("New Page")

        # self.connect("enter-notify-event", self.enter_notify_event)
        # self.connect("leave-notify-event", self.leave_notify_event)

    def focus(self):
        self.focused = True
        self.set_relief(1)
        self.socket.show()

    def mute(self):
        self.focused = False
        self.set_relief(2)
        self.socket.hide()

    def set_text(self, new_text):
        self.label.set_text(new_text)

    def enter_notify_event(self, *args, **kargs):
        self.button.set_visible(True)
    
    def leave_notify_event(self, *args, **kargs):
        self.button.set_visible(False)

    
class BrowserTab(IpcListener, TabLabel):
    _event_routing = {
        r'^PLUG ID: (?P<plug_id>\d+)$': "attach_event",
        r'^TITLE: (?P<new_title>.*)$': "title_changed_event",
        r'^HISTORY_STATE: (?P<blob>.*)$': "update_history_state",
    }
    
    def __init__(self, parent, url):
        self.url = url
        self.title = "New Tab"
        self.parent = parent
        self.socket = Gtk.Socket()
        self.universe = Universe(self)
        TabLabel.__init__(self)
        IpcListener.__init__(self, self.universe.ipc)

        self.send("NAVIGATE: %s" % url)
        self.connect("clicked", self.activate)

    def activate(self, *args, **kargs):
        self.parent.focus_tab(self)
        self.request_history_state()
        
    def close_event(self, *args, **kargs):
        print "Closing tab:", self.url
        self.universe.destroy()

    def attach_event(self, plug_id):
        print "Attach:", plug_id
        self.socket.add_id(int(plug_id))

    def title_changed_event(self, new_title):
        self.label.set_text(new_title)

    def request_history_state(self):
        self.send("REQ_HISTORY")

    def update_history_state(self, blob):
        back, forward = json.loads(blob)
        self.parent.update_history_buttons(back, forward)

        
class BrowserWindow(object):
    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file("layout.glade")
        builder.connect_signals(self)
        
        window = builder.get_object("BrowserWindow")
        window.set_default_size(900, 675)

        self.url_bar = builder.get_object("UrlBar")
        self.history_forward = builder.get_object("HistoryForward")
        self.history_backward = builder.get_object("HistoryBackward")
        self.refresh_button = builder.get_object("Refresh")

        # tabs tracks the objects in the sidebar
        self.tabs = builder.get_object("BrowserTabs")
        self.focused = None

        # remove any placeholder pages that might be in the glade file
        for widget in self.tabs.get_children():
            self.tabs.remove(widget)

        # self.views tracks all of the sockets
        self.views = builder.get_object("ViewPorts")

        window.show_all()
            
        # create a new tab
        self.new_tab("http://pirateradiotheater.org")
        self.new_tab("http://duckduckgo.com")

    def focus_tab(self, tab):
        if self.focused:
            self.focused.mute()

        self.focused = tab
        tab.focus()
        self.req_history_update()

    def new_tab(self, uri):
        tab = BrowserTab(self, uri)
        self.tabs.pack_start(tab, False, False, 0)
        self.views.pack_start(tab.socket, True, True, 0)
        tab.socket.hide()
        
        self.focus_tab(tab)

    def open_url_event(self, *args, **kargs):
        new_url = self.url_bar.get_text()
        print "Navigate to:", new_url

    def req_history_update(self):
        if self.focused:
            self.focused.request_history_state()

    def update_history_buttons(self, back, forward):
        if back:
            self.history_backward.set_sensitive(back)
        if forward:
            self.history_forward.set_sensitive(forward)

    def history_back(self, *args, **kargs):
        self.focused.send("HISTORY_BACKWARD")
        
    def history_forward(self, *args, **kargs):
        self.focused.send("HISTORY_FORWARD")

    def refresh_page(self, *args, **kargs):
        self.focused.send("RELOAD")

    def shutdown_event(self, *args, **kargs):
        for tab in self.tabs:
            tab.close_event()
        Gtk.main_quit()


if __name__ == "__main__":
    Gtk.init()
    BrowserWindow()
    Gtk.main()

