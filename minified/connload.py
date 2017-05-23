import guspirc.main as pirc
import cson
import sys
import threading
import traceback
import commands
import importlib
def load_from_config(connector,filename):
 for c in data["servers"]:
  threading.Thread(target=connector.add_connection_socket,args=(c["server"],c["port"],c.get("ident","GusPIRC2"),c.get("realname","Happy for being ran in GusPIRC 2. C:"),c["nickname"],c.get("password",""),c.get("email",""),c.get("account_name",""),c.get("has_account",True),c.get("channels",[]),c.get("motd_end_numeric",376),c.get("use_ssl",False),c.get("master","None!None@None"),c.get("masterperm",data.get("global_info",{}).get("master_perm",250)),c.get("quit_message","https://github.com/Gustavo6046/GusPIRC-2 for more info."),)).start()
 return connector
def get_from_config(filename):
 data=cson.load(open(filename))
 connector=pirc.IRCConnector(data.get("global_info",{}).get("master_name","__DefaultMaster__"),data.get("global_info",{}).get("command_prefix","|;"))
 for c in data["servers"]:
  threading.Thread(target=connector.add_connection_socket,args=(c["server"],c["port"],c.get("ident","GusPIRC2"),c.get("realname","Happy for being ran in GusPIRC 2. C:"),c["nickname"],c.get("password",""),c.get("email",""),c.get("account_name",""),c.get("has_account",True),c.get("channels",[]),c.get("motd_end_numeric",376),c.get("use_ssl",False),c.get("master","None!None@None"),c.get("masterperm",data.get("global_info",{}).get("master_perm",250)),c.get("quit_message","https://github.com/Gustavo6046/GusPIRC-2 for more info."),)).start()
 return connector
if __name__=="__main__":
 if len(sys.argv)<2:
  data=cson.load(open("connections.cson"))
 else:
  data=cson.load(open(" ".join(sys.argv[1:])))
 c=pirc.IRCConnector(data.get("global_info",{}).get("master_name","__DefaultMaster__"),data.get("global_info",{}).get("command_prefix","|;"))
 try:
  print "Loading commands..."
  commands.define_commands(c)
  print "Commands finished loading!"
 except BaseException as err:
  del c
  raise
 if len(sys.argv)<2:
  load_from_config(c,"connections.cson")
 else:
  load_from_config(c," ".join(sys.argv[1:]))
 @c.no_perm_handler()
 def no_permission(connection,message,needed,func):
  if(not hasattr(func,"cmd_name"))or re.match(func.full_regex,message.raw):
   host="{}!{}@{}".format(*message.message_data[:3])
   connection.send_command("PRIVMSG {} :{}: No permission to execute that command ('{}'; You need {}, but you have {})!".format(message.message_data[3],message.message_data[0],message.message_data[-1],needed,connection.get_perm(host)))
def reload_commands(c):
 try:
  global commands
  commands=reload(commands)
 except BaseException as err:
  return err
 else:
  try:
   commands.define_commands(c)
  except BaseException as err:
   return err
  c.clear_all_receivers()
  commands.define_commands(c)
  return None
# Created by pyminifier (https://github.com/liftoff/pyminifier)
