import guspirc.main as pirc
import cson
import sys

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
        )

    return connector

if __name__ == "__main__":
    if len(sys.argv) < 2:
        c = get_from_config("connections.cson")

    else:
        c = get_from_config(" ".join(sys.argv[1:]))

    @c.global_receiver(regex="[^ ]+ PRIVMSG ##lazy-valoran \\:\\|\\;reverse (.+)")
    def reverse_string(connection, message, custom_groups):
        connection.send_command("PRIVMSG ##lazy-valoran :{}: {}".format(message.groups[0], custom_groups[0]))

    @c.global_receiver(regex="[^ ]+ PRIVMSG ##lazy-valoran \\:\\|\\;reverse$")
    def reverse_string_noargs(connection, message, custom_groups):
        connection.send_command("PRIVMSG ##lazy-valoran :{}: Specify a string to reverse!".format(message.groups[0]))
