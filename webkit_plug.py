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


class BrowserWorker(object):
    """
    This class runs in a subprocess of the browser and provides a
    webkit instance / "universe".

    This class is pretty much boilerplate code for connecting the
    webkit instance to the frontend via the IPC framework defined in
    universe.py.
    """

    def __init__(self, tracker, url, tab_id):
        self.tracker = tracker
        self.uuid = tab_id
        self.plug = Gtk.Plug()
        self.plug.connect("destroy", Gtk.main_quit)
        
        self.webview = WebKit.WebView()
        settings = self.webview.get_settings()
        settings.set_property("enable-developer-extras", True)
        #settings.set_property("enable-webgl", True)

        self.webview.connect("load-started", self.load_start_event)
        self.webview.connect("notify::title", self.push_title_change)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.webview)
        self.plug.set_default_size(800, 600)
        self.plug.add(scrolled_window)
        self.plug.show_all()

        self.send("attach_event", plug_id = str(self.plug.get_id()))
        self.navigate_event(url)

    def send(self, action, **packet):
        """
        """
        self.tracker.send(action, target=self.uuid, **packet)

    def load_start_event(self, *args, **kargs):
        uri = self.webview.get_uri()
        self.send("update_uri", uri=uri)
        self.update_history_state()
    
    def push_title_change(self, *args, **kargs):
        title = self.webview.get_title()
        if title:
            self.send("title_changed_event", new_title=str(title))

    def navigate_event(self, uri):
        self.webview.load_uri(uri)
        self.send("update_uri", uri=uri)

    def update_history_state(self):
        self.send("update_history_buttons",
                  back=self.webview.can_go_back(),
                  forward=self.webview.can_go_forward())

    def history_forward(self):
        self.webview.go_forward()
        self.update_history_state()

    def history_backward(self):
        self.webview.go_back()
        self.update_history_state()

    def reload(self):
        self.webview.reload()


class UniverseTracker(IpcListener):
    def __init__(self):
        IpcListener.__init__(self, IpcHandler(signal=self))
        
    def create_new_tab(self, target, url):
        new_tab = BrowserWorker(self, url, target)
        self.register(target, new_tab)

if __name__ == "__main__":
    Gtk.init()
    UniverseTracker()
    Gtk.main()
