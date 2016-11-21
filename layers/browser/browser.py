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


import sys, os.path
import gi
gi.require_version("WebKit", "3.0")
from gi.repository import WebKit, Gtk, GObject


class MainWindow(Gtk.Window):
    def __init__(self, url, *args, **kargs):
        Gtk.Window.__init__(self, *args, **kargs)
        self.set_default_size(1024, 768)
        self.connect("destroy", Gtk.main_quit)
        self.webview = WebKit.WebView()
        settings = self.webview.get_settings()
        #settings.set_property("enable-webgl", True)
        #settings.set_property("enable-developer-extras", True)


        self.add(self.webview)
        self.show_all()
        self.webview.load_uri(url)
        

if __name__ == "__main__":
    url = "https://wikipedia.com"
    if len(sys.argv) > 0:
        url = sys.argv[0];

    w = MainWindow(url)
    Gtk.main()
