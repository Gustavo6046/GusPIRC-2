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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        c = get_from_config("connections.cson")

    else:
        c = get_from_config(" ".join(sys.argv[1:]))

    @c.global_receiver(regex="[^\\!]+\\![^\\@]+\\@[^ ]+ PRIVMSG #([^ ]+) :|;reverse (.+)")
    def reverse_string(connection, message, custom_groups):
        r = custom_groups[1]

        if r is None:
            return

        r.reverse()

        return "PRIVMSG #{} :{}: {}".format(custom_groups[0], message.message_data[0], r)

    @c.global_receiver(regex="[^!]+![^@]+@[^ ]+ PRIVMSG #([^ ]+) :|;reverse ?$")
    def reverse_string_noargs(connection, message, custom_groups):
        print message.message_data, message.message_type, message.raw

        return "PRIVMSG #{} :ERROR: Specify a string to reverse!".format(custom_groups[0])



    pynput.keyboard.Listener(on_press=check_press)
