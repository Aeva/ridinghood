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

import subprocess
import select
import time
import re

import gi
from gi.repository import Gtk, GObject


class BrowserTab(object):
    def __init__(self, url, notebook):
        self.url = url
        self._notebook = notebook
        self.socket = Gtk.Socket()
        self.socket.show()
        self._notebook.append_page(self.socket, Gtk.Label('lorem ipsum'))
        print "New tab:", url
        self.create_webkit_process(url)

    def close_event(self, *args, **kargs):
        print "Closing tab:", self.url
        self._notebook.remove(self.socket)
        self.proc.kill()

    def create_webkit_process(self, url):
        args_list = ["python", "webkit_plug.py", url]
        self.proc = subprocess.Popen(args_list, stdout=subprocess.PIPE)

        start = time.time()
        plug_id = None
        plug_pattern = r'^PLUG ID: (?P<plug_id>\d+)$'
        while True:
            ready = select.select([self.proc.stdout], [], [])[0]
            if ready:
                line = ready[0].readline()
                match = re.match(plug_pattern, line)
                if match:
                    plug_id = int(match.groupdict()['plug_id'])
                    break
            time.sleep(0.01)
            if time.time() - start > 1:
                break
            
        if plug_id:
            self.socket.add_id(plug_id)

        else:
            print "ERROR: No browser plug found."

        
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
        self.tabs.append(BrowserTab("http://pirateradiotheater.org", self.notebook))
        self.tabs.append(BrowserTab("http://duckduckgo.com", self.notebook))

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

