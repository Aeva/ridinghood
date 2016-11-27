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


import re
import json
import uuid

from urlparse import urlsplit, urlunsplit

import gi
from gi.repository import Gtk, GObject
from universe import Universe, IpcListener


def validate_url(in_url):
    """
    Take some value provided by the user and attempt to produce a
    meaningful url from it.
    """
    parts = list(urlsplit(in_url))
    scheme = parts[0]
    netloc = parts[1]
    path = parts[2]

    if not netloc:
        tld_regex = r'^\S+\.\S+$'
        if re.match(tld_regex, in_url):
            return validate_url("https://%s" % in_url)
        elif in_url == "about:blank":
            return in_url
        else:
            return validate_url("https://en.wikipedia.org/wiki/%s" % in_url)
    return urlunsplit(parts)


def url_domain(url):
    """
    Return the two top-most domains from a given url.
    """
    parts = urlsplit(url)
    return ".".join(parts.netloc.split(".")[-2:])


class BrowserTab(object):
    """
    This class represents a browser tab.  It is mostly boilerplate for
    event routing.  It is also responsible for tracking the Socket
    object needed to display the browser tab.
    """
    
    def __init__(self, browser, url, universe):
        self.url = url
        self.title = "New Tab"
        
        self.uuid = uuid.uuid4().hex
        self.browser = browser
        self.universe = universe
        self.universe.register(self.uuid, self)

        self.init_ui_elements()
        self.send("create_new_tab", url=self.url)

    def init_ui_elements(self):
        # setup the XEmbed socket:
        self.socket = Gtk.Socket()
        self.socket.set_can_focus(True)

        # add universe tab to tree, if applicable:
        tab_store = self.browser.tab_store
        uni_id = self.universe.universe_id
        uni_iter = self.browser.find_tree_iter(uni_id)
        if not uni_iter:
            uni_row = [
                self.universe.__repr__(),
                str(uni_id),
            ]
            uni_iter = tab_store.append(None, uni_row)

        # add browser tab to tree:
        tab_row = [self.title, self.uuid]
        tree_iter = tab_store.append(uni_iter, tab_row)

        # expand universe row:
        uni_path = tab_store.get_path(uni_iter)
        self.browser.tab_tree_view.expand_row(uni_path, True)

    def send(self, action, **packet):
        """
        Wrapper to send a message to the BrowserWorker instance that
        corresponds to this BrowserTab instance.  This automatically
        populates the 'target' field of the packet.
        """
        self.universe.send(action, target=self.uuid, **packet)
        
    def navigate_to(self, url):
        """
        Request that the universe open the given url.
        """
        self.send("navigate_event", uri=url)
        self.browser.url_bar.set_text(url)
        self.url = url

    def activate(self, *args, **kargs):
        """
        Call this to force the browser tab to focus itself.
        """
        self.browser.focus_tab(self)

    def focus(self):
        """
        Event handler for when the tab recieves focus.
        """
        self.request_history_state()
    
    def mute(self):
        """
        Event handler for when the tab loses focus.
        """
        pass

    def close_event(self, *args, **kargs):
        """
        Event handler for when the program is trying to quit.  This
        triggers the browser universe to tear down.
        """
        self.send("teardown")
        self.universe.remove(self.uuid)
        if not self.universe.actors:
            self.universe.destroy()
        self.clean_up()

    def clean_up(self):
        """
        Assumes the connection with the universe has been terminated.
        Clean up whatever is left on this object.  Calling close_event
        implies this.
        """
        self.browser.views.remove(self.socket)
        self.socket.destroy()

    def attach_event(self, plug_id):
        """
        Event handler for when the universe reports the plug_id of its
        Plug object.
        """
        self.socket.add_id(int(plug_id))

    def title_changed_event(self, new_title):
        """
        Event handler for when the title of the open web page changes.
        """
        self.title = new_title
        tree_iter = self.browser.find_tree_iter(self.uuid)
        if tree_iter:
            self.browser.tab_store[tree_iter][0] = self.title

    def request_history_state(self):
        """
        Query the universe for the current status of the history buttons.
        """
        self.send("update_history_state")

    def update_history_buttons(self, back, forward):
        """
        Event handler that is triggered by a browser universe to update
        the history navigation buttons.
        """
        self.browser.history_backward.set_sensitive(back)
        self.browser.history_forward.set_sensitive(forward)

    def update_uri(self, uri):
        """
        Update the value shown in the url bar.
        """
        if uri:
            self.browser.url_bar.set_text(uri)


class TabContextMenu(object):
    """
    This class represents the popup context menu that appears when you
    right click on a browser ui tab.  Only one instance is needed by
    the BrowserWindow, since the menu is the same for each one.
    """
    def __init__(self, browser):
        self.browser = browser
        self.tab = None
        
        self.menu = Gtk.Menu()
        close_item = Gtk.MenuItem("Close Tab")
        close_item.connect("activate", self.on_close)
        self.menu.append(close_item)

    def on_close(self, *args, **kargs):
        """
        Signals that the tab should be closed.
        """
        self.browser.close_tab(self.tab)

    def __call__(self, tab):
        self.tab = tab
        self.menu.show_all()
        self.menu.popup(None, None, None, None, 0, Gtk.get_current_event_time())

