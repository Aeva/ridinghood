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
import uuid

import gi
from gi.repository import Gtk, GObject
from universe import Universe, IpcListener

    
class BrowserTab(IpcListener):
    _event_routing = {
        r'^PLUG ID: (?P<plug_id>\d+)$': "attach_event",
        r'^TITLE: (?P<new_title>.*)$': "title_changed_event",
        r'^HISTORY_STATE: (?P<blob>.*)$': "update_history_state",
        r'^URI: (?P<uri>.*)$': "update_uri",
    }
    
    def __init__(self, browser, url):
        self.uuid = uuid.uuid4().hex
        self.url = url
        self.title = "New Tab"
        self.browser = browser
        self.socket = Gtk.Socket()
        self.universe = Universe(self)
        IpcListener.__init__(self, self.universe.ipc)
        self.tab_store = self.browser.tab_store
        #self.tree_iter = self.tab_store.append(None, [self.title, self.uuid])
        self.tree_iter = self.tab_store.append(None, [self.title])

        self.navigate_to(url)
        #self.connect("clicked", self.activate)

    def navigate_to(self, url):
        self.send("NAVIGATE: %s" % url)

    def activate(self, *args, **kargs):
        self.browser.focus_tab(self)

    def focus(self):
        self.request_history_state()
        print "tab has focus"
    
    def mute(self):
        print "tab lost focus"
        
    def close_event(self, *args, **kargs):
        print "Closing tab:", self.url
        self.universe.destroy()

    def attach_event(self, plug_id):
        print "Attach:", plug_id
        self.socket.add_id(int(plug_id))

    def title_changed_event(self, new_title):
        self.title = new_title
        self.tab_store[self.tree_iter][0] = self.title

    def request_history_state(self):
        self.send("REQ_HISTORY")

    def update_history_state(self, blob):
        back, forward = json.loads(blob)
        self.browser.update_history_buttons(back, forward)

    def update_uri(self, uri):
        self.browser.url_bar.set_text(uri)

        
class BrowserWindow(object):
    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file("layout.glade")
        builder.connect_signals(self)
        
        window = builder.get_object("BrowserWindow")
        window.set_default_size(900, 675)

        self.url_bar = builder.get_object("UrlBar")
        self.refresh_button = builder.get_object("Refresh")
        self.history_forward = builder.get_object("HistoryForward")
        self.history_backward = builder.get_object("HistoryBackward")

        # tabs tracks the open BrowserTab objects
        self.tabs = {}
        self.focused = None
        self.tab_store = builder.get_object("TabTreeStore")
        self.tab_tree_view = builder.get_object("TabTreeView")

        # setup the treeview's renderer
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Tab Title", renderer, text=0)
        self.tab_tree_view.append_column(column)
        #self.tab_tree_view.connect("row_activated", self.tree_activates_tab)

        # self.views tracks all of the sockets
        self.views = builder.get_object("ViewPorts")

        window.show_all()
            
        # create a new tab
        self.new_tab("http://pirateradiotheater.org")
        self.new_tab("http://duckduckgo.com")

    def tree_activates_tab(self, tree_view, path, column):
        tree_iter = self.tab_store.get_iter(path)
        uuid = self.tab_store.get_value(tree_iter)
        tab = self.tabs[uuid]
        self.focus_tab(tab)

    def focus_tab(self, tab):
        if self.focused:
            self.focused.mute()

        self.focused = tab
        tab.focus()
        self.req_history_update()

    def new_tab(self, uri):
        tab = BrowserTab(self, uri)
        self.tabs[tab.uuid] = tab
        self.views.pack_start(tab.socket, True, True, 0)
        tab.socket.hide()
        
        self.focus_tab(tab)

    def open_url_event(self, *args, **kargs):
        new_url = self.url_bar.get_text()
        self.focused.navigate_to(new_url)
        self.focused.socket.child_focus(1)
        
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
        for tab in self.tabs.values():
            tab.close_event()
        Gtk.main_quit()


if __name__ == "__main__":
    Gtk.init()
    BrowserWindow()
    Gtk.main()

