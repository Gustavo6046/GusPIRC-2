# -*- encoding: utf-8 -*-

import socket as skt
import ssl
import re

from Queue import Empty
from socket import SOCK_STREAM, socket, AF_INET, error
from threading import Thread
from time import sleep, strftime, time
from io import open
from iterqueue import IterableQueue

__doc__ = """
Need to simplify your IRC bot?
Or maybe minimize your IRC interface code?

GusPIRC² comes to save your day!

The simple, event-driven, and now HIGH-level IRC library EVERYONE wants!

To connect to IRC, all you have to do is to do a IRCConnector object and use the function
addSocketConnection() to add a connection to the server!

And you can even create custom commands, set prefixes, etcetra, all with the call
of a SINGLE function (and sometimes use decorators)!
"""

disclaimer = """

Warning: Connecting to the same server and port multiple times may result in failure! This
module is no warranty that your bot is going to work.

GusPIRC 2 is (c)2017 Gustavo Ramos "Gustavo6046" Rehermann and the Sentient Team, Inc.
CC0.

sentientteam.freeforums.org

"""


# GusPIRC
#
# The simple, event-driven, high-level IRC library everyone wants
MESSAGE_TYPES = {
	"KICK":			"([^\\!]+)!([^\\@]+)@([^ ]+) KICK (#[^ ]+) ([^ ]+)( :(.*))?",
	"PRIVMSG":		"([^\\!]+)!([^\\@]+)@([^ ]+) PRIVMSG (#[^ ]+)( :(.+))",
	"BAN":			"([^\\!]+)!([^\\@]+)@([^ ]+) BAN (#[^ ]+)",
	"NOTICE":		"([^\\!]+)!([^\\@]+)@([^ ]+) NOTICE ([^ ]+)( :(.+))",
	"NICK":			"([^\\!]+)!([^\\@]+)@([^ ]+) NICK ([^ ]+)"
}

MESSAGES_RECEIVED = []

class IRCChannel(object):
	"""An IRC channel. A simple class that enables you to quickly access
	any channel GusPIRC II is currently in."""
	def __init__(self, channel_name, connection):
		self.connection = connection

		if channel_name.startswith("#"):
			self.channel = channel_name
			self.no_pound = channel_name.strip("#")

			while self.no_pound.startswith("#"):
				self.no_pound = self.no_pound.strip("#")

		else:
			self.channel = "#{}".format(channel_name)
			self.no_pound = channel_name

class IRCMessage(object):
	"""An IRC message. A flexible, high-level adaptation of GusBot2's
	parsed message dicts."""

	def __init__(self, raw, connection):
		try:
			numeric = int(raw.split(" ")[1])

		except ValueError:
			numeric = None

		if numeric:
			self.message_type = "NUMERIC"
			self.message_data = raw

		else:
			matches = {a: re.match(b, raw).groups() for a, b in {k: v for k, v in MESSAGE_TYPES.items() if re.match(v, raw)}.items()}
			self.message_type = matches.keys()[0]
			self.message_data = matches.values()[0]

		self.raw = raw
		self.connection = connection
		self.duplicates_received = [x.raw for x in MESSAGES_RECEIVED].count(self.raw)

		MESSAGES_RECEIVED.append(self)

class IRCConnection(object):
	"""A connection to IRC. Only usable within an IRCConnector."""

	def __init__(
		connector,
		socket,
		master,
		nickname,
		ident,
		server_host,
		port,
		real_name,
		channels
	):
		self.connector = connector
		self.socket = socket
		self.master = master
		self.nickname = nickname
		self.ident = ident
		self.server_host = server_host
		self.port = port
		self.real_name = real_name

		self.out_queue = IterableQueue()

		self.permissions = {}
		self.receivers = []
		self.channels = [IRCChannel(c, self) for c in channels]

		self.received = []

		threading.Thread(target=self.main_loop).start()

	def join_channel(self, channel):
		"""
		Joins and adds an IRC channel to the channel list.

		It is advisable to *always* precede channel names with
		'#'!
		"""
		self.send_command("JOIN {}".format(channel))
		self.channels.append(IRCChannel(channel, self))

	def part_channel(self, channel):
		"""
		Parts an removes an IRC channel from the channel list.

		It is advisable to *always* precede channel names with
		'#'!
		"""

		if channel.startswith("#"):
			i = [x.channel for x in self.channels].index(channel)

		else:
			i = [x.no_pound for x in self.channels].index(channel)

		self.send_command("PART {}".format(channel))
		self.channels.pop(i)

	def change_perm_level(self, hostmask, level):
		"""Changes the permission level for a hostmask.

		During permission tests of an user, all hostmasks are sorted, and the one
		with the highest permission level is chosen to set the permission for the
		user."""

		self.permissions[hostmask] = level

	def main_loop(self):
		"""It's the main loop mentioned in the docs.

		This is automatically executed upon init and receives all messages
		from this connection.
		"""

		raw = ""

		while True:
			raw += self.socket.read()
			lines = [y for y in [x.strip("\r") for x in raw.split("\n")] if y != ""]
			raw = lines[-1]
			result = lines[:-1]

			for l in lines:
				for f in self.receivers:
					msg = IRCMessage(l, self)

					self.received.append(msg)
					f(msg, l)

	def receiver(self, permission_level=0, regex=".+"):
		def __decorator__(func):
			def __wrapper__(raw):
				self.receivers.append(__wrapper__)

	def send_command(self, cmd):
		if type(cmd) is unicode:
			cmd = cmd.encode("utf-8")

		self.socket.sendall(cmd + "\r\n")


