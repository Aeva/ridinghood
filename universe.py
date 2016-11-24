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
                    GLib.idle_add(self.__signal)
            time.sleep(0.01)
    
    def send(self, packet):
        if type(packet) is str:
            self.__write.write(packet.strip() + "\n")
            self.__write.flush()
        elif type(packet) is unicode:
            self.send(packet.encode('utf-8'))
        else:
            raise NotImplementedError("sending arbitrary objects via json")

    def read(self):
        data = None
        if self.__ready.wait(0.01):
            self.__lock.acquire()
            data = self.__new_data
            self.__new_data = []
            self.__lock.release()
        return data

    
class IpcListener(object):
    _event_routing = {}

    def __init__(self, ipc):
        self._ipc = ipc

    def send(self, packet):
        self._ipc.send(packet)
                
    def routing_event(self):
        for line in self.universe.ipc.read():
            for pattern, handler in self._event_routing.items():
                match = re.match(pattern, line)
                if match:
                    self.__getattribute__(handler)(**match.groupdict())


class Universe(object):
    def __init__(self, tab):
        args_list = ["python", "webkit_plug.py", tab.url]
        self.proc = subprocess.Popen(
            args_list, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.ipc = IpcHandler(self.proc.stdout, self.proc.stdin, tab.routing_event)
        
    def destroy(self):
        print "Destroying universe"
        self.proc.kill()
        self.ipc.alive = False
