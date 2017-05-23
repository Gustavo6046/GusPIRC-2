# -*- encoding: utf-8 -*-

import socket as skt
import ssl
import re
import threading
import sys
import cson
import traceback

from Queue import Empty
from socket import SOCK_STREAM, socket, AF_INET, error, gethostname
from threading import Thread
from time import sleep, strftime, time
from io import open
from iterqueue import IterableQueue
from ansi.colour import fg, bg


def locate(i, aname, acont):
	for o in i:
		if hasattr(o, aname) and getattr(o, aname) == acont:
			return o

def name_func(name):
	def __decorator__(func):
		func.__name__ = name
		return func

def multi_match(s, pats):
	return {k: r.match(s) for k, r in pats.items()}

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
	"KICK":			":([^\\!]+)!([^\\@]+)@([^ ]+) KICK (#[^ ]+) ([^ ]+)( :(.*))?",
	"PRIVMSG":		(":([^\\!]+)!([^\\@]+)@([^ ]+) PRIVMSG ([^ ]+)( :(.+))", 3),
	"BAN":			(":([^\\!]+)!([^\\@]+)@([^ ]+) BAN (#[^ ]+) ([^ ]+)", 3),
	"NOTICE":		(":([^\\!]+)!([^\\@]+)@([^ ]+) NOTICE ([^ ]+) :(.+)", 3),
	"NICK":			(":([^\\!]+)!([^\\@]+)@([^ ]+) NICK (#[^ ])+ ([^ ]+)", 3),
	"UMODE":		":([^\\!]+)!([^\\@]+)@([^ ]+) MODE ([^ ]+) (\+.+)?(\-.+)?",
	"CMODE":		(":([^\\!]+)!([^\\@]+)@([^ ]+) MODE (#[^ ]+) ([^ ]+) (\+.+)?(\-.+)?", 3),
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

	def send_message(self, msg):
		"""
		Sends this channel a PRIVMSG. Simple.
		"""
		self.connection.send_message(self.channel, m)

class IRCMessage(object):
	"""An IRC message. A flexible, high-level adaptation of GusBot2's
	parsed message dicts. Due to it's flexibility and not being
	command-specific you must identify the regex groups yourself when
	gathering data about PRIVMSG's and other messages.

	Currently supported messages: KICK, PRIVMSG, BAN, NOTICE, NICK, MODE."""

	def __init__(self, raw, connection=None):
		try:
			numeric = int(raw.split(" ")[1])

		except ValueError:
			numeric = None

		if numeric:
			self.message_type = "NUMERIC"
			self.message_data = raw

		else:
			matches = {a: ((None, re.match(b, raw).groups()) if type(b) not in (tuple, list) else (b[1], re.match(b[0], raw).groups())) for a, b in {k: v for k, v in MESSAGE_TYPES.items() if re.match((v if type(v) not in (tuple, list) else v[0]), raw)}.items()}

			if len(matches) == 0:
				self.message_type = "UNKNOWN"
				self.message_data = raw
				self.channel_index = None

			else:
				self.message_type = matches.keys()[0]
				self.message_data = matches.values()[0][1]
				self.channel_index = matches.values()[0][0]

		self.raw = raw
		self.connection = connection
		self.duplicates_received = [x.raw for x in MESSAGES_RECEIVED].count(self.raw)

		MESSAGES_RECEIVED.append(self)

	def reply(self, msg, reptype="PRIVMSG"):
		if self.channel_index is not None:
			self.connection.send_command("{} {} :{}".format(reptype, self.message_data[self.channel_index], msg))
			return True

		else:
			return False

class DiscordMessage(IRCMessage):
	def __init__(self, connection, message):
		self.message_data = [message.author.nick, "DiscordUser", "discord.vhost", message.channel, message.content]
		self.message_type = "PRIVMSG"

		self.raw = None
		self.connection = connection
		self.discordmsg = message

		MESSAGES_RECEIVED.append(self)

