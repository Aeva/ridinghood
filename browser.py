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


import gi
from gi.repository import Gtk, GObject
from universe import Universe, IpcListener


class BrowserTab(IpcListener):
    _event_routing = {
        r'^PLUG ID: (?P<plug_id>\d+)$': "attach_event",
        r'^TITLE: (?P<new_title>.*)$': "title_changed_event",
    }
    
    def __init__(self, parent, url):
        self.url = url
        self.title = "New Tab"
        self.parent = parent
        self._notebook = parent.notebook
        self.socket = Gtk.Socket()
        self.socket.show()
        self.label = Gtk.Label(self.title)
        self.label.show()
        self._notebook.append_page(self.socket, self.label)
        print "New tab:", url
        
        self.universe = Universe(self)
        IpcListener.__init__(self, self.universe.ipc)

        self.send("NAVIGATE: %s" % url)

    def close_event(self, *args, **kargs):
        print "Closing tab:", self.url
        self._notebook.remove(self.socket)
        self.universe.destroy()

    def attach_event(self, plug_id):
        self.socket.add_id(int(plug_id))

    def title_changed_event(self, new_title):
        self.label.set_text(new_title[:5])

        
class BrowserWindow(object):
    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file("layout.glade")
        builder.connect_signals(self)
        
        window = builder.get_object("BrowserWindow")
        window.set_default_size(800, 600)
        window.show_all()

        self.url_bar = builder.get_object("UrlBar")
        self.notebook = builder.get_object("BrowserTabs")
        self.tabs = []

        # remove any placeholder pages that might be in the glade file
        for page in range(self.notebook.get_n_pages()):
            self.notebook.remove_page(page)
            
        # create a new tab
        self.tabs.append(BrowserTab(self, "http://pirateradiotheater.org"))
        self.tabs.append(BrowserTab(self, "http://duckduckgo.com"))

    def open_url_event(self, *args, **kargs):
        new_url = self.url_bar.get_text()
        print "Navigate to:", new_url

    def history_back(self, *args, **kargs):
        print "History Back Event"
        
    def history_forward(self, *args, **kargs):
        print "History Forward Event"

    def refresh_page(self, *args, **kargs):
        print "Refresh Event"

    def shutdown_event(self, *args, **kargs):
        for tab in self.tabs:
            tab.close_event()
        Gtk.main_quit()


if __name__ == "__main__":
    Gtk.init()
    BrowserWindow()
    Gtk.main()

