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
import sys
import time
import json
import select
import subprocess
from threading import Thread, Lock, Event
from gi.repository import GLib


class IpcHandler(Thread):
    """
    This class provides easy interprocess communication over IO
    objects!

    A child process will want to use stdin as the read pipe, and
    stdout as the write pipe.  The parent process will want to use the
    Popen object's stdin as the write pipe, and the Popen object's
    stdout as the read pipe.

    A method or IpcListener instance may also be passed in for the
    signal argument so that message events may be pushed.

    Currently, this depends on a GLib event loop to be present.

    An instance of this class creates a new thread to use ot listen to
    the read_pipe.  When new data is found, it is buffered so that the
    'read' method can acces it, and optionally signal method is
    scheduled to run on the main thread when GLib is idle again.

    This class provides a "read" and "send" method, both of which are
    non-blocking.

    For Gtk applications, you will likely only use the "send" method
    and a signal callback.
    """
    def __init__(self, read_pipe=sys.stdin, write_pipe=sys.stdout, signal=None):
        Thread.__init__(self)
        self.__read = read_pipe
        self.__write = write_pipe
        self.__signal = signal
        
        self.__new_data = []
        self.__lock = Lock()
        self.__ready = Event()

        self.alive = True
        self.start()

    def run(self):
        while self.alive:
            ready = select.select([self.__read], [], [])[0]
            if ready:
                line = ready[0].readline()
                self.__lock.acquire()
                self.__new_data.append(line)
                self.__lock.release()
                self.__ready.set()
                if self.__signal:
                    if hasattr(self.__signal, "routing_event"):
                        GLib.idle_add(self.__signal.routing_event)
                    elif hasattr(self.__signal, "__call__"):
                        GLib.idle_add(self.__signal)
            time.sleep(0.01)
    
    def send(self, packet):
        """
        Sends a "packet" to the other process.  Right now, a packet is
        just a line of ascii encoded text.
        """
        if type(packet) is str:
            self.__write.write(packet.strip() + "\n")
            self.__write.flush()
        elif type(packet) is unicode:
            self.send(packet.encode('utf-8'))
        else:
            raise NotImplementedError("sending arbitrary objects via json")

    def read(self):
        """
        Returns a list of new data from the other process.
        """
        data = None
        if self.__ready.wait(0.01):
            self.__lock.acquire()
            data = self.__new_data
            self.__new_data = []
            self.__lock.release()
        return data

    
class IpcListener(object):
    """
    The IpcListener class provides event routing on top of the
    functionality defined by IpcHandler.  To use this, a derrived
    class should define a dictionary as the "_event_routing" member
    variable.  The keys in the dictionary should be regular
    expressions, the values are method names on the class.  Any name
    groups in the regex are in turn used as named parameters on the
    event callback.

    See BrowserTab as an example of how to use this.
    """
    _event_routing = {}

    def __init__(self, ipc):
        self._ipc = ipc

    def send(self, packet):
        self._ipc.send(packet)
                
    def routing_event(self):
        for line in self._ipc.read():
            handled = False
            for pattern, handler in self._event_routing.items():
                match = re.match(pattern, line)
                if match:
                    self.__getattribute__(handler)(**match.groupdict())
                    handled = True
                    break
            if not handled and line.strip():
                print "No handler found: %s" % line.strip()


class Universe(object):
    """
    This class is used by the browser frontend to create universe
    subprocesses, which encapsulate a clean browsing context.

    This also provides an IpcHandler to communicate with the
    subprocess.

    It is expected that whatever creates this class derrives from
    IpcListener, and attaches to the IpcHandler instance on this, so
    that automatic event routing can be performed.
    """

    __next_universe__ = 1
    __active_universes__ = {}

    def __init__(self, tab):
        self.universe_id = str(Universe.__next_universe__)
        Universe.__next_universe__ += 1
        Universe.__active_universes__[self.universe_id] = self

        args_list = ["python", "webkit_plug.py", tab.url]
        self.proc = subprocess.Popen(
            args_list, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.ipc = IpcHandler(self.proc.stdout, self.proc.stdin, tab)

    def __repr__(self):
        return "EARTH %s" % self.universe_id
        
    def destroy(self):
        print "Destroying universe: %s" % self.__repr__()
        Universe.__active_universes__.pop(self.universe_id)
        self.proc.kill()
        self.ipc.alive = False