class UniverseContextMenu(object):
    """
    This class represents the popup context menu that appears when you
    right click on a browser ui tab.  Only one instance is needed by
    the BrowserWindow, since the menu is the same for each one.
    """
    def __init__(self, browser):
        self.browser = browser
        self.universe = None
        self.menu = Gtk.Menu()
        self.add_item("New Tab", self.on_new_tab)
        self.add_item("Destroy Universe", self.on_close)

    def add_item(self, name, handler):
        """
        Add a new menu item.
        """
        item = Gtk.MenuItem(name)
        item.connect("activate", handler)
        self.menu.append(item)

    def on_new_tab(self, *args, **kargs):
        """
        Signals the creation of a new tab in-universe.
        """
        self.browser.new_tab("about:blank", self.universe)

    def on_close(self, *args, **kargs):
        """
        Signals that the tab should be closed.
        """
        self.browser.close_universe(self.universe)

    def __call__(self, universe):
        self.universe = universe
        self.menu.show_all()
        self.menu.popup(None, None, None, None, 0, Gtk.get_current_event_time())

        
class BrowserWindow(object):
    """
    This class represents... the browser window!  It is currently used
    as a singleton, though, but it is plausible that you could run
    multiple instances and everything will work fine.

    This class is responsible for UI boilerplate comment to the entire
    window, eg url entry, tab bar, etc.  It tracks multiple BrowserTab
    instances, which in turn encapsulate data specific to the browsing
    tabs.  For example, the title, the webkit universe, and so on.
    """
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

        # create popup menu for browser tabs
        self.tab_menu = TabContextMenu(self)
        self.uni_menu = UniverseContextMenu(self)

        # tabs tracks the open BrowserTab objects
        self.tabs = {}
        self.focused = None
        self.tab_store = builder.get_object("TabTreeStore")
        self.tab_tree_view = builder.get_object("TabTreeView")
        self.tab_tree_view.set_activate_on_single_click(True)

        # stores a list of tab ID's, in order of call
        self.focus_history = []

        # setup the treeview's renderer
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", 3)
        self.title_column = Gtk.TreeViewColumn("Tab Title", renderer, text=0)
        self.tab_tree_view.append_column(self.title_column)
        self.tab_tree_view.connect("row_activated", self.tree_activates_tab)

        # self.views tracks all of the sockets
        self.views = builder.get_object("ViewPorts")

        window.show_all()
        
        # create a new tab
        self.new_tab("http://duckduckgo.com")

    def push_focus_history(self, tab_id):
        """
        The focus_history list contains BrowserTab IDs, should contain no
        repeat entries, and is ordered from oldest to newest.

        When a browser tab is closed, this list is used to determine
        what should be focused next.

        This method ensures 'tab_id' is the newest item in the list.
        """
        try:
            self.focus_history.remove(tab_id)
        except ValueError:
            pass
        self.focus_history.append(tab_id)

    def lookup_id(self, mystery_id):
        """
        This method returns one of the following objects for a given ID value:
         - a BrowserTab instance
         - a Universe instance
         - None
        """
        universes = Universe.__active_universes__
        return self.tabs.get(mystery_id) or universes.get(mystery_id)

    def tree_activates_tab(self, tree_view, path, column):
        """
        Event handler, which is triggerd by the TreeView, when the user
        clicks on a row.
        """
        tree_iter = self.tab_store.get_iter(path)
        mystery_id = self.tab_store.get_value(tree_iter, 1)
        thing = self.lookup_id(mystery_id)

        if type(thing) is BrowserTab:
            self.focus_tab(thing, False)
            self.viewport_grab_focus()

        elif type(thing) is Universe:
            print "User selected universe tab: %s" % thing.universe_id

    def tab_tree_button_press_event(self, caller, event_info):
        """
        Event handler which is connected to the button-press event on the
        tabs TreeView object.

        This is used to show a context menue when a right click happens.
        """
        button = event_info.get_button()[1]
        if button == 3:
            # right click
            found = self.tab_tree_view.get_path_at_pos(event_info.x, event_info.y)
            if not found:
                return
            iter = self.tab_store.get_iter(found[0])
            mystery_id = self.tab_store.get_value(iter, 1)
            thing = self.lookup_id(mystery_id)
            if type(thing) is BrowserTab:
                self.tab_menu(thing)

            elif type(thing) is Universe:
                self.uni_menu(thing)

    def viewport_grab_focus(self):
        """
        Gives the browser viewport input focus.  All this does is change
        the input focus to whatever is encapsulated in the tab's
        Socket instance.  This is different from the "focus_tab"
        method.
        """
        # HACK: Cant' call grab_focus() directly on the socket, so we
        # do this instead to make it work. The child_focus call
        # doesn't always work depending on what is currently focused
        # either, so we have the url_bar grab focus first.
        self.url_bar.grab_focus()
        self.focused.socket.child_focus(Gtk.DirectionType.TAB_FORWARD)

    def focus_tab(self, tab, update_highlight=True):
        """
        This method changes which Socket is visible.  Only one is visible
        at a time.  It also calls the "focus" method on the
        cooresponding BrowserTab instance, and triggers some ui state
        changes.
        """
        if self.focused:
            self.focused.mute()
            self.focused.socket.hide()
        self.focused = tab
        tab.focus()
        tab.socket.show()
        self.req_history_update()
        if update_highlight:
            iter = self.find_tree_iter(tab.uuid)
            if iter:
                path = self.tab_store.get_path(iter)
                selector = self.tab_tree_view.get_selection()
                selector.select_path(path)
        self.push_focus_history(tab.uuid)

    def new_tab(self, uri="about:blank", universe=None):
        """
        This method creates a new BrowserTab instance and connects it to
        the web browser!
        """
        if not universe:
            universe = Universe()

        tab = BrowserTab(self, uri, universe)
        self.tabs[tab.uuid] = tab
        self.views.pack_start(tab.socket, True, True, 0)
        self.focus_tab(tab)
        self.viewport_grab_focus()
        self.push_focus_history(tab.uuid)
        self.url_bar.set_text(uri)

    def find_tree_iter(self, thing_id, search=None):
        """
        Returns either None or the GtkTreeIter object associated to the
        provided object ID present in the tab bar.
        """
        for row in search or self.tab_store:
            row_id = self.tab_store.get_value(row.iter, 1)
            if str(thing_id) == row_id:
                return row.iter
            else:
                found = self.find_tree_iter(thing_id, row.iterchildren())
                if found:
                    return found

    def open_url_event(self, *args, **kargs):
        """
        Event handler, triggerd by pressing enter in the url bar.  This
        attempts to navigate to a new page.
        """
        new_url = validate_url(self.url_bar.get_text())
        new_domain = url_domain(new_url)
        old_domain = url_domain(self.focused.url)
        if new_domain == old_domain or self.focused.url == "about:blank":
            self.focused.navigate_to(new_url)
            self.viewport_grab_focus()
        else:
            self.new_tab(new_url)

    def url_bar_gains_focus(self, *args, **kargs):
        """
        Event handler that is called when the url bar gains input focus.
        """
        # This might be useful for changing the cursor position or
        # highlighting the url or something.
        pass
        
    def req_history_update(self):
        """
        When this method is called, the active browser tab's universe is
        queried for the status of the history buttons.
        """
        if self.focused:
            self.focused.request_history_state()

    def history_back(self, *args, **kargs):
        """
        Attempt to navigate backwards in the browsing history.
        """
        self.focused.send("history_backward")
        
    def history_forward(self, *args, **kargs):
        """
        Attempt to navigate forwards in the browsing history.
        """
        self.focused.send("history_forward")

    def refresh_page(self, *args, **kargs):
        """
        Refresh the current page.
        """
        self.focused.send("reload")

    def close_universe(self, universe):
        """
        Close all of the tabs in a given universe.
        """
        tabs = universe.actors.values()
        universe.destroy()
        for tab in tabs:
            self.close_tab(tab)

    def close_tab(self, tab):
        """
        Close a tab, and possibly also the universe it belongs to.
        """

        # store some handy values
        tab_id = tab.uuid
        universe = tab.universe
        universe_id = universe.universe_id
        shutdown = False
        
        # focus a new tab
        self.focus_history.remove(tab_id)
        if self.focus_history:
            new_tab_id = self.focus_history[-1]
            new_tab = self.lookup_id(new_tab_id)
            self.focus_tab(new_tab)
        else:
            shutdown = True

        # tear down the old tab
        if universe.ipc.alive:
            tab.close_event()
        else:
            tab.clean_up()
        self.tabs.pop(tab_id)

        tab_iter = self.find_tree_iter(tab_id)
        if tab_iter:
            self.tab_store.remove(tab_iter)
        if not universe.actors:
            # and also the old universe
            universe_iter = self.find_tree_iter(universe_id)
            if universe_iter:
                self.tab_store.remove(universe_iter)

        # and shut down if there are no other tabs
        if shutdown:
            # no tabs left, so close the browser
            print "shutdown event?"
            self.shutdown_event()

    def shutdown_event(self, *args, **kargs):
        """
        Tear down all subprocesses and stop the Gtk event loop.  This
        causes the program to quit gracefully.
        """
        for tab in self.tabs.values():
            tab.close_event()
        Gtk.main_quit()


if __name__ == "__main__":
    Gtk.init()
    browser = BrowserWindow()
    Gtk.main()
