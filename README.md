# GusPIRC 2
The sequel to the IRC interface that GusBot2 runs in, now with a higher level!

## What is GusPIRC 2?
GusPIRC 2 is an IRC (and, to some extent, general communication automation) library designed to be powerful, not focusing on
performance, but user-friendliness.

## Why use GusPIRC 2?
- GusPIRC 2 is one of few IRC libraries/bots that ship with a window for manual interaction with the bot and IRC.
- There is a default commands.py file that comes with the commands that GusBot 3 uses. Each command is more fun than the other!
- The ease to define commands.
- With a bit more of Python experience one can easily make an `ExtendableConnector` interface for another communication protocol!

## Why NOT use GusPIRC 2?
- We don't focus on performance, although the bot does run quite fine in most old PCs.
- Currently the bot does not automatically fetch users from the channels it joins.

## How to GusPIRC 2?`
- API

You can use the API located in `guspirc\main.py` (`import guspirc.main as pirc`) and use it when you are doing your own IRC bot.
There is no documentation for the API... yet.
Of course you can also use connload.cson, which is simpler, and uses instead configuration, like below.

- `connections.cson`

This file is what defines the networks, channels and most other connection attributes when using `connload.py`.

Here is an example that connects to [freenode](http://freenode.net/):

	global_info:
	  command_prefix: "%%"
	  master_name: "Your_IRC_Nickname"

	servers: [
	  {
		server: "irc.freenode.net"
		port: 6667
		ident: "GusPIRC2"
		nickname: "MyTestBot"
		password: ""
		account_name: "undefined"
		has_account: true
		email: "your@email.address"
		channels: ["#botters-test"]
		use_ssl: false
		master: ".*!.*@your_hostmask"
		quit_message: "I go to sleep now. Good nite! *hugs everybody and leaves*"
	  }
	]

- Commands

You can use either the `commands.py` file that ships with GusPIRC 2 (basically GusBot 3's personality), or make your own commands.

This is a basic Hello World command (you only need to call this function with the `guspirc.main.IRCConnector` you made to connect):

	def load_commands(c):
		@c.command("test( (.*))?", 0, help_string="Enough ping pong, let's talk test.")
		def hworld(conn, msg, custom):
			if custom[1]:
				return "{}: Hello World!".format(custom[1])
				
			else:
				return "Hello World!"
				
- Running

Running the bot is as simple as `python connload.py [configurations file; omit for connections.cson]`.
