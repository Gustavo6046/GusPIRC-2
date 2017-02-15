import guspirc.main as pirc
import cson
import sys
import pynput

def get_from_config(filename):
    connector = pirc.IRCConnector()

    for c in cson.load(open(filename)):
        connector.add_connection_socket(
            c["server"],
            c["port"],
            c.get("ident", "GusPIRC2"),
            c.get("realname", "Happy for being ran in GusPIRC 2. C:"),
            c["nickname"],
            c.get("password", ""),
            c.get("email", ""),
            c.get("account_name", ""),
            c.get("has_account", True),
            c.get("channels", []),
            c.get("motd_end_numeric", 376),
            c.get("use_ssl", False),
            c.get("master", "None!None@None"),
            c.get("masterperm", 250),
            c.get("quit_message", "https://github.com/Gustavo6046/GusPIRC-2 for more info.")
        )

    return connector

def keyboard_listener(auto_start=True):
    def __decorator__(func):
        def __wrapper__(key):
            l = pynput.keyboard.Listener(on_press=func)

            if auto_start:
                l.start()

            return l

        return __wrapper__

    return __decorator__

if __name__ == "__main__":
    if len(sys.argv) < 2:
        c = get_from_config("connections.cson")

    else:
        c = get_from_config(" ".join(sys.argv[1:]))

    @c.global_receiver(regex=":[^\\!]+\\![^\\@]+\\@[^ ]+ PRIVMSG #([^ ]+) :\\|;reverse( (.+))?")
    def reverse_string(connection, message, custom_groups):
        if custom_groups[1] == "":
            return "PRIVMSG #{} :Syntax: reverse <string to reverse>"

        r = custom_groups[2]

        if r is None:
            return

        return "PRIVMSG #{} :{}: {}".format(custom_groups[0], message.message_data[0], r[::-1])

    @keyboard_listener()
    def check_press(key):
        if not hasattr(key, "char"):
            return

        if key.char == "q":
            pirc.log(logfile, "Stopping...")
            pirc.raw_log.write("\n\n=========\n\n")
            c.stop()

    check_press()
