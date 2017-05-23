# Credits to J.F. Sebastian for basecode.
import platform
import os
import threading

from subprocess import Popen, CREATE_NEW_CONSOLE

# define a command that starts new terminal
if platform.system() == "Windows":
    new_window_command = "start cmd /c".split()
else:  #XXX this can be made more portable
    new_window_command = "x-terminal-emulator -e".split()

num_streams = 0

class Console(object):
    def __init__(self, init_msg):
        global num_streams
        global new_window_command

        self.filename = "ss{}.cmd".format(num_streams)
        num_streams += 1

        stream = open(self.filename, "w")
        stream.write("@echo off\nECHO {}\n".format(init_msg))
        stream.close()

        runtime_cmd = new_window_command + [" ".join(["loop.bat", self.filename])]

        self.proc = Popen(runtime_cmd, shell=True)

    def execute(self, command):
        open(self.filename, "a").write("\n{}".format(command))

    def __del__(self):
        self.close()

    def close(self):
        os.unlink(self.filename)

        self.proc.terminate()