class IRCConnection(object):
	"""A connection to IRC. Only usable within an IRCConnector."""

	def __init__(
		self,
		connector,
		socket,
		master,
		nickname,
		ident,
		server_host,
		port,
		real_name,
		channels,
		quit_message,
	):
		assert connector != None, "IRCConnection *must* be instantiated inside an IRCConnector!"

		self.connector = connector
		self.socket = socket
		self.master = master
		self.nickname = nickname
		self.ident = ident
		self.server_host = server_host
		self.port = port
		self.real_name = real_name
		self.quitmsg = quit_message

		self.out_queue = IterableQueue()

		self.permissions = {}
		self.receivers = []
		self.channels = [IRCChannel(c, self) for c in channels]

		self.received = []

		threading.Thread(target=self.main_loop).start()

	def emulate(self, raw):
		"""
		Emulates a raw IRC message.
		"""

		log(self.connector.logfile, u"$$ {}".format(raw))

		self.received.append(IRCMessage(raw, self))

		for f in self.all_receivers():
			f(self, raw)

	def clear_receivers(self):
		self.receivers = []

	def join_channel(self, channel):
		"""
		Joins and adds an IRC channel to the channel list.

		It is advisable to *always* precede channel names with
		'#'!
		"""
		if type(channel) is unicode:
			channel = channel.encode("utf-8")

		if not channel.startswith("#"):
			channel = "#{}".format(channel)

		self.send_command("JOIN {}".format(channel))
		self.channels.append(IRCChannel(channel, self))

	def part_channel(self, channel):
		"""
		Parts an removes an IRC channel from the channel list.

		It is advisable to *always* precede channel names with
		'#'!
		"""
		if type(channel) is unicode:
			channel = channel.encode("utf-8")

		if channel.startswith("#"):
			if channel not in [x.channel for x in self.channels]:
				return False

			i = [x.channel for x in self.channels].index(channel)

		else:
			if channel not in [x.no_pound for x in self.channels]:
				return False

			i = [x.no_pound for x in self.channels].index(channel)

		self.send_command("PART {}".format(channel))
		self.channels.pop(i)

		return True

	def change_perm_level(self, hostmask, level):
		"""Changes the permission level for a hostmask.

		During permission tests of an user, all hostmasks are sorted, and the one
		with the highest permission level is chosen to set the permission for the
		user."""

		self.permissions[hostmask] = level

	def clear_queue(self):
		"""
		Clears the output queue from the connection, clearing all messages
		the bot goes to output.

		Useful to cancel a spammy command.
		"""

		self.out_queue = IterableQueue()

	def main_loop(self):
		"""It's the main loop mentioned in the docs.

		This is automatically executed upon init and receives all messages
		from this connection.
		"""

		raw = ""

		try:
			while True:
				try:
					raw += self.socket.recv(2048)

				except skt.error:
					self._out()
					continue

				try:
					raw = raw.decode("utf-8")

				except UnicodeDecodeError:
					continue

				self.connector.raw_log.write(raw)

				lines = raw.split("\r\n")
				raw = lines[-1].encode("utf-8")
				res = lines[:-1]

				for l in res:
					log(self.connector.logfile, u"<< {}".format(l.strip()))

					self.received.append(IRCMessage(l, self))

					if l.startswith("PING "):
						self.out_queue.put("PONG {}\r\n".format(" ".join(l.split(" ")[1:])))

					for f in self.all_receivers():
						f(self, l)

				self._out()

		except KeyboardInterrupt:
			self.connector.raw_log.write(u"\n")
			self.socket.sendall("QUIT :{}".format(self.quitmsg))

			raise

	def all_receivers(self):
		r = self.receivers + self.connector.receivers

		return r

	def _out(self):
		try:
			r = self.out_queue.get_nowait()

			if type(r) is unicode:
				r = r.encode("utf-8")

			log(self.connector.logfile, ">> {}".format(r.strip()))
			self.socket.sendall(r)
			sleep(0.8)

		except Empty:
			sleep(0.15)

	def get_perm(self, host):
		self.connector.load_perms(self.connector.perm_filename)

		perms = self.permissions.copy()
		perms.update(self.connector.global_permissions)

		possibles = [y for x, y in perms.items() if re.match(x, host)]

		if len(possibles) == 0:
			return 0

		return max(possibles)

	def receiver(self, regex=".+", permission_level=0, case_insensitive=True):
		"""
		Decorator. Use this in functions you want to use
		to handle incoming messages!
		"""

		def __decorator__(func):
			def __wrapper__(connection, raw):
				msg = IRCMessage(raw)

				if case_insensitive:
					match = re.match(regex, raw, re.I)

				else:
					match = re.match(regex, raw)

				if match is None:
					return False

				if msg.message_type == "PRIVMSG":
					host = "{}!{}@{}".format(*msg.message_data[0:2])

					if self.get_perm(host) < permission_level:
						self.log("Access denied to command '{}'...".format(func.__name__))
						self.connector.no_perm(msg)
						return False

				self.log("Running command '{}'...".format(func.__name__))

				try:
					result = func(connection, msg, match.groups())

				except BaseException as err:
					connection.send_message(connection.connector.master, "Error running command! ({}: {})".format(type(err).__name__, str(err)))
					return False

				if result:
					connection.send_command(result)

				return True

			self.receivers.append(__wrapper__)

			return __wrapper__

		return __decorator__

	def send_command(self, cmd):
		"""
		Sends a command to this connection.

		It is automatically succeded by CRLF,
		so you shouldn't worry with appending those
		to your command!
		"""
		if type(cmd) in (tuple, list):
			for c in cmd:
				if type(c) is unicode:
					c = c.encode("utf-8")

				if c.endswith("\r\n"):
					self.out_queue.put(c.decode("utf-8"))

				elif c.endswith("\n"):
					self.out_queue.put("{}\r\n".format(c[:-2]).decode("utf-8"))

				else:
					self.out_queue.put(c.decode("utf-8") + u"\r\n")

			return

		elif type(cmd) is unicode:
			cmd = cmd.encode("utf-8")

		if cmd.endswith("\r\n"):
			self.out_queue.put(cmd.decode("utf-8"))

		elif cmd.endswith("\n"):
			self.out_queue.put("{}\r\n".format(cmd[:-2]).decode("utf-8"))

		else:
			self.out_queue.put(cmd.decode("utf-8") + u"\r\n")

	def send_message(self, target, message):
		"""
		Sends a message (PRIVMSG) to the target.
		Automatically splits the message in spaces
		(with word wrap) before sending each line to
		avoid lines being trimmed.
		"""

		if type(target) is unicode:
			target = target.encode("utf-8")

		if type(message) is unicode:
			message = message.encode("utf-8")

		messages = []

		if type(message) in (str, unicode):
			message = [message]

		for line in message:
			sub = []

			if len(line.split(" ")) == 1:
				messages.append(line)
				sub = [line]

				continue

			for l in line.split(" "):
				sub.append(l)

				if len(" ".join(sub)) > 270:
					messages.append(" ".join(sub))
					sub = []

		if len(sub) > 1:
			messages.append(" ".join(sub))

		for m in messages:
			self.send_command(u"PRIVMSG {} :{}".format(target.decode("utf-8"), m.decode("utf-8")))

	def log(self, msg):
		self.connector.log(msg)


