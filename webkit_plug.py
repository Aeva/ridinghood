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
gi.require_version("WebKit", "3.0")
from gi.repository import WebKit, Gtk, GObject

from universe import IpcHandler, IpcListener


class BrowserWorker(IpcListener):
    _event_routing = {
        r'^NAVIGATE: (?P<uri>.*)$': "navigate_event",
        r'^REQ_HISTORY$' : "update_history_state",
        r'^HISTORY_FORWARD$' : "history_forward",
        r'^HISTORY_BACKWARD$' : "history_backward",
    }

    def __init__(self):
        IpcListener.__init__(self, IpcHandler(signal=self))
        
        self.plug = Gtk.Plug()
        self.plug.connect("destroy", Gtk.main_quit)
        
        self.webview = WebKit.WebView()
        settings = self.webview.get_settings()
        settings.set_property("enable-developer-extras", True)
        #settings.set_property("enable-webgl", True)

        self.webview.connect('load-finished', self.push_page_load)
        self.webview.connect("notify::title", self.push_title_change)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.webview)
        self.plug.set_default_size(800, 600)
        self.plug.add(scrolled_window)
        self.plug.show_all()
        self.send("PLUG ID: %s" % str(self.plug.get_id()))

    def push_page_load(self, *args, **kargs):
        pass

    def push_title_change(self, *args, **kargs):
        title = self.webview.get_title()
        if title:
            self.send("TITLE: %s" % str(title))

    def navigate_event(self, uri):
        self.webview.load_uri(uri)

    def update_history_state(self):
        data = json.dumps((
            self.webview.can_go_back(),
            self.webview.can_go_forward()
        ))
        self.send("HISTORY_STATE: %s" % data)

    def history_forward(self):
        self.webview.go_forward()
        self.update_history_state()

    def history_backward(self):
        self.webview.go_back()
        self.update_history_state()

if __name__ == "__main__":
    Gtk.init()
    BrowserWorker()
    Gtk.main()