log_handlers = []

def add_log_handler(func):
	log_handlers.append(func)

def log(logfile, msg):
	"""Logs msg to the log file.

	Reminder: msg must be a Unicode string!"""
	try:
		msg = msg.encode('utf-8')

	except (UnicodeDecodeError, UnicodeEncodeError):
		pass

	x = "[{0}]: {1}".format(strftime(u"%A %d - %X"), msg)

	print x

	try:
		logfile.write(x.decode("utf-8") + u"\n")

	except UnicodeEncodeError:
		logfile.write(x + u"\n")

	for f in log_handlers:
		f(msg)

class IRCConnector(object):
	"""The main connector with the IRC world!

	It must only be used once!

	And it's __init__ won't connect to a server by itself. Use
	add_connection_socket() function for this!"""

	def __init__(self):
		"""Are you really willing to call this?

		I though this was called automatically when you started the
		class variable!"""

		self.connections = []
		self.loopthreads = []

		self.logfile = open("log.txt", "a", encoding="utf-8")

		for n in xrange(len(self.connections)):
			self.loopthreads.append(Thread(target=self.main_loop, args=(n,)))

		for x in self.loopthreads:
			x.start()

		self.message_handlers = []

	def add_connection_socket(self,
							  server,
							  port=6697,
							  ident="GusPIRC",
							  real_name="A GusPIRC Bot",
							  nickname="GusPIRC Bot",
							  password="",
							  email="email@address.com",
							  account_name="",
							  has_account=False,
							  channels=None,
							  auth_numeric=267,
							  use_ssl=True,
							  master=""
							  ):
		"""Adds a IRC connection.

		Only call this ONCE PER SERVER! For multiple channels give a
		tuple with all the channel names as string for the argument channels!

		This function only works for NICKSERV-CONTAINING SERVERS!

		- server is the server address to connect to.
		Example: irc.freenode.com

		- port is the port of the server address.
		Example and default value: 6667

		- ident is the ident the bot's hostname will use! It's usually limited
		to 10 characters.

		Example: ident_here
		Result: connector.connections[index][4]!~ident_here@ip_here
		Default value: "GusPIRC"

		- real_name is the bot's real name d==played in most IRC clients.

		Example: GusBot(tm) the property of Gustavo6046

		- nickname is the nick of the bot (self-explanatory)

		Example: YourBotsName

		- password is the password of the bot.

		Example: password123bot

		USE WITH CAUTION! Don't share the password to anyone! Only to extremely
		trustable personnel! Only load it from a external file (like password.txt)
		and DON'T SHARE THE PASSWORD, IN SOURCE CODE, OR IN FILE!!!

		- email: the email the server should send the registration email to
		if has_account is set to False (see below!)

		Example and default value: email@address.com

		- account_name: is the name of the NickServ account the bot will
		use.

		Default value: ""

		Example: botaccount
		Default value: ""

		- has_account: is a bool that determines if the bot already has a reg==tered
		account.

		- channels: iterable object containing strings for the names of all the
		channels the bot should connect to upon joining the network.

		Example: (\"#botters-test\", \"#python\")
		Default value: None (== later defaulted to (\"#<insert bot's nickname here>help\"))

		- auth_numeric: the numeric after which the bot can auth.

		Defaults to 267.

		- master: the name of the admin of the bot. ToDo: add tuple instead of string
		for multiple admins"""

		if not hasattr(channels, "__iter__"):
			raise TypeError("channels == not iterable!")

		log(self.logfile, u"Iteration check done!")

		# | The following commented-out code is known to be faulty and thus
		# | was commented out.

		# if socket_index_by_address(server, port) != -1:
		#	  log(self.logfile, u"Warning: Trying to append socket of existing address!"
		#	  return False
		#
		# log(self.logfile, u"Check for duplicates done!"

		if use_ssl:
			sock = ssl.wrap_socket(socket(AF_INET, SOCK_STREAM))

		else:
			sock = socket(AF_INET, SOCK_STREAM)

		log(self.logfile, u"Socket making done!")

		try:
			sock.connect((server, int(port)))

		except skt.gaierror:
			return False

		log(self.logfile, u"Connected socket!")

		start_time = time()

		if not has_account:
			sock.sendall("NICK {0:s}\r\n".format(account_name))
			sock.sendall("USER {0:s} * * :{1:s}\r\n".format(ident, real_name))

		else:
			sock.sendall("PASS {0:s}:{1:s}\r\n".format(account_name.encode('utf-8'), password.encode('utf-8')))
			sock.sendall("USER {0:s} * * :{1:s}\r\n".format(ident, real_name))
			sock.sendall("NICK {0:s}\r\n".format(nickname))

		log(self.logfile, u"Sent first commands to socket!")

		# function used for breaking through all loops
		def waituntilnotice():
			"""This function is NOT to be called!
			It's a solution to the "break only inner loop" problem!"""
			buffering = u""
			while True:
				raw_received_message = sock.recv(1024).decode('utf-8')

				if raw_received_message == u"":
					sleep(0.2)
					continue

				if not raw_received_message.endswith(u"\r\n"):
					buffering += raw_received_message
					continue

				if buffering != u"":
					raw_received_message = u"%s%s" % (buffering, raw_received_message)
					buffering = ""

				y = raw_received_message.split(u"\r\n")
				y.pop(-1)

				for z in y:
					log(self.logfile, z.encode("utf-8"))

					try:
						compdata = z.split(" ")[1]
						errordata = z.split(" ")[0]

					except IndexError:
						sleep(0.2)
						continue

					if errordata == "PING":
						sock.sendall("PONG :{}\r\n".format(" ".join(z.split(":")[1:])))
						sleep(0.1)
						continue

					if errordata == "ERROR":
						return False

					if compdata == str(auth_numeric):
						return True

		if not waituntilnotice():
			return False

		log(self.logfile, u"NickServ Notice found!")

		if not has_account:
			sock.sendall(u"PRIVMSG NickServ :REGISTER {0:s} {1:s}\r\n".format(password, email))
			sock.sendall(u"PRIVMSG Q :HELLO {0:s} {1:s}\r\n".format(email, email))
			log(self.logfile, u"Made account!")

		try:
			sock.sendall("AUTH {0:s} {1:s}\r\n".format(account_name.encode('utf-8'), password[:10].encode('utf-8')))

		except IndexError:
			sock.sendall("AUTH {0:s} {1:s}\r\n".format(account_name.encode('utf-8'), password.encode('utf-8')))

		sock.sendall("NICK {0:s}\r\n".format(nickname.encode('utf-8')))

		if channels is None:
			channels = (u"#%shelp" % nickname,)
			log(self.logfile, u"Channel defaulting done!")
		else:
			log(self.logfile, u"Channel defaulting check done!")

		executed_time = time() - start_time

		sock.sendall("PASS {0:s}:{1:s}\r\n".format(account_name.encode('utf-8'), password.encode('utf-8')))
		sock.sendall("PRIVMSG Q@CServe.quakenet.org :AUTH {} {}\r\n".format(account_name.encode('utf-8'), password.encode('utf-8')))
		sock.sendall("PRIVMSG NickServ IDENTIFY {0:s} {1:s}\r\n".format(account_name.encode('utf-8'), password.encode('utf-8')))

		sleep(3 - executed_time if executed_time < 3 else 3)

		for x in channels:
			sock.sendall("JOIN %s\r\n" % x.encode('utf-8'))

		log(self.logfile, u"Joined channels!")

		sock.setblocking(0)

		self.name_connections[server] = len(self.connections)

		self.connections.append(IRCConnection(
			connector=self,
			socket=sock,
			master=master,
			nickname=nickname,
			ident=ident,
			server_host=server,
			port=port,
			real_name=real_name,
			channels=channels
		))

		log(self.logfile, u"Added to connections!")

		return True