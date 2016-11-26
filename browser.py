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
    """
    This class represents a browser tab.  It is mostly boilerplate for
    event routing.

    It is mainly responsible for the creation and communication with
    browsing Universes, and the corresponding Socket object.

    This currently assumes a 1:1 relationship with Universe objects,
    so some future refactoring will be needed to enable multiple tabs
    in the same universe.
    """

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
        self.universe = Universe(self)
        IpcListener.__init__(self, self.universe.ipc)
        self.init_ui_elements()
        self.navigate_to(url)

    def init_ui_elements(self):
        # setup the XEmbed socket:
        self.socket = Gtk.Socket()
        self.socket.set_can_focus(True)

        # add universe tab to tree, if applicable:
        self.tab_store = self.browser.tab_store
        if not hasattr(self.universe, "tree_iter"):
            uni_row = [
                self.universe.__repr__(),
                str(self.universe.universe_id),
            ]
            self.universe.tree_iter = self.tab_store.append(None, uni_row)

        # add browser tab to tree:
        tab_row = [self.title, self.uuid]
        self.tree_iter = self.tab_store.append(self.universe.tree_iter, tab_row)

        # expand universe row:
        uni_path = self.tab_store.get_path(self.universe.tree_iter)
        tree_view = self.browser.tab_tree_view
        tree_view.expand_row(uni_path, True)

    def navigate_to(self, url):
        """
        Request that the universe open the given url.
        """
        self.send("NAVIGATE: %s" % url)

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
        self.universe.destroy()

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
        self.tab_store[self.tree_iter][0] = self.title

    def request_history_state(self):
        """
        Query the universe for the current status of the history buttons.
        """
        self.send("REQ_HISTORY")

    def update_history_state(self, blob):
        """
        Event handler that is triggered by the browser universe reporting
        the status of the history buttons.
        """
        back, forward = json.loads(blob)
        self.browser.update_history_buttons(back, forward)

    def update_uri(self, uri):
        """
        Update the value shown in the url bar.
        """
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
        self.new_tab("http://pirateradiotheater.org")
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
            self.focus_history.remove(tab.uuid)
        except ValueError:
            pass
        self.focus_history.append(tab.uuid)

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
            path = self.tab_tree_view.get_path_at_pos(event_info.x, event_info.y)[0]
            iter = self.tab_store.get_iter(path)
            mystery_id = self.tab_store.get_value(iter, 1)
            thing = self.lookup_id(mystery_id)
            if type(thing) is BrowserTab:
                self.tab_menu(thing)

            elif type(thing) is Universe:
                pass

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
            path = self.tab_store.get_path(tab.tree_iter)
            selector = self.tab_tree_view.get_selection()
            selector.select_path(path)
        self.push_focus_history(tab.uuid)

    def new_tab(self, uri="about:blank"):
        """
        This method creates a new BrowserTab instance and connects it to
        the web browser!
        """
        tab = BrowserTab(self, uri)
        self.tabs[tab.uuid] = tab
        self.views.pack_start(tab.socket, True, True, 0)
        self.focus_tab(tab)
        self.viewport_grab_focus()
        self.push_focus_history(tab.uuid)

    def open_url_event(self, *args, **kargs):
        """
        Event handler, triggerd by pressing enter in the url bar.  This
        attempts to navigate to a new page.
        """
        new_url = self.url_bar.get_text()
        self.focused.navigate_to(new_url)
        self.viewport_grab_focus()

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

    def update_history_buttons(self, back, forward):
        """
        Event handler that is triggered by a browser universe to update
        the history navigation buttons.
        """
        if back:
            self.history_backward.set_sensitive(back)
        if forward:
            self.history_forward.set_sensitive(forward)

    def history_back(self, *args, **kargs):
        """
        Attempt to navigate backwards in the browsing history.
        """
        self.focused.send("HISTORY_BACKWARD")
        
    def history_forward(self, *args, **kargs):
        """
        Attempt to navigate forwards in the browsing history.
        """
        self.focused.send("HISTORY_FORWARD")

    def refresh_page(self, *args, **kargs):
        """
        Refresh the current page.
        """
        self.focused.send("RELOAD")

    def close_tab(self, tab):
        """
        Close a tab, and possibly also the universe it belongs to.
        """
        tab_id = tab.uuid
        tab_iter = tab.tree_iter
        universe_id = tab.universe.universe_id
        universe_iter = tab.universe.tree_iter
        tab.close_event()
        self.tabs.pop(tab_id)
        self.tab_store.remove(tab_iter)
        self.tab_store.remove(universe_iter)
        self.focus_history.remove(tab_id)
        if self.focus_history:
            new_tab_id = self.focus_history[-1]
            new_tab = self.lookup_id(new_tab_id)
            self.focus_tab(new_tab)
        else:
            # no tabs left, so close the browser
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
    BrowserWindow()
    Gtk.main()