log_handlers = []

def add_log_handler(func):
	"""
	Adds a function that will handle every log message broadcast.

	Is also usable as decorator.
	"""
	log_handlers.append(func)
	return func

_LOGGING = False

def log(logfile, msg):
	"""Logs msg to the log file.

	Reminder: msg must be a Unicode string!"""
	global _LOGGING

	while _LOGGING:
		sleep(0.1)

	_LOGGING = True
	try:
		msg = msg.encode('utf-8')

	except (UnicodeDecodeError, UnicodeEncodeError):
		pass

	x = "[{0}]: {1}".format(strftime(u"%A %d %B %Y - %X"), msg)

	print x

	try:
		logfile.write(x.decode("utf-8") + u"\n")

	except UnicodeEncodeError:
		logfile.write(x + u"\n")

	for f in log_handlers:
		f(msg)

	_LOGGING = False

class IRCConnector(object):
	"""The main connector with the IRC world!

	It must only be used once!

	And it's __init__ won't connect to a server by itself. Use
	add_connection_socket() function for this!

	(update v2.0) This is also just a way of organizing your
	IRCConnections, but the advantage is making server
	connections quick and easy. Just use the add_connection_socket() function!"""

	def __init__(self, master_name, cmd_prefix="|;", perm_filename="perms.cson"):
		self.connections = []
		self.logfile = open("log.txt", "a", encoding="utf-8")
		self.message_handlers = []
		self.global_permissions = {}
		self.no_perm_handlers = []
		self.name_connections = {}
		self.raw_log = open("rlog.txt", "a", encoding="utf-8")
		self.receivers = []

		self.mastername = master_name
		self.command_prefix = cmd_prefix
		self.perm_filename = perm_filename
		self.load_perms(self.perm_filename)

	def stop(self):
		"""
		Ends the running of the IRC connector.
		"""
		for c in self.connections:
			c.send_command("QUIT :{}".format(c.quitmsg))
			c.socket.stop()
			del c

	def log(self, s):
		log(self.logfile, s)

	def add_custom_connection(
		self,
		conn_type,
		*args,
		**kwargs
	):
		"""Adds a connection of a custom type."""

	def add_connection_socket(self,
							  server,
							  port=6697,
							  ident="GusPIRC2",
							  real_name="A GusPIRC Bot",
							  nickname="GusPIRC Bot",
							  password="",
							  email="email@address.com",
							  account_name="",
							  has_account=False,
							  channels=None,
							  auth_numeric=376,
							  use_ssl=True,
							  master="",
							  master_perm=250,
							  quit_message="Join the GusPIRC 2 bandwagon! https://github.com/Gustavo6046/GusPIRC-2",
	):
		"""Adds an IRC connection.

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

		- master: the hostmask of the admin of the bot.

		- masterperm: the permission level of the admin. How much the admin needs is
		relative to the average command permission level required. Remember that
		you can also change the permission levels of other hostmasks!

		- quitmsg: The quit message (for when the bot takes a KeyboardInterrupt).

		Full documentation coming soon.
		"""

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
			channels=channels,
			quit_message=quit_message,
		))

		log(self.logfile, u"Added to connections!")
		self.global_permissions[master] = master_perm

		self.load_perms(self.perm_filename)

		return True

	def get_perm(self, host):
		possibles = [y for x, y in self.global_permissions.items() if re.match(x, host)]

		if len(possibles) == 0:
			return 0

		return max(possibles)

	def no_perm(self, connection, message, needed, func):
		for f in self.no_perm_handlers:
			f(connection, message, needed, func)

	def clear_all_receivers(self):
		self.receivers = []

		for c in self.connections:
			c.clear_receivers()

	def _name_command(self, oname):
		def __decorator__(ofunc):
			ofunc.__name__ = oname
			return ofunc

	def command(self, n_cmd_regex="", permission_level=0, case_insensitive=False, help_string="No help available for this command."):
		"""
		Decorator. Use this in functions you want to use
		in PRIVMSG's only, to simplify it! Just a global_receiver
		wrapper.
		"""

		def __decorator__(afunc):
			@self.global_receiver("([^\\!]+)\\![^\\@]+\\@[^ ]+ PRIVMSG (#?[^ ]+) :{}(.+)".format(re.escape(self.command_prefix)), case_insensitive, True)
			def __wrapper__(connection, message, custom_groups):
				n, chan, m = custom_groups

				if case_insensitive:
					mt = re.match(n_cmd_regex, m, re.I)

				else:
					mt = re.match(n_cmd_regex, m)

				if mt is None:
					return

				host = "{}!{}@{}".format(*message.message_data[0:3])

				p = connection.get_perm(host)

				if p < permission_level:
					self.log("Access denied to command '{}'...".format(afunc.__name__))
					self.no_perm(connection, message, permission_level, afunc)
					return

				self.log("Executing command '{}'...".format(afunc.__name__))

				p = connection.get_perm(host)

				if chan == connection.nickname:
					chan = n[1:]

				try:
					result = afunc(connection, message, mt.groups())

				except BaseException as e:
					connection.send_message(self.mastername, "{}: {}".format(e.__class__.__name__, str(e)))
					traceback.print_exc()
					return

				if result:
					if type(result) in (list, tuple):
						for r in result:
							if type(r) is unicode:
								r = r.encode("utf-8")

							connection.send_message(chan, r)

						return None

					else:
						if type(result) is unicode:
							result = result.encode("utf-8")

						connection.send_message(chan, result)

			__wrapper__.cmd_name = re.split("[^a-zA-Z1-9_-]", n_cmd_regex.lower())[0]
			__wrapper__.help_string = help_string
			__wrapper__.regex = n_cmd_regex
			__wrapper__.full_regex = "([^\\!]+)\\![^\\@]+\\@[^ ]+ PRIVMSG (#?[^ ]+) :{}{}".format(self.command_prefix, n_cmd_regex)
			__wrapper__.min_perm = permission_level

			return __wrapper__

		return __decorator__

	def global_receiver(self, regex=".+", case_insensitive=True, __command_wrapper__=False):
		"""
		Decorator. Use this in functions you want to use
		to handle incoming messages! Available from all
		connections.
		"""

		def __decorator__(func):
			def __wrapper__(connection, raw):
				msg = IRCMessage(raw)

				if case_insensitive:
					match = re.match(regex, raw, re.I)

				else:
					match = re.match(regex, raw)

				if match is None:
					return

				try:
					result = func(connection, msg, match.groups())

				except BaseException as e:
					connection.send_command("PRIVMSG {} :{}: {}".format(self.mastername, e.__class__.__name__, str(e)))
					traceback.print_exc()
					return

				if result:
					if type(result) in (list, tuple):
						for r in result:
							if type(r) is unicode:
								r = r.encode("utf-8")

							connection.send_command(r)

					else:
						if type(result) is unicode:
							result = result.encode("utf-8")

						connection.send_command(result)

				return

			self.receivers.append(__wrapper__)

			return __wrapper__

		return __decorator__

	def save_perms(self, filename=None):
		if not filename:
			filename = self.perm_filename

		open(filename, "w").write(cson.dumps({
			"global": self.global_permissions,
			"local": {conn.server_host: conn.permissions for conn in self.connections}
		}, indent=4).decode("utf-8"))

	def load_perms(self, filename=None):
		if not filename:
			filename = self.perm_filename

		try:
			data = cson.loads(open(filename).read())

		except BaseException as e:
			self.log("Error loading permissions, using empty default (except for owner):")
			traceback.print_exc()
			return

		self.global_permissions = data["global"]

		for c in self.connections:
			if c.server_host in data["local"]:
				c.permissions = data["local"][c.server_host]

	def change_global_perm(self, hostmask, level):
		"""Changes the global permission level for a hostmask.

		During permission tests of an user, all hostmasks are sorted, and the one
		with the highest permission level is chosen to set the permission for the
		user."""

		self.load_perms()
		self.global_permissions[hostmask] = level
		self.save_perms()

	def no_perm_handler(self):
		def __decorator__(func):
			self.no_perm_handlers.append(func)
			return func

		return __decorator__

class ExtendableConnection(IRCConnection):
	pass

class ExtendableConnector(IRCConnector):
	def add_connection(
		self,
		connection_type,
		server, # Interfaces that don't use name_connections can omit this.
		*args,
		**kwargs
	):
		conn = connection_type(*args, server=server, **kwargs)

		self.connections.append(conn)
		self.name_connections[server] = conn
