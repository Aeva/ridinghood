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
gi.require_version("WebKit", "3.0")
from gi.repository import WebKit, Gtk, GObject

from universe import IpcHandler, IpcListener


class BrowserWorker(IpcListener):
    _event_routing = {
        r'^NAVIGATE: (?P<uri>.*)$': "navigate_event",
    }

    def __init__(self):
        IpcListener.__init__(self, IpcHandler(signal=self))
        
        self.plug = Gtk.Plug()
        self.plug.connect("destroy", Gtk.main_quit)
        
        self.webview = WebKit.WebView()
        settings = self.webview.get_settings()
        settings.set_property("enable-developer-extras", True)
        #settings.set_property("enable-webgl", True)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.webview)
        self.plug.add(scrolled_window)
        self.plug.show_all()
        self.send("PLUG ID: %s" % str(self.plug.get_id()))

    def navigate_event(self, uri):
        print "Navigating to:", uri
        self.webview.load_uri(uri)

if __name__ == "__main__":
    Gtk.init()
    BrowserWorker()
    Gtk.main()
