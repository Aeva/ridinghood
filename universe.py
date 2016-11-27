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
    
    def send(self, action, **kargs):
        """
        Sends a "packet" to the other process.  Right now, a packet is
        just a line of ascii encoded text.
        """
        if self.alive:
            packet = "JSON:" + json.dumps({
                "action" : action,
                "kargs" : kargs,
            }).strip().replace("\n", chr(31))

            self.__write.write(packet + "\n")
            try:
                self.__write.flush()
            except IOError:
                self.alive = False

    def read(self):
        """
        Returns a list of new data from the other process.
        """
        data = []
        if self.alive and self.__ready.wait(0.01):
            self.__lock.acquire()
            while self.__new_data:
                raw = self.__new_data.pop(0)
                if raw.startswith("JSON:"):
                    raw = raw.replace(chr(31), "\n")
                    data.append(json.loads(raw[5:]))
                else:
                    data.append(raw)
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

    def __init__(self, ipc):
        self.ipc = ipc
        self.actors = {}

    def register(self, route_id, instance):
        self.actors[route_id] = instance

    def remove(self, route_id):
        try:
            self.actors.pop(route_id)
        except KeyError:
            pass

    def send(self, action, **kargs):
        if self.ipc.alive:
            self.ipc.send(action, **kargs)
                
    def routing_event(self):
        for packet in self.ipc.read():
            handled = False
            if type(packet) is str:
                sys.stderr.write(packet + "\n")

            elif type(packet) is dict:
                action = packet.get('action')
                kargs = packet.get('kargs')
                if action and kargs:
                    if hasattr(self, action):
                        self.__getattribute__(action)(**kargs)
                    else:
                        target = self.actors.get(kargs.get("target"))
                        if target and hasattr(target, action):
                            kargs.pop("target")
                            target.__getattribute__(action)(**kargs)
                        else:
                            sys.stderr.write(
                                "No handler found: %s\n" % action)
                else:
                    sys.stderr.write(
                        "Malformed packet: %s\n" % packet)


class Universe(IpcListener):
    """
    This class is used by the browser frontend to create universe
    subprocesses, which encapsulate a clean browsing context.

    This also doubles up as a IpcListener instance to provide event
    routing stuff.

    Use the 'register' method to attach objects to the event routing
    system.
    """

    __next_universe__ = 1
    __active_universes__ = {}

    def __init__(self):
        self.universe_id = str(Universe.__next_universe__)
        Universe.__next_universe__ += 1
        Universe.__active_universes__[self.universe_id] = self

        args_list = ["python", "webkit_plug.py"]
        self.proc = subprocess.Popen(
            args_list, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.ipc = IpcHandler(self.proc.stdout, self.proc.stdin, self)
        IpcListener.__init__(self, self.ipc)

    def __repr__(self):
        return "EARTH %s" % self.universe_id
        
    def destroy(self):
        if self.ipc.alive:
            self.ipc.alive = False
            print "Destroying universe: %s" % self.__repr__()
            Universe.__active_universes__.pop(self.universe_id)
            self.proc.kill()
            self.actors = []
