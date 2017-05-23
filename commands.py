import markov
import re
import requests
import aiml
import bs4
import traceback
import random
import imp
import crawl
import relateword
import threading
import cson
import json
import os
import coffeescript
import js2py
import subprocess
import time
import sys
import pprint
import feedme
import base64
import aiml
import glob

from lxml import etree
from random import randint, choice, uniform
from time import sleep
from cson import dumps, load
from chatterbot import *
from relateword import AutoDictionary
from google import google

try:
    import queue

except ImportError:
    import Queue as queue


stop_trainer = 0

ws_only = re.compile(r"^\s*$")
evalnl  = re.compile(r"[ \t]*((\;\;)([ \t]*\;\;)*)+(([\t ])([^\t ]))?")
whitesp = re.compile(r"\s+$")
assignr = re.compile(r".*[^=]=[^=]")
indent  = re.compile("^(\s+)")

terminate = []
stdin_buf = []
gcid = 0

pp = pprint.PrettyPrinter(4)
trainq = queue.Queue()

def percent_chance(percentage):
    trandom = randint(0, 100)

    print trandom, percentage
    return percentage >= trandom and percentage > 0

def chatter_mainloop(ch, q):
    global stop_trainer

    print "Starting ChatterBot training loop..."

    while True:
        if stop_trainer == 1:
            print "Stopping ChatterBot training loop..."
            stop_trainer = 0
            break

        try:
            data = q.get_nowait()
            ch.train(data)

        except queue.Empty:
            time.sleep(1)

        else:
            time.sleep(1)

def train_chatbot(chatter, l):
    trainq.put_nowait(l)

def urban_dictionary(query):
    req = requests.get("http://api.urbandictionary.com/v0/define?term={}".format(query), timeout=10)

    return json.loads(req.text)

class RegexTable(object):
    def __init__(self, regexes=()):
        self.table = {k: re.compile(r) for k, r in dict(regexes).items()}
        self.raw = dict(regexes)

    def format(self, *args, **kwargs):
        res = {k: v.format(*[re.escape(x) for x in args], **{a: re.escape(b) for a, b in kwargs.items()}) for k, v in self.raw.items()}

        return type(self)(
            res
        )

    def matches(self, line):
        return {k: r.match(line) for k, r in self.table.items()}

    def subs(self, suber, line):
        return {k: r.sub(suber, line) for k, r in self.table.items()}

    def subs_keys(self, line):
        return {k: r.sub(k, line) for k, r in self.table.items()}

    def subs_cond(self, suber, line):
        return {k: v for k, v in self.subs(suber, line).items() if self.matches(line)[k]}

    def subs_keys_cond(self, line):
        return {k: v for k, v in self.subs_keys(line).items() if self.matches(line)[k]}

    def capture(self, line):
        return {k: m.groups() for k, m in self.matches(line).items() if m is not None}

    def any(self, line):
        return any([x is not None for x in self.matches(line)])

    def all(self, line):
        return all([x is not None for x in self.matches(line)])

def run_command(conn, chan, cmd):
    global gcid

    cid = len(terminate)
    tcid = gcid
    gcid += 1
    terminate.append(False)
    stdin_buf.append("")
    a = ""
    ol = len(terminate)

    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, bufsize=1, shell=True)

        oldtime = time.time()

        def read_output():
            while p.returncode is None:
                for line in iter(p.stdout.readline, b''):
                    conn.send_message(chan, u"OUT CID={} :{}".format(cid, line.rstrip().decode("charmap", errors="ignore")))

                for line in iter(p.stderr.readline, b''):
                    conn.send_message(chan, u"ERR CID={} :{}".format(cid, line.rstrip().decode("charmap", errors="ignore")))

        t = threading.Thread(target=read_output)
        t.start()

        while True:
            if len(terminate) < ol:
                cid -= (ol - len(terminate))
                ol = len(terminate)

            if terminate[cid]:
                p.terminate()
                break

            if p.returncode is not None:
                break

            inlines = (a + stdin_buf[cid]).split("\n")

            try:
                a = inlines[-1]

            except IndexError:
                a = ""

            for line in inlines[:-1]:
                conn.send_message(chan, "IN CID={} :{}".format(cid, line))

                def write():
                    p.stdin.write(line + "\n")
                    p.stdin.flush()

                threading.Thread(target=write).start()

            stdin_buf[cid] = ""
            time.sleep(0.2)

        r = p.returncode

        if terminate[cid]:
            conn.send_message(chan, "Process terminated successfully. CIDs > {} are now n-1.".format(cid))

        else:
            for line in iter(p.stdout.readline, b''):
                conn.send_message(chan, u"OUT CID={} :{}".format(cid, line.decode("charmap", errors="ignore")))

            for line in iter(p.stderr.readline, b''):
                conn.send_message(chan, u"ERR CID={} :{}".format(cid, line.decode("charmap", errors="ignore")))

            conn.send_message(chan, "Process stopped with status code {} after {} seconds. CIDs > {} are now n-1.".format(r, time.time() - oldtime, cid))

        terminate.pop(cid)
        stdin_buf.pop(cid)

    except BaseException as err:
        conn.send_message(chan, "Error running process of CID {}! ({}: {})".format(cid, type(err).__name__, str(err)).decode("utf-8", errors="ignore"))

        try:
            terminate.pop(cid)
            stdin_buf.pop(cid)

        except IndexError:
            pass

        raise

def wsrstrip(s):
    return whitesp.sub(s, "")

def multiline(oneliner):
    return evalnl.sub(lambda m: "\n" * (len(m.group(1)) / 2) + (m.group(6) if m.group(6) else ""), oneliner)

def hose(host, channel):
    return "{}#{}".format(host, (channel[1:] if channel.startswith("#") else channel))

def dehose(hosed):
    return [hosed.split("#")[0], "#" + "#".join(hosed.split("#")[1:])]

def certcode(_string, encoding, replacer):
    if type(_string) is str:
        _string = _string.decode("utf-8")

    a = _string.encode(encoding, errors="replace")

    return a.replace("\ufffd", replacer)

def decertcode(_string, encoding, replacer):
    if type(_string) is unicode:
        _string = _string.encode("utf-8")

    a = _string.decode(encoding, errors="replace")

    return a.replace(u"\ufffd", replacer)

def visible(element):
    e = markov.unifix(element).encode("utf-8")

    if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
        return False

    elif re.match(r'\s+<!--.*-->', e):
        return False

    return True

def de_xml(xcode):
    try:
        e = etree.fromstring(xcode)

    except BaseException as err:
        traceback.print_exc()
        return xcode

    r = de_xml_element(e)
    return r

def de_xml_element(e):
    if not e.text:
        for se in e:
            text = de_xml_element(se).encode("utf-8")

        if not e.tail:
            return ""

        return e.text

    text = e.text

    for se in e:
        try:
            text += de_xml_element(se).encode("utf-8")

        except AttributeError:
            continue

    try:
        text += e.tail

    except TypeError:
        return text

    if not text:
        return ""

    return text

def webget(url):
    url = crawl.ensure_url(url)

    try:
        w = requests.get(url, timeout=15)

    except BaseException:
        print "Error trying to retrieve webget data:"
        traceback.print_exc()
        return []

    soup = bs4.BeautifulSoup(w.text, "lxml")
    result = []

    for s in filter(visible, soup.findAll(text=True)):
        while s.endswith("\n") or s.startswith("\n"): s = s.strip("\n")

        if ws_only.match(s):
            continue

        result.append(s)

    return (de_xml("<ROOT>{}</ROOT>".format(s.encode("utf-8"))).strip(" ").strip("\t").strip("\n") for s in result)

def pureweb(url):
    url = crawl.ensure_url(url)

    try:
        w = requests.get(url, timeout=15)

    except BaseException:
        print "Error trying to retrieve webget data:"
        traceback.print_exc()
        return []

    return w.text

def website_to_markov(chain, website):
    chain.read("_markov.cson")

    for s in webget(website):
        for l in markov.unifix(s).splitlines():
            if ws_only.match(l):
                continue

            chain.receive(l)

    chain.write("_markov.cson")

def website_to_autodict(dictionary, url):
    for s in webget(url):
        for l in certcode(s, "ascii", "[?]").splitlines():
            dictionary.parse(s)

def crawl_to(url, feed_func, _max_level, crawl_regex, ex_regex, filt=".*", _verbose=False):
    if not crawl_regex:
        crawl_regex = os.path.join(url, r".+")

    class _crawler(crawl.WebSpider):
        link_regex = crawl_regex
        exclude_regex = ex_regex
        max_level = _max_level
        verbose = _verbose

        def parse(self, soup, url, level):
            if re.match(filt, url) is not None:
                feed_func(soup, url, level)

    _crawler().run(url)

def no_ws(p):
    while p.endswith(" ") or p.startswith(" ") or p.endswith("\t") or p.startswith("\t") or p.endswith("\n") or p.startswith("\n"): p = p.strip()

    return p

def website_to_chatter(chatter, url):
    lines = [l for s in webget(url) for l in certcode(s, "ascii", "[?]").splitlines() if not ws_only.match(l)]

    for p in markov.pairwise(lines):
        print p

        p = tuple(no_ws(x) for x in p)
        train_chatbot(chatter, p)

def reprexc(s, **kwargs):
    m = multiline(s).split("\n")

    for k, v in kwargs.items():
        locals()[k] = v

    if not assignr.match(m[-1]):
        m[-1] = "{}globals()['__r'] = {}".format((indent.match(m[-1]).group(1) if indent.match(m[-1]) is not None else ""), indent.sub("", m[-1]))

    else:
        m.append("globals()['__r'] = None")

    print "\n".join(m)
    exec("\n".join(m))

    if __r is not None:
        return __r

def define_commands(c):
    global markov, relateword, crawl, warzone_port, _num_bots, turn_index, autodict_enabled
    global condense_bot_messages, listeners_enabled, when_events, listeners, relay_msgs
    global cht, stop_trainer, parse_markov, google, memos, mch, rss, feedme, deltas
    global aiml, aik, chatterparse, aiml_parse

    # Reload dependencies that ship with GusBot 3
    markov = reload(markov)
    relateword = reload(relateword)
    crawl = reload(crawl)
    feedme = reload(feedme)

    # Reload other dependencies
    google = reload(google)
    aiml = reload(aiml)

    # Library stuff
    mch = markov.MarkovChain()

    rss = feedme.RSSPool()

    try:
        autod = AutoDictionary.load("autodict.cson")

        if not autod:
            raise ValueError("AutoDict savefile not found; defaulting to empty!")

    except BaseException as err:
        print "Got error trying to load AutoDictionary from file, doing from scratch:"
        traceback.print_exc()
        autod = AutoDictionary()

    autod.save("autodict.cson")

    chatter = ChatBot("GusBot Chat", trainer="chatterbot.trainers.ListTrainer", storage_adapter="chatterbot.storage.JsonFileStorageAdapter")
    aik = aiml.Kernel()

    # Configuration
    chatterparse = False
    aiml_parse = False

    try:
        deltas = cson.load(open("_deltas.cson"))

    except IOError:
        print "Error loading deltas, skipping:"
        traceback.print_exc()
        deltas = []
        cson.dump([], open("_deltas.cson", "w"))

    memos = []

    if "cht" in globals():
        stop_trainer = 1
        while stop_trainer != 0: time.sleep(0.5)

    cht = threading.Thread(target=chatter_mainloop, args=(chatter, trainq))
    cht.start()

    relay_msgs = RegexTable({ # format 1 -> server host
        r"[\1 \3] * \2 \5": r"({}): :([^!]+)![^@]+@[^ ]+ PRIVMSG ({}) :(\x01)ACTION (.+)(\x01)",
        r"[\1 \3] <\2> \4": r"({}): :([^!]+)![^@]+@[^ ]+ PRIVMSG ({}) :((?!(\x01)ACTION).+)",
        r"[\1] \2 joined \3": r"({}): :([^ ]+) JOIN :({})",
        r"[\1] \2 left \3 (\5)": r"({}): :([^!]+)![^ ]+ PART ({})( :(.+))?",
        r"[\1] \2 has quit (\3)": r"({}): :([^!]+)![^ ]+ QUIT :(.+)",
        r"[\1] \2 has kicked \4 from \3 (Reason: \3)": r"({}): :([^!]+)![^ ]+ KICK ({}) ([^ ]+) :(.+)",
        r"[\1] \2 sets ban on \4 in \3": r"({}): :([^ ]+) BAN ({}) (.+)",
        r"[\1] \2 changes nick to \3": r"({}): :([^!]+)![^ +] NICK :(.+)",
    })

    last_message = {}
    verbose_crawling = True
    when_events = []
    accum = {}
    when_events = []

    try:
        listeners = {}
        listeners = cson.load(open("listeners.cson"))

    except BaseException as err:
        print "Error loading listeners file, defaulting to empty:"
        traceback.print_exc()

        listeners = {}

    _num_bots = 0
    capsname = {}
    autodict_enabled = False
    user_data = {}
    turns = []
    turn_index = 0
    condense_bot_messages = True
    listeners_enabled = True
    parse_markov = False

    ammo_data = cson.load(open("smw/ammo_data.cson"))
    weapon_data = cson.load(open("smw/weapon_data.cson"))

    shoot_successful = True

    if os.path.isfile("aiml.brn"): aik.loadBrain("aiml.brn")

    # Commands
    @c.command("aiml_tog", 100, help_string="Toggle AIML parsing.")
    def toggle_aiml(conn, msg, custom):
        global aiml_parse

        aiml_parse = not aiml_parse
        return "AIML parsing set to {}.".format(aiml_parse)

    @c.command("chatter_tog", 100, help_string="Toggle ChatterBot parsing.")
    def toggle_cparse(conn, msg, custom):
        global chatterparse

        chatterparse = not chatterparse
        return "ChatterBot parsing set to {}.".format(chatterparse)

    @c.command("aiml_train (.+)", 80, help_string="Train an AIML set!")
    def train_aiml(conn, msg, custom):
        global aik

        if os.path.isfile("aiml.brn"): aik.loadBrain("aiml.brn")

        if not os.path.isdir("AIMLSets/{}".format(custom[0])) and not ("?" in custom[0] or "*" in custom[0]):
            return "No such AIML set!"

        numerrs = 0
        numfiles = 0

        for a in glob.glob("AIMLSets/{}/*.aiml".format(custom[0])):
            print "Training AIML '{}'...".format(a)

            try:
                aik.learn(a.decode("utf-8"))

            except BaseException as err:
                print "Ignoring error training..."
                traceback.print_exc()
                numerrs += 1

            finally:
                numfiles += 1

        aik.saveBrain("aiml.brn")

        return "AIML trained successfully! {} errors parsing {} files.".format(numerrs, numfiles)

    @c.command("aiml (.+)", 0, help_string="Chat with AIML!")
    def chat_aiml(conn, msg, custom):
        global aik

        if os.path.isfile("aiml.brn"): aik.loadBrain("aiml.brn")
        r = aik.respond("{} said {}".format(msg.message_data[0], custom[0].encode("utf-8")))
        aik.saveBrain("aiml.brn")
        return "{}: {}".format(msg.message_data[0], r)

    @c.command("rss_config (.+)", 165, help_string="Load RSS configuration from config file")
    def load_rss(conn, msg, custom):
        global rss

        if not os.path.exists(filename):
            rss = feedme.RSSPool()

        rss = feedme.RSSPool()
        data = cson.load(custom[0])

    @c.command(r"rss_hook (.+)( ?\| ?(.+))?")
    def hook_rss_feed(conn, msg, custom):
        global rss, hooks

        name, _, chan = custom

        if not chan:
            chan = msg.message_data[3]

        def announce_rss(_, n, e):
            if n == name:
                conn.send_message(chan, u"[RSS] {} ({}) '{}' @ {}".format(e.title, e.link, e.description, e.published))

            hooks[n] = e

        rss.hook(announce_rss)

        if name not in rss.names():
            return "No such RSS label (yet)! Adding hook to empty name. You can add a feed to the name."

        return "RSS hook from label '{}' added successfully!".format(name)

    @c.command("delta_add (\d+) ([^ ]+) (.+)", 120, help_string="Add a Delta alias to bot!")
    def add_delta(conn, msg, custom):
        global deltas

        try:
            deltas.append({"perm": int(custom[0]), "label": custom[1], "func": custom[2]})

        except ValueError:
            return "Invalid permission number!"

        cson.dump(deltas, open("_deltas.cson", "w"))

        return "Delta added successfully!"

    @c.command("delta_count$", 0, help_string="List Delta aliases!")
    def list_deltas(conn, msg, custom):
        global deltas
        return "# of Deltas: {}".format(len(deltas))

    @c.command("delta_list$", 0, help_string="List Delta names!")
    def list_deltas(conn, msg, custom):
        global deltas
        return "Delta List: {}".format(", ".join("{}: {} (perm {})".format(i, d["label"], d["perm"]) for i, d in enumerate(deltas)))

    @c.command("delta (\d+)( (.*))?", 0, help_string="Execute a Delta alias!")
    def exec_delta(conn, msg, custom):
        global deltas

        try:
            d = deltas[int(custom[0])]

        except IndexError:
            return "Error: No such delta!"

        except ValueError:
            return "Error: Invalid delta index!"

        p = conn.get_perm("{}!{}@{}".format(*msg.message_data[:3]))
        if d["perm"] > p:
            return "Error: No permission to run this delta! (you need '{}', but you have only '{}')".format(d["perm"], p)

        return reprexc(d["func"], conn=conn, msg=msg, custom=custom, c=c, _dargs=custom[2].split(" "))

    @c.command(r"rss_unhook (.+)( ?\| ?(.+))?")
    def unhook_rss_feed(conn, msg, custom):
        global rss, hooks

        name, _, chan = custom

        if not chan:
            chan = msg.message_data[3]

        try:
            rss.hooks.remove(hooks[name])

        except ValueError:
            return "No such hook!"

        else:
            return "Hook removed successfully!"

    @c.command(r"rss_add ([^\|]+)\|(.+)", 50, help_string="Add RSS feed! Syntax: rss_add <url> | <label>")
    def add_rss(conn, msg, custom):
        global rss

        url, name = custom

        rss.add_urls(False, {name: url})
        return "RSS Feed '{}' (url: {}) added successfully!".format(name, url)

    @c.command("rss_remove (.+)", 40, help_string="Remove RSS feed! Syntax: rss_remove <label>")
    def rem_rss(conn, msg, custom):
        global rss

        if custom[0] not in rss.names():
            return "No such RSS feed!"

        rss.remove_names(custom[0])
        return "RSS Feed {} removed successfully!"

    @c.command("rss_list", 0, help_string="List RSS feeds!")
    def list_rss_feeds(conn, msg, custom):
        global rss

        return "Feeds: {}".format(",".join("'{}'".format(n) for n in rss.names()))

    @c.command(r"as ([^ ]+) (.+)", 200, help_string="Transfer to someone... hue")
    def run_as(conn, msg, custom):
        user = custom[0]

        conn.emulate(":{} PRIVMSG {} :{}{}".format(user, msg.message_data[3], c.command_prefix, custom[1]))

    @c.command(r"at ([^ ]+) (.+)", 150, help_string="Emulate a command call in another location.")
    def server_emulation(conn, msg, custom):
        server, chan = dehose(custom[0])

        if server not in c.name_connections:
            return "No such server!"

        else:
            if chan:
                c.connections[c.name_connections[server]].emulate(":{} PRIVMSG {} :{}{}".format("{}!{}@{}".format(*msg.message_data[:3]), chan, c.command_prefix, custom[1]))

            else:
                c.connections[c.name_connections[server]].emulate(":{} PRIVMSG GusBot3 :{}{}".format("{}!{}@{}".format(*msg.message_data[:3]), c.command_prefix, custom[1]))

    @c.command("who ([^ ]+)( (.+)+)?", 0, help_string="Who is there? Query the who command! Get a list of people or run a command for each person in the channel! Syntax: who <[server host]#channel> [$bot or #irc command to emulate] | Format Notes: %c -> channel, %i -> issuer, %u -> user, %t -> target chan, %s -> target server, %% -> % (escaped)")
    def who_there(conn, msg, custom):
        q = []

        serv, chan = dehose(custom[0])

        if not custom[2]:
            ufmt = None

        else:
            ufmt = custom[2]

        if not serv:
            serv = conn.server_host

        if serv not in c.name_connections:
            return "No such server!"

        con = c.connections[c.name_connections[serv]]

        if ufmt and not (ufmt.startswith("$") or ufmt.startswith("#")):
            return "Invalid user format! Syntax: <$bot command to pipe to | #IRC command to format>"

        elif ufmt and ufmt.startswith("#") and conn.get_perm("{}!{}@{}".format(*msg.message_data[:3])) < 125:
            return "No permission to execute user formats of IRC commands: you need 125!"

        @con.receiver(r":[^ ]+ (352|315) [^ ]+ {} [^ ]+ [^ ]+ [^ ]+ ([^ ]+)".format(re.escape(chan)))
        def who_parser(conn2, msg2, custom2):
            if not who_parser.done:
                if custom2[0] == "352" and custom2[1]:
                    if ufmt:
                        res = ufmt[1:].replace("%u", custom2[1]).replace("%i", msg.message_data[0]).replace("%c", msg.message_data[3]).replace("%t", chan).replace("%s", serv)
                        print res

                        if ufmt.startswith("$"):
                            conn.emulate(":{}!{}@{} PRIVMSG {} :{}{}".format(msg.message_data[0], msg.message_data[1], msg.message_data[2], msg.message_data[3], c.command_prefix, res))

                        elif ufmt.startswith("#"):
                            conn.send_command(":" + res)

                    else:
                        q.append(custom2[1])

                elif custom2[0] == "315" and not ufmt:
                    who_parser.done = True

                    if msg.message_data[3] == conn.nickname:
                        if q:
                            conn.send_message(msg.message_data[0], "{} /WHO list: {}".format(custom[0], ", ".join(q)))

                        else:
                            conn.send_message(msg.message_data[0], "Nobody at {}.".format(custom[0], ", ".join(q)))

                    else:
                        if q:
                            conn.send_message(msg.message_data[3], "{} /WHO list: {}".format(custom[0], ", ".join(q)))

                        else:
                            conn.send_message(msg.message_data[3], "Nobody at {}.".format(custom[0], ", ".join(q)))

        who_parser.done = False

        con.send_command("who {}".format(chan))

    @c.command("udict (.+)", 75, help_string="Urban Dictionary now!")
    def urban_dict(conn, msg, custom):
        results = []
        query = urban_dictionary(custom[0])

        if query["result_type"] != "exact":
            return "Error: No results found!"

        results.append("Tags: {}".format(", ".join(query["tags"])))

        for l in sorted(query["list"][:5], key=lambda x: x["thumbs_up"] - x["thumbs_down"]):
            results.append(
                "Definition for '{}' (#{}) by {} (up: {}, down: {}): '{}' | Example: '{}'".format(
                    l["word"].encode("utf-8"),
                    l["defid"],
                    l["author"].encode("utf-8"),
                    l["thumbs_up"],
                    l["thumbs_down"],
                    l["definition"].replace("\n", " ").replace("\r", " ").encode("utf-8"),
                    l["example"].replace("\n", " ").replace("\r", " ").encode("utf-8")
                )
            )

        final = []

        for r in results:
            sub = []

            for w in r.split(" "):
                sub.append(w)

                if len(" ".join(sub)) > 260:
                    final.append(" ".join(sub))
                    print sub
                    sub = []

            if sub:
                final.append(" ".join(sub))

        return final

    @c.command("py (.+)", 200, help_string="Evaluate Python code.")
    def py_eval(conn, msg, custom):
        try:
            __r = reprexc(custom[0], conn=conn, msg=msg, custom=custom, c=c)
            return repr(__r)

        except BaseException as err:
            traceback.print_exc()
            return "{}: {}!".format(type(err).__name__, str(err))

    @c.command("memo ([^ ]+) (.+)", 0, help_string="Send memo to someone when this one joins or talks.")
    def def_memo(conn, msg, custom):
        global memos

        memoid = len(memos)
        memos.append(False)

        @c.global_receiver(":{}![^@]+@[^ ]+ (JOIN|PRIVMSG) {}.*".format(custom[0], msg.message_data[3]))
        def send_memo(conn2, msg2, custom2):
            global memos

            try:
                if not memos[memoid]:
                    memos[memoid] = True

                    return "PRIVMSG {} :{}: {} sent a memo to you: {}".format(msg.message_data[3], custom[0], msg.message_data[0], custom[1])

            except IndexError:
                return

        return "Memo sent to {} successfully!".format(custom[0])

    @c.command("cmd (.+)", 200, help_string="Send an IRC command!")
    def send_irc_cmd(conn, msg, custom):
        conn.send_command(custom[0])
        return "Command sent successfully!"

    @c.command(r"google( (\d+))? (.+)", 0, help_string="Google search... from IRC! | Syntax: google <starting index (5 pages are counted)> <query>!")
    def search_google(conn, msg, custom):
        if custom[1]:
            mini = max(int(custom[1]) - 1, 1)

        else:
            mini = 0

        msgs = []

        result = google.search(custom[2], mini + 5)[-5:]
        for i, r in enumerate(result):
            msgs.append(u"{}. {} ({}): '{}'".format(i + mini + 1, markov.unifix(r.name), markov.unifix(r.link), markov.unifix(r.description)))

        return msgs

    @c.command("base64 (.+)", 0, help_string="Encode something in Base64!")
    def base64_enc(conn, msg, custom):
        return "Result: {}".format(base64.b64encode(custom[0]))

    @c.command("debase64 (.+)", 0, help_string="Decode something in Base64!")
    def base64_dec(conn, msg, custom):
        return "Result: {}".format(base64.b64decode(custom[0]).replace("\n", "\\\n"))

    @c.command("js (.+)", 200, help_string="Run something in JavaScript!")
    def js_eval(conn, msg, custom):
        code = multiline(custom[0])

        try:
            return "Result: " + str(js2py.eval_js(code))

        except BaseException as err:
            traceback.print_exc()
            return "Error running code ('{}: {}')!".format(type(err).__name__, str(err))
            raise

    @c.command("cs (.+)", 205, help_string="Run something in CoffeeScript!")
    def cs_eval(conn, msg, custom):
        code = multiline(custom[0])
        compiled = coffeescript.compile(code, True)

        try:
            return "Result: " + str(js2py.eval_js(compiled))

        except BaseException as err:
            return "Error running code ('{}: {}')!".format(type(err).__name__, str(err))
            raise

    @c.command("accumulate (.+)", 120, help_string="Accumulate another message to display later on a single line!")
    def accumulate(conn, msg, custom):
        try:
            accum[msg.message_data[3]].append(custom[0])

        except KeyError:
            accum[msg.message_data[3]] = [custom[0]]

    @c.command("adict_toggleparse", 120, help_string="Toggle AutoDictionary parsing!")
    def toggle_autodict(conn, msg, custom):
        global autodict_enabled

        autodict_enabled = not autodict_enabled
        return "AutoDictionary parsing set to {}!".format(autodict_enabled)

    @c.command("togrelay", 120, help_string="Toggle Listeners!")
    def toggle_autodict(conn, msg, custom):
        global listeners_enabled

        listeners_enabled = not listeners_enabled
        return "Relaying set to {}!".format(listeners_enabled)

    @c.command("release (.+)", 120, help_string="Release accumulated messages!")
    def release_accu(conn, msg, custom):
        try:
            r = accum[msg.message_data[3]]
            del accum[msg.message_data[3]]
            return " | ".join(accum[msg.message_data[3]])

        except KeyError:
            pass

    @c.command("flushmarkov", 75, help_string="Flush Markov data away!")
    def flush_markov(conn, msg, custom):
        global mch

        del mch
        os.unlink("_markov.cson")
        mch = markov.MarkovChain()
        mch.write("_markov.cson")

        return "Flushed Markov succesfully!"

    @c.command("adict_clear", 150, help_string="Clear auto dictionary!")
    def autod_clear(conn, msg, custom):
        autod.perm_def = {}
        autod.def_cache = {}
        autod.historic = []
        autod.times = []
        autod.save("autodict.cson")

        return "AutoDictionary cleared successfully!"

    @c.command(r"when (.+)", help_string="Execute when someone says that! Warning: VERY low-level syntax! Syntax: when <raw event to respond to>$$<raw reply (e.g. 'PRIVMSG #chan :Hello again!')>")
    def execute_whenever(conn, msg, custom):
        global when_enabled
        global when_events

        host = "{}!{}@{}".format(*msg.message_data[0:3])
        when_cmd = "$$".join(custom[0].split("$$")[1:])
        when_event = custom[0].split("$$")[0]
        event_index = len(when_events)

        try:
            when_enabled[when_event] = True

        except NameError:
            when_enabled = {when_event: True}

        @conn.receiver(when_event)
        def execution_when(conn2, msg2, custom2):
            global when_enabled

            when_enabled[when_event] = False
            if when_enabled[when_event]: return when_cmd

        when_events.append(execution_when)

        return "Event setup successfully!"

    @c.command(r"clearwhen", 50, help_string="Clear every 'when' event!")
    def clear_whens(conn, msg, custom):
        global when_events

        for e in when_events:
            del e

        for w in when_events:
            del w

        return "Cleared 'when' events successfully!"

    @c.command("getperm (.+)", help_string="Get the permissions of some host!")
    def get_permission(conn, msg, custom):
        return "Permissions for {}: {}".format(custom[0], conn.get_perm(custom[0]))

    @c.command("reverse( (.+))?", help_string="Reverse any string! :D")
    def reverse_string(conn, msg, custom):
        if custom[0] == "":
            return "PRIVMSG #{} :Syntax: reverse <string to reverse>"

        r = custom[1]

        if r is None:
            return

        return "{}: {}".format(msg.message_data[0], r[::-1].encode("utf-8"))

    @c.command("relay ([^ ]+) ([^ ]+)", 230, help_string="Define a new listener.")
    def make_listener(conn, msg, custom):
        global listeners

        # Forwards...
        if dehose(custom[0])[0] in listeners:
            try:
                listeners[dehose(custom[0])[0]][dehose(custom[0])[1]].append(custom[1])

            except KeyError:
                listeners[dehose(custom[0])[0]][dehose(custom[0])[1]] = [custom[1]]

        else: listeners[dehose(custom[0])[0]] = {dehose(custom[0])[1]: [custom[1]]}

        # ...and backwards!
        if dehose(custom[1])[0] in listeners:
            try:
                listeners[dehose(custom[1])[0]][dehose(custom[1])[1]].append(custom[0])

            except KeyError:
                listeners[dehose(custom[1])[0]][dehose(custom[1])[1]] = [custom[0]]

        else: listeners[dehose(custom[1])[0]] = {dehose(custom[1])[1]: [custom[0]]}

        open("listeners.cson", "w").write(cson.dumps(listeners, indent=4))

        return "Listener defined successfully!"

    @c.command("unrelay ([^ ]+) ([^ ]+)", 230, help_string="Define a new listener.")
    def make_listener(conn, msg, custom):
        global listeners

        # Forwards...
        if dehose(custom[0])[0] not in listeners: return "No such listener in server!"

        try: listeners[dehose(custom[0])[0]][dehose(custom[0])[1]].remove(custom[1])

        except KeyError: return "No such listener in channel!"
        except ValueError: return "No such listener out!"

        if not listeners[dehose(custom[0])[0]][dehose(custom[0])[1]]: del listeners[dehose(custom[0])[0]][dehose(custom[0])[1]]
        if not listeners[dehose(custom[0])[0]]: del listeners[dehose(custom[0])[0]]

        # ...and backwards!
        if dehose(custom[1])[0] not in listeners: return "No such listener in server!"

        try: listeners[dehose(custom[1])[0]][dehose(custom[1])[1]].remove(custom[0])

        except KeyError: return "No such listener in channel!"
        except ValueError: return "No such listener out!"

        if not listeners[dehose(custom[1])[0]][dehose(custom[1])[1]]: del listeners[dehose(custom[1])[0]][dehose(custom[1])[1]]
        if not listeners[dehose(custom[1])[0]]: del listeners[dehose(custom[1])[0]]

        open("listeners.cson", "w").write(cson.dumps(listeners, indent=4))

        return "Listener undefined successfully!"

    @c.command("join (.+)", 50, help_string="Make me join some channel!")
    def join_chan(connection, message, custom_groups):
        connection.join_channel(custom_groups[0])

        return "Channel joined successfully!"

    @c.command("adict_cleanup( ([\\d.]+))?", 240, help_string="Trim some AutoDict size.")
    def cleanup_autodict(conn, msg, custom):
        if not custom[0]:
            trim_ratio = 0.35

        else:
            trim_ratio = float(custom[1])

        autod.def_cache = {k: random.sample(v, int(float(len(v)) * trim_ratio)) for k, v in autod.def_cache.items()}
        autod.save("autodict.cson")

        return "AutoDitionary cleaned successfully! Removed {}%.".format(100 - (trim_ratio * 100))

    @c.command("part (.+)", 80, help_string="Make me leave some channel.")
    def part_chan(connection, message, custom_groups):
        if connection.part_channel(custom_groups[0]):
            return "Channel left successfully!"

        else:
            return "No such channel!"

    @c.command(r"setperm ([^ ]+) (\d+)", 225, help_string="Give someone the BOOT!")
    def set_permission(conn, msg, custom):
        print "Changing perm..."

        c.change_global_perm(custom[0], int(custom[1]))

        return "Permission for '{}' changed successfully!".format(custom[0])

    try:
        mch.read("_markov.cson")

    except IOError:
        open("_markov.cson", "w").write("{}")

    @c.command("prun (.+)", 250, help_string="Execute a shell command at host PC. ADMIN ONLY!")
    def run_shell(conn, msg, custom):
        m = "Process started successfully! CID: {}".format(len(terminate))

        t = threading.Thread(
            target=run_command,
            args=(
                conn,
                msg.message_data[3],
                custom[0]
            )
        )

        t.daemon = True
        t.start()

        return m

    @c.command("pstop (.+)", 250, help_string="Terminate a process started by prun. Syntax: pstop <CID>")
    def stop_shell(conn, msg, custom):
        try:
            a = int(custom[0])

        except ValueError:
            return "Syntax: pstop <CID (number!!)>"

        if a > len(terminate) - 1:
            return "No such CID!"

        terminate[a] = True
        return "CID stopped succesfully!"

    @c.command("pfeed (\d+) (.+)", 250, help_string="Feed bytes into a 'prun' process' STDIN. Syntax: pfeed <CID>")
    def feed_shell(conn, msg, custom):
        a = int(custom[0])

        if a > len(stdin_buf) - 1:
            return "No such CID!"

        stdin_buf[a] += multiline(custom[1]) + "\n"
        return "Input fed successfully to stdin!"

    @c.command("markov( (.+))?", help_string="Get Markov data! Word order is stored and then requested back at a weighted randomness.")
    def get_markov(connection, message, custom_groups):
        global mch

        if not custom_groups[1]:
            r = mch.random_markov()

        else:
            r = mch.get(custom_groups[1])

        if type(r) is int:
            if r == 0:
                return "No such keyword in Markov data!"

            elif r == 1:
                return "No Markov data!"

        return "{}: {}".format(message.message_data[0], r.encode("utf-8"))

    fl = re.compile(" [ \t]+$")

    @c.command("loadmarkov (.+)", 50, help_string="Save Markov data!")
    def save_markov(conn, msg, custom):
        global mch

        mch.read(custom[0])

        return "Markov saved successfully!"

    @c.command("parsemarkov( (.+))", 240, help_string="Parse a file for Markov data!")
    def parse_file_markov(connection, message, custom_groups):
        global mch

        fname = custom_groups[1]

        if fname == "":
            return "Syntax: parsemarkov <filename>"

        try:
            data = [x.strip() for x in open(fname).readlines() if not fl.match(x)]

        except IOError:
            return "Error opening file!"

        mch.read("_markov.cson")

        for x in data:
            mch.receive(x)

        mch.write("_markov.cson")

        return "Data parsed successfully!"

    @c.command("adict_web (.+)", 60, help_string="Parse the Web for AutoDictionary data!")
    def parse_web_adict(conn, msg, custom):
        for w in custom[1].split(" "):
            website_to_autodict(autod, w)

        return "Websites {} parsed successfully!".format(", ".join(custom[1].split(" ")))

    @c.command("ch_web (.+)", 80, help_string="Parse the Web for ChatterBot data!")
    def parse_web_adict(conn, msg, custom):
        for w in custom[0].split(" "):
            website_to_chatter(chatter, w)

        return "Websites {} parsed successfully!".format(", ".join(custom[0].split(" ")))

    @c.command("echo (.+)", 200, help_string="Echo in channel!")
    def echo(conn, msg, custom):
        return custom[0]

    @c.command(r"pipecrawl ([^\|]+)\| ?([^ ]+) ([^ ]+) ([^ ]+) (\d+) (.+)", 240, help_string="Pipe crawling into some command! Syntax: pipecrawl <command to pipe to (%u for URL)> | <URL crawling regex> <URL crawling exclusion regex> <URL piping filter regex> <max depth> <URL to crawl [<URL to crawl> [...]]>.")
    def pipe_crawling(conn, msg, custom):
        print "Crawling... Options:", custom

        host = "{}!{}@{}".format(*msg.message_data[0:3])

        def crawled(soup, url, level):
            conn.emulate(":{} PRIVMSG {} :{}{}".format(host, msg.message_data[3], c.command_prefix, re.sub(r"([^\%])\%u", "\\1" + url.replace("\\", "\\\\"), custom[0].rstrip()).replace("%%", "%")))

        try:
            max_level = min(4, int(custom[4]))

        except ValueError:
            max_level = 2

        for url in custom[5].split(" "):
            crawl_to(url, crawled, max_level, custom[1], custom[2], custom[3], True)

        return "Crawling process started!"

    @c.command("say ([^ ]+) (.+)", 125, help_string="Activate my puppet mouth mode!")
    def emulate_message(connection, message, custom_groups):
        if custom_groups[0] != "$":
            connection.send_message(custom_groups[0], custom_groups[1])

        else:
            connection.send_message(message.message_data[3], custom_groups[1])

    @c.command("act ([^ ]+) (.+)", 110, help_string="* GusBot3 gives a body language example of how act works. (/me for bots)")
    def emulate_message(connection, message, custom_groups):
        action = "\x01ACTION {}\x01"

        if custom_groups[0] != "$":
            connection.send_message(custom_groups[0], action.format(custom_groups[1]))

        else:
            connection.send_message(message.message_data[3], action.format(custom_groups[1]))

    @c.command("webmarkov( (.+))?", 90, help_string="Parse the Web for Markov data!")
    def parse_web_markov(conn, msg, custom):
        if custom[1] == "":
            return "Syntax: webmarkov <list of HTML website URLs separated by space>"

        websites = filter(lambda x: x != "", custom[1].split(" "))

        for w in websites:
            website_to_markov(mch, w)

        return "Websites {} parsed successfully!".format(", ".join(custom[1].split(" ")))

    @c.command("chatter (.+)", 0, help_string="Chat with ChatterBot!")
    def chat(conn, msg, custom):
        print "Getting response..."

        return "{}: {}".format(msg.message_data[0], chatter.get_response(custom[0]))

    @c.command("chparse (.+)", 250, help_string="Train ChatterBot some file.")
    def chat_parse_file(conn, msg, custom):
        train_chatbot(chatter, [certcode(x, "ascii", "[?]") for x in open(custom[0]).readlines()])

    @c.command("ping", 0, help_string="Life test! You don't need to hit this button if you see this message, woof woof :)")
    def life_test(conn, msg, custom):
        return "Pong!"

    @c.command("autodict ([^ ]+)", 0, help_string="Get automatically generated definitions for a word.")
    def autodict_get(conn, msg, custom):
        defs = autod.define(custom[0], "autodict.cson")

        if len(defs) > 0:
            return "Definitions for {}: {}".format(custom[0], "; ".join("{}: {}".format(i + 1, x) for i, x in enumerate(defs)))

        else:
            return "No definitions found for {}!".format(custom[0])

    @c.command("adict_feed (.+)", 100, help_string="Parse a string for AutoDict definitions, using the TF-IDF algorithm.")
    def autodict_feed(conn, msg, custom):
        autod.perm_parse(custom[1])
        autod.save("autodict.cson")

        return "String parsed successfully!"

    @c.command("adict_imply ([^ ]+) (.+)", 100, help_string="Manually add a definition to the auto-dict.")
    def autodict_imply(conn, msg, custom):
        for s in custom[1].split(" "):
            try:
                autod.perm_def[custom[0]].append(s)

            except (KeyError, AttributeError):
                autod.perm_def[custom[0]] = [s]

        autod.save("autodict.cson")

        return "Definition added successfully!"

    @c.global_receiver(regex=r"(.+)")
    def everything_parse(conn, msg, custom):
        # Ignored Assertion
        if conn.get_perm("{}!{}@{}") < 0:
            return

        # Relay
        global listeners_enabled

        try:
            listeners = cson.load(open("listeners.cson"))

        except BaseException as err:
            pass

        if listeners_enabled and conn.server_host in listeners:
            for a, b in listeners[conn.server_host].items():
                tipes = relay_msgs.format(conn.server_host, a)

                if tipes.any("{}: {}".format(conn.server_host, custom[0].encode("utf-8"))):
                    for d in b:
                        serv, chan = dehose(d)

                        if serv in c.name_connections:
                            con = c.connections[c.name_connections[serv]]

                            messages = tipes.subs_keys_cond("{}: {}".format(conn.server_host, custom[0].encode("utf-8"))).values()

                            for m in messages:
                                con.send_message(chan, m)

    @c.command("togmarkov$", 150, help_string="Toggle message parsing of Markov data! (does not affect explicit forms of parsing e.g. webmarkov)")
    def toggle_markov(conn, msg, custom):
        global parse_markov

        parse_markov = not parse_markov

        return "Markov parsing set to {}!".format(parse_markov)

    @c.global_receiver(regex=r"[^ ]+ PRIVMSG (#[^ ]+) :(.+)")
    def generic_message(connection, message, custom_groups):
        global autodict_enabled, parse_markov, mch, chatterparse, aik

        # Ignored Assertion
        try:
            if message.message_type == "PRIVMSG" and connection.get_perm("{}!{}@{}".format(message.message_data[:3])) < 0:
                return

        except IndexError:
            pass

        # Non-Command Assertion
        if custom_groups[1].startswith(c.command_prefix):
            return

        # Markov
        if parse_markov:
            mch.read("_markov.cson")
            mch.receive(custom_groups[1])
            mch.write("_markov.cson")

        # ChaterBot
        if chatterparse:
            a = certcode(custom_groups[1], "ascii", "[?]")

            if custom_groups[0] in last_message:
                try:
                    train_chatbot(chatter, [last_message[custom_groups[0]], a])

                except ValueError:
                    pass

            else:
                last_message[custom_groups[0]] = a

        # AutoDictionary
        if autodict_enabled:
            autod.parse(custom_groups[1])

            autod.save("autodict.cson")

        # (experimental) AIML
        if aiml_parse: c.log("[AIML thinks about it] {}".format(aik.respond("{} said '{}' at the location '{}'.".format(message.message_data[0], custom_groups[1].encode("utf-8"), custom_groups[0]))))

    @c.command("flushq", 220, help_string="Flush send queue.")
    def flush_queue(conn, msg, custom):
        while True:
            try:
                conn.out_queue.get_nowait()

            except BaseException:
                break

        conn.send_message(msg.message_data[3], ".")

    @c.command("reload", 150, help_string="Reload all commands.")
    def reload_bot(conn, msg, custom):
        import connload
        _error = connload.reload_commands(c)

        if _error:
            return "Error reloading bot! ({}: {})".format(type(_error).__name__, str(_error))
            traceback.print_exc()

        return "Bot reloaded successfully!"

    @c.command("list( (.+))?", 0, help_string="Get a list of commands available.")
    def list_commands(conn, msg, custom):
        r = conn.all_receivers()

        if custom[1]: filt = custom[1]
        else: filt = ".*"

        return [
            "Do {}help <command> to get command's help string as provided by it's module. Commands: {}".format(c.command_prefix, ", ".join([f.cmd_name for f in r if hasattr(f, "help_string") and re.match(filt, f.cmd_name)]))
        ]

    @c.command("help (.+)", 0, help_string="Get help for a command.")
    def command_help(conn, msg, custom):
        for cmd in conn.all_receivers():
            if hasattr(cmd, "cmd_name") and cmd.cmd_name.lower() == custom[0].lower():
                return "Help for '{}{}': '{}'; Regex syntax: '{}'; Minimum permission: {}.".format(c.command_prefix, custom[0], cmd.help_string, cmd.regex, cmd.min_perm)

        return "No help found for that command ('{}').".format(custom[0])

    # Sentient Mushes: IRC Warzone

    def shoot(user, target, weapon, bot=False):
        global turn_index

        gun = weapon_data[weapon]

        realdamage = gun["damage"] + uniform(-gun["randomrange"], gun["randomrange"])
        realfdamage = gun["damagefungus"] + uniform(-gun["randomrange"], gun["randomrange"])
        realidamage = gun["damageimmune"] + uniform(-gun["randomimmunerange"], gun["randomimmunerange"])

        if user_data[user.lower()]["ammo"][weapon_data[weapon]["ammotype"]] < 1:
            shoot_successful = False
            if not bot:
                return ["You are loading empty clips!"]

            return ["{} is loading empty clips!".format(capsname[user.lower()])]

        try:
            if turns[turn_index] != user.lower():
                print turns[turn_index]
                print user.lower()

                shoot_successful = False
                return ["Hey! It's not your turn! Stop breaking the queue!"]

        except IndexError:
            shoot_successful = False
            return ["Nobody's playing! There's no turn to pass!"]

        turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

        user_data[user.lower()]["ammo"][gun["ammotype"]] -= 1

        if "nocheckneghealth" not in [x.lower() for x in gun["flags"]]:
            if realdamage < 0:
                realdamage = 0

            if realfdamage < 0:
                realfdamage = 0

            if realidamage < 0:
                realidamage = 0

        if gun["drainhealth"]:
            user_data[target.lower()]["health"] -= realdamage

        if gun["drainfungushealth"] and user_data[target.lower()]["mush"]:
            user_data[target.lower()]["fungushealth"] -= realfdamage

        if gun["drainimmunehealth"]:
            user_data[target.lower()]["immune"] -= realidamage

            if user_data[target.lower()]["immune"] <= 0:
                if user_data[target.lower()]["mush"]:
                    user_data[target.lower()]["immune"] = 0

                else:
                    user_data.__delitem__(target.lower())

                    for i, x in enumerate(turns):
                        if x == target.lower():
                            turns.pop(i)

                    if turn_index >= len(turns):
                        turn_index = 0

                    user_data[user.lower()]["stats"]["AIDS Overdoses"] += 1
                    user_data[user.lower()]["stats"]["Kills"] += 1

                    if not bot:
                        return ["{} received an AIDS overdose! He's out of the game! Rejoin?".format(target)]

                    return ["{} overdosed {} with AIDS using {}! He's out of the game!".format(capsname[user.lower()], capsname[target.lower()], weapon)]

            if not bot:
                return ["{} received a {} damage on immune!".format(capsname[target.lower()], realidamage)]

            return ["{} shot {} with {} to deal {} damage on immune!".format(capsname[user.lower()], weapon, capsname[target.lower()], realidamage)]

        if user_data[target.lower()]["health"] <= 0:
            user_data.__delitem__(target.lower())

            for i, x in enumerate(turns):
                if x == target.lower():
                    turns.pop(i)

            if turn_index >= len(turns):
                turn_index = 0

            mm = uniform(25, 35)
            user_data[user.lower()]["money"] += mm

            user_data[user.lower()]["stats"]["Kills"] += 1

            if not bot:
                return ["(+{money}) {user} is now dead! He's out of the game! Rejoin?".format(money=mm, user=target)]

            return ["{} killed {} with {}! He's out of the game!".format(capsname[user.lower()], weapon, capsname[target.lower()])]

        if user_data[target.lower()]["fungushealth"] < 1 and user_data[target.lower()]["mush"]:
            user_data[user.lower()]["money"] += 50
            user_data[target.lower()]["mush"] = False
            user_data[target.lower()]["immune"] = 3

            user_data[user.lower()]["stats"]["Cures"] += 1

            return ["(+50) {} is not a mush anymore!".format(target)]

        if user_data[target.lower()]["mush"] != user_data[user.lower()]["mush"]:
            user_data[user.lower()]["money"] += uniform(4.75, 10)

        if not user_data[target.lower()]["mush"]:
            if not bot:
                return ["Dealt {} damage into the target!".format((realdamage if gun["drainhealth"] else 0))]

            else:
                return ["{} dealt {} damage into {}!".format(capsname[user.lower()], (realdamage if gun["drainhealth"] else 0), capsname[target.lower()])]

        else:
            if not bot:
                return ["Dealt {} damage into the target plus {} damage to the fungus!".format((realdamage if gun["drainhealth"] else 0), (realfdamage if gun["drainfungushealth"] else 0))]

            else:
                return ["{} dealt {} damage into {} plus {} damage to it's fungus!".format(capsname[user.lower()], (realdamage if gun["drainhealth"] else 0), capsname[target.lower()], (realfdamage if gun["drainfungushealth"] else 0))]

    def pass_turn():
        global turn_index

        turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

    def best_weapon(player, trying_cure=False):
        if trying_cure:
            order = ["gas", "serum", "rockox", "machinegun", "pistol"]

        else:
            order = ["rockox", "machinegun", "gas", "pistol", "serum"]

        try:
            if user_data[player.lower()]["mush"]:
                return max([x for x, y in user_data[player.lower()]["weapons"].items() if y], key=lambda x: 0 if x not in order else order.index(x) + 1)

            else:
                return max([x for x, y in user_data[player.lower()]["weapons"].items() if y], key=lambda x: 0 if x not in [y for y in order if y not in ("serum", "gas")] else order.index(x) + 1)

        except (IndexError, ValueError):
            return None

    class OneSideCatching(BaseException):
        pass

    def check_bot_turn(top_level=True):
        global turn_index, condense_bot_messages

        bp = turns[turn_index].lower()

        user_data[bp]["stats"]["Turns Survived"] += 1

        if not user_data[bp]["bot"]:
            return ["It's now {}'s turn!".format(capsname[turns[turn_index]])]

        messages = []

        bd = user_data[bp]

        turn_passed = False

        weapons = set()

        while True:
            if len([x for x, y in user_data.items() if y["mush"]]) == 0 or len([x for x, y in user_data.items() if not y["mush"]]) == 0:
                if not top_level:
                    raise OneSideCatching

                else:
                    return ["{}Mushes Already Won!".format(("Non-" if False in [y["mush"] for x, y in user_data.items()] else ""))]

            if bd["mush"]:
                try:
                    mtarget = choice([x for x, y in user_data.items() if not y["mush"]])
                    teammate = choice([x for x, y in user_data.items() if y["mush"]])

                    print mtarget, teammate

                except ValueError:
                    turn_passed = True
                    break

                if mtarget == None:
                    turn_passed = True
                    break

                if bd["fungushealth"] < 35:
                    mfh = mfh = uniform(20, 50)

                    user_data[bp]["fungushealth"] += mfh

                    messages.append("{} ate something healthy! +{} fungus health!".format(capsname[bp], mfh))

                    break

                elif bd["health"] < 47.5:
                    if not bd["weapons"]["healgun"] and weapon_data["healgun"]["cost"] < bd["money"]:
                        user_data[bp]["weapons"]["healgun"] = True
                        messages.append("{} bought a healgun!".format(capsname[bp]))

                    if bd["ammo"]["heal"] <= 0 and ammo_data["heal"]["cost"] < bd["money"]:
                        messages.append("{} bought heal ammo!".format(capsname[bp]))
                        user_data[bp]["ammo"]["heal"] += ammo_data["heal"]["amount"]
                        user_data[bp]["money"] += ammo_data["heal"]["cost"]

                    messages.append("{} shot himself a healgun!".format(capsname[bp]))
                    messages += shoot(capsname[bp], bp, "healgun", True)

                elif user_data[teammate]["health"] < 40 or user_data[teammate]["fungushealth"] < 35:
                    if not bd["weapons"]["healgun"] and weapon_data["healgun"]["cost"] < bd["money"]:
                        user_data[bp]["weapons"]["healgun"] = True
                        messages.append("{} bought a healgun!".format(capsname[bp]))

                    if bd["ammo"]["heal"] <= 0 and ammo_data["heal"]["cost"] < bd["money"]:
                        messages.append("{} bought heal ammo!".format(capsname[bp]))
                        user_data[bp]["ammo"]["heal"] += ammo_data["heal"]["amount"]
                        user_data[bp]["money"] += ammo_data["heal"]["cost"]

                    messages.append("{} shot {} a healgun!".format(capsname[bp], capsname[teammate]))
                    messages += shoot(capsname[bp], teammate, "healgun", True)

                elif user_data[mtarget]["immune"] > 1.85 and user_data[bp]["weapons"]["aidsgun"]:
                    while True:
                        if bd["ammo"]["aids"] <= 0 and ammo_data["aids"]["cost"] < bd["money"]:
                            messages.append("{} bought aids ammo!".format(capsname[bp]))
                            user_data[bp]["ammo"]["aids"] += ammo_data["aids"]["amount"]
                            user_data[bp]["money"] += ammo_data["aids"]["cost"]

                        elif bd["ammo"]["aids"] <= 0:
                            break

                        messages.append("{} shot {} at {}!".format(capsname[bp], "aidsgun", capsname[mtarget]))
                        messages += shoot(capsname[bp], mtarget, "aidsgun", True)

                        break

                elif not user_data[bp]["weapons"]["aidsgun"]:
                    random_weapon = "aidsgun"

                    user_data[bp]["money"] -= weapon_data[random_weapon]["cost"]
                    user_data[bp]["weapons"][random_weapon] = True

                    messages.append("{} bought {}!".format(capsname[bp], random_weapon))

                    if user_data[mtarget]["immune"] > 1.85 and user_data[bp]["weapons"]["aidsgun"]:
                        messages.append("{} shot {} at {}!".format(capsname[bp], "aidsgun", capsname[mtarget]))
                        messages += shoot(capsname[bp], mtarget, "aidsgun", True)

                elif user_data[mtarget]["immune"] < 1.2 and user_data[bp]["spores"] and user_data[bp]["spores"] > 0:
                    user_data[bp]["spores"] -= 1
                    user_data[mtarget]["immune"] -= 1

                    if user_data[mtarget]["immune"] <= 0:
                        user_data[mtarget]["fungushealth"] = 72
                        user_data[mtarget]["mush"] = True
                        user_data[bp]["money"] += 35
                        user_data[bp]["stats"]["Infections"] += 1
                        messages.append("{} infected {}! Now {} is a mush!".format(capsname[bp], capsname[mtarget], capsname[mtarget]))

                    else:
                        messages += ["{} spiked {}! But it'll take more than that! Immune down to {} now!".format(capsname[bp], capsname[mtarget], user_data[mtarget]["immune"])]

                elif user_data[bp]["spores"] <= 0:
                    user_data[bp]["spores"] += 1
                    messages += ["Extracted a spore! (now with {})".format(user_data[bp]["spores"])]

                elif user_data[mtarget]["health"] < 21 and best_weapon(bp) != None:
                    if bd["ammo"][weapon_data[best_weapon(bp)]["ammotype"]] <= 0 and ammo_data[weapon_data[best_weapon(bp)]["ammotype"]]["cost"] < bd["money"]:
                        user_data[bp]["ammo"][weapon_data[best_weapon(bp)]["ammotype"]] += ammo_data[weapon_data[best_weapon(bp)]["ammotype"]]["amount"]
                        user_data[bp]["money"] -= ammo_data[weapon_data[best_weapon(bp)]["ammotype"]]["cost"]
                        user_data[bp]["stats"]["Buys"] += 1
                        messages.append("{} bought {} ammo!".format(weapon_data[best_weapon(bp)]["ammotype"]))
                        break

                    messages.append("{} shot {} at {}! Shots Fired!".format(capsname[bp], best_weapon(bp), capsname[mtarget]))
                    messages += shoot(capsname[bp], mtarget, best_weapon(bp), True)

                elif best_weapon(bp) == None:
                    fail = False

                    while True:
                        random_weapon = choice([x for x in weapon_data.keys() if x not in ("healgun", "serum", "gas")])

                        if weapon_data[random_weapon]["cost"] > bd["money"] or random_weapon in weapons:
                            weapons.add(random_weapon)

                            print weapons

                            if len(weapons & set(weapon_data.keys())) == len(weapon_data.keys()):
                                fail = True
                                break

                            continue

                        break

                    if fail:
                        turn_passed = True
                        break

                    print user_data[bp]["money"],
                    user_data[bp]["money"] -= weapon_data[random_weapon]["cost"]
                    print user_data[bp]["money"]
                    user_data[bp]["weapons"][random_weapon] = True
                    user_data[bp]["stats"]["Buys"] += 1

                    messages.append("{} bought {}!".format(capsname[bp]), random_weapon)
                    continue

                else:
                    turn_passed = True

            else:
                try:
                    mtarget = choice([x for x, y in user_data.items() if y["mush"]])
                    teammate = choice([x for x, y in user_data.items() if not y["mush"]])

                except ValueError:
                    turn_passed = True
                    break

                if mtarget == None:
                    turn_passed = True
                    break

                elif user_data[mtarget]["fungushealth"] < 45 and best_weapon(bp, True) != None:
                    messages.append("{} shot {} at {}! Shots Fired!".format(capsname[bp], best_weapon(bp, True), capsname[mtarget]))
                    messages += shoot(capsname[bp], mtarget, best_weapon(bp, True))

                elif user_data[mtarget]["health"] < 58.25 and best_weapon(bp) != None:
                    messages.append("{} shot {} at {}! Shots Fired!".format(capsname[bp], best_weapon(bp, False), capsname[mtarget]))
                    messages += shoot(capsname[bp], mtarget, best_weapon(bp, True))

                elif bd["health"] < 47.5:
                    if not bd["weapons"]["healgun"] and weapon_data["healgun"]["cost"] < bd["money"]:
                        user_data[bp]["weapons"]["healgun"] = True
                        messages.append("{} bought a healgun!".format(capsname[bp]))

                    if bd["ammo"]["heal"] <= 0 and ammo_data["heal"]["cost"] < bd["money"]:
                        messages.append("{} bought heal ammo!".format(capsname[bp]))
                        user_data[bp]["ammo"]["heal"] += ammo_data["heal"]["amount"]
                        user_data[bp]["money"] += ammo_data["heal"]["cost"]

                    messages.append("{} shot himself a healgun!".format(capsname[bp]))
                    messages += shoot(capsname[bp], bp, "healgun", True)

                elif user_data[teammate]["health"] < 40:
                    if not bd["weapons"]["healgun"] and weapon_data["healgun"]["cost"] < bd["money"]:
                        user_data[bp]["weapons"]["healgun"] = True
                        messages.append("{} bought a healgun!".format(capsname[bp]))

                    if bd["ammo"]["heal"] <= 0 and ammo_data["heal"]["cost"] < bd["money"]:
                        messages.append("{} bought heal ammo!".format(capsname[bp]))
                        user_data[bp]["ammo"]["heal"] += ammo_data["heal"]["amount"]
                        user_data[bp]["money"] += ammo_data["heal"]["cost"]

                    messages.append("{} shot {} a healgun!".format(capsname[bp], capsname[teammate]))
                    messages += shoot(capsname[bp], teammate, "healgun", True)

                elif user_data[bp]["immune"] < 2.0:
                    old_immune = user_data[bp]["immune"]
                    user_data[bp]["immune"] += randint(72, 132) * 0.01
                    messages.append("{} ate something healthy! Mmmmm, +{} immune on Rehermann scale!".format(capsname[bp], user_data[bp]["immune"] - old_immune))

                elif best_weapon(bp) != None:
                    if bd["ammo"][weapon_data[best_weapon(bp)]["ammotype"]] <= 0:
                        user_data[bp]["ammo"][weapon_data[best_weapon(bp)]["ammotype"]] += ammo_data[weapon_data[best_weapon(bp)]["ammotype"]]["amount"]
                        user_data[bp]["money"] -= ammo_data[weapon_data[best_weapon(bp)]["ammotype"]]["cost"]
                        messages.append("{} bought {} ammo!".format(capsname[bp], weapon_data[best_weapon(bp)]["ammotype"]))
                        break

                    if user_data[mtarget]["fungushealth"] > user_data[mtarget]["health"] * 1.725:
                        messages.append("{} shot {} at {}! Shots Fired!".format(capsname[bp], best_weapon(bp, False), capsname[mtarget]))
                        messages += shoot(capsname[bp], mtarget, best_weapon(bp, True))

                    else:
                        messages.append("{} shot {} at {}! Shots Fired!".format(capsname[bp], best_weapon(bp, True), capsname[mtarget]))
                        messages += shoot(capsname[bp], mtarget, best_weapon(bp), True)

                else:
                    fail = False

                    if percent_chance(50):
                        while True:
                            random_weapon = choice([x for x in weapon_data.keys() if x not in ("aidsgun", "healgun")])

                            if weapon_data[random_weapon]["cost"] > bd["money"] or random_weapon in weapons:
                                weapons.add(random_weapon)

                                print weapons

                                if len(weapons & set(weapon_data.keys())) == len(weapon_data.keys()):
                                    fail = True
                                    break

                                continue

                            break

                        if fail:
                            turn_passed = True
                            break

                    else:
                        random_weapon = "gas"

                        if weapon_data[random_weapon]["cost"] < bd["money"] or random_weapon in weapons:
                            turn_passed = True
                            break

                    user_data[bp]["money"] -= weapon_data[random_weapon]["cost"]
                    user_data[bp]["weapons"][random_weapon] = True
                    user_data[bp]["stats"]["Buys"] += 1

                    messages.append("{} bought {}!".format(capsname[bp], random_weapon))
                    continue

            break

        pass_turn()

        if turn_passed:
            messages.append("{} passed the turn!".format(capsname[bp]))

        try:
            messages += check_bot_turn(False)

        except OneSideCatching:
            return ["{}Mushes Win!".format(("Non-" if False in [y["mush"] for x, y in user_data.items()] else ""))]

        if top_level and condense_bot_messages:
            full = " | ".join(messages)

            messages = [full[i:i+250] for i in xrange(0, len(full), 250)]

        return messages

    @c.command("smw_statistics( (.+))?", help_string="Game statistics for Sentient Mushes: Warzone.")
    def get_statistics(conn, message, custom):
        try:
            target = custom[1].split()[0]
            tn = target.lower()

        except IndexError:
            target = tn = ""

        if tn in turns:
            return "{} ({}Mush) Game Statistics: ".format(target, ("Non-" if not user_data[tn]["mush"] else "")) + "; ".join(["{}: {}".format(x, y) for x, y in user_data[tn]["stats"].items()])

        else:
            result = ["Match Statistics: "] + ["{} ({}Mush) Game Statistics: ".format(capsname[tn], ("Non-" if not user_data[tn]["mush"] else "")) + "; ".join(["{}: {}".format(x, y) for x, y in user_data[tn]["stats"].items()]) for tn in turns]

            if result:
                return result

            else:
                return "Error: No one in the match!"

    @c.command("smw_leaderboard( (.+))?", help_string="Game leaderboard for Sentient Mushes: Warzone.")
    def statistical_leaderboard(conn, message, custom):
        parts = ["OFFICIAL LEADERBOARD!"]

        try:
            leaderboard = {
                "Lightcaster": (sorted(user_data.items(), key=lambda x: x[1]["stats"]["Infections"])[0], "enlightenings", "Infections"),
                "Spender": (sorted(user_data.items(), key=lambda x: x[1]["stats"]["Buys"])[0], "buys", "Buys"),
                "Assassin": (sorted(user_data.items(), key=lambda x: x[1]["stats"]["Kills"])[0], "kills", "Kills"),
                "Survivor": (sorted(user_data.items(), key=lambda x: x[1]["stats"]["Turns Survived"])[0], "turns survived", "Turns Survived"),
                "AIDS Killer": (sorted(user_data.items(), key=lambda x: x[1]["stats"]["AIDS Overdoses"])[0], "overdoses caused by them", "AIDS Overdoses"),
                "Medic": (sorted(user_data.items(), key=lambda x: x[1]["stats"]["Cures"])[0], "\'unmushings\'", "Cures"),
            }

        except IndexError:
            return "No one tries, no one wins!"

        for rankee, ranking in leaderboard.items():
            parts.append("Best {}: {} with {} {}!".format(rankee, ranking[0][1]["capsname"], ranking[0][1]["stats"][ranking[2]], ranking[1]))

        return parts

    @c.command("smw_addbots( (.+))?", help_string="Add a number of AI players to Sentient Mushes: Warzone.")
    def smw_add_a_bot(conn, message, custom):
        global _num_bots

        names = []

        try:
            bots = int(custom[1].split()[0])

        except (IndexError, ValueError):
            bots = 1

        if bots + _num_bots > 40:
            bots = 40 - _num_bots

        if bots <= 0:
            return "Error: Max limit reached!"

        _num_bots += bots

        for i in xrange(bots):
            is_mush = percent_chance(48)

            try:
                name = choice([x.strip("\n") for x in open("botnames.txt").readlines() if not ws_only.match(x)])

            except IndexError:
                return "No bot name to use! (use {}smw_addnames to add some bot names :D)".format(c.command_prefix)

            while name.lower() in user_data.keys():
                name += str(user_data.keys().count(name.lower()))

            names.append(name)
            turns.append(name.lower())
            user_data[name.lower()] = {
                "host": ".!.@.",
                "money": 30,
                "mush": is_mush,
                "spores": 6,
                "immune": 3,
                "ammo": {x: y["defaultvalue"] for x, y in ammo_data.items()},
                "weapons": {x: False for x in weapon_data.keys()},
                "capsname": message.message_data[0],
                "health": 100,
                "bot": True,
                "fungushealth": 72,
                "stats": {
                    "Kills": 0,
                    "AIDS Overdoses": 0,
                    "Infections": 0,
                    "Buys": 0,
                    "Turns Survived": 0,
                    "Cures": 0,
                },
            }
            capsname[name.lower()] = name

        return "Added {} bots ({}) to the game!".format(bots, ", ".join(names))

    @c.command("smw_eat( (.+))?", help_string="Eat (different effects for mush or not) on Sentient Mushes Warzone.")
    def smw_eat_something_healthy(conn, message, custom):
        global turn_index

        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return ["Eat your vegetables and brush after every meal! ;)"]

        if user.lower() != turns[turn_index]:
            return "Hey! Eat when it's your turn! :P"

        if len(user_data.keys()) < 2:
            return "Mmmmmm! That's appreciable, indeed."

        if user_data[user.lower()]["mush"]:
            mfh = uniform(20, 50)
            user_data[user.lower()]["fungushealth"] += mfh

            turn_index += 1

            if turn_index >= len(turns):
                turn_index = 0

            return ["Mmmmmmm! +{} fungus health!".format(mfh)]

        old_immune = user_data[user.lower()]["immune"]
        user_data[user.lower()]["immune"] += randint(72, 132) * 0.01

        turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

        return ["Mmmmmmmmmmm! +{} immune power in Rehermann scale!".format(user_data[user.lower()]["immune"] - old_immune)] + check_bot_turn()

        check_bot_turn()

    @c.command("smw_findspore( (.+))?", help_string="Find a spore on Sentient Mushes: Warzone. May have different effects.")
    def smw_search_for_spores(conn, message, custom):
        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        if not percent_chance(62):
            return ["No spore found!"]

        if user_data[user.lower()]["mush"]:
            user_data[user.lower()]["spores"] += 1
            pass_turn()
            return ["Found a random spore! Absorbing... Now you have {} spores!".format(user_data[user.lower()]["spores"]) + "It's now {}'s turn!".format(capsname[turns[turn_index]])] + check_bot_turn()

        if percent_chance(72):
            user_data[user.lower()]["fungushealth"] = 72
            user_data[user.lower()]["mush"] = True
            return ["Found a spore... but wait, was that meant to happen? Now you are... a mush!"]

        else:
            return ["You found a spore! But wait... why were you looking for spores?", "Do you want to plant champignons or didn't you know the danger of this?"]

    @c.command("smw_turns( (.+))?", help_string="Who's turn? On Sentient Mushes: Warzone.")
    def turn_list(conn, message, custom):
        check_bot_turn()

        return ["Turn queue: " + ", ".join([capsname[x] for x in turns])] + (["Current: " + capsname[turns[turn_index]]] if turns else [])

    @c.command("smw_join( (.+))?", help_string="Join the Warzone! (Sentient Mushes: Warzone)")
    def join_warzone_stats(conn, message, custom):
        user = message.message_data[0]
        is_mush = percent_chance(48)

        if user.lower() in user_data.keys():
            return ["You already joined the game! To quit (suicide), use ||smw_quit ."]

        turns.append(user.lower())

        user_data[user.lower()] = {
                "host": "{}!{}@{}".format(*message.message_data[:3]),
                "money": 30,
                "mush": is_mush,
                "spores": 6,
                "immune": 3,
                "ammo": {x: y["defaultvalue"] for x, y in ammo_data.items()},
                "weapons": {x: False for x in weapon_data.keys()},
                "capsname": message.message_data[0],
                "health": 100,
                "bot": False,
                "fungushealth": 72,
                "stats": {
                        "Kills": 0,
                        "AIDS Overdoses": 0,
                        "Infections": 0,
                        "Buys": 0,
                        "Turns Survived": 0,
                        "Cures": 0,
                },
        }
        capsname[user.lower()] = user

        return ["You were added to the game! You are{}a mush!".format((" not " if not is_mush else " "))] + check_bot_turn()

    @c.command("smw_givemoney( (.+))?", help_string="Give money to someone on Sentient Mushes: Warzone.")
    def give_someone_dollars(conn, message, custom):
        user = message.message_data[0]

        try:
            target = custom[1].split()[0]

        except IndexError:
            return ["Give money to who?"]

        try:
            amount = int(custom[1].split()[1])

        except IndexError:
            return ["Give how much money?"]

        except ValueError:
            return ["Invalid money literal!"]

        if user.lower() not in user_data.keys():
            return ["Join first using ||smw_join !"]

        if target.lower() not in user_data.keys():
            return ["Uh? Give money to who?"]

        if user_data[user.lower()]["money"] < amount:
            return "Not enough money!"

        user_data[user.lower()]["money"] -= amount
        user_data[target.lower()]["money"] += amount

        return ["{} gave {} bucks to {}!".format(user, target, amount)]

    @c.command("smw_players( (.+))?", help_string="Player list for Sentient Mushes: Warzone.")
    def smw_player_list(conn, message, custom):
        player_list = []
        mini_player_list = []

        print user_data

        for player in user_data.keys():
            mini_player_list.append("{} ({} | {}Bot)".format(capsname[player].encode('utf-8'), ("Mush" if user_data[player]["mush"] else "Not Mush"), ("Not a " if not user_data[player]["bot"] else "")))

            if len(mini_player_list) % 30 == 0:
                player_list.append(", ".join(mini_player_list))
                mini_player_list = []

        if len(player_list) < 1 or player_list[-1] != mini_player_list[-1]:
            player_list.append(", ".join(mini_player_list))

        return ["There are {} players: ".format(len(user_data)) + player_list[0]] + player_list[1:]

    @c.command("smw_rebalance( (.+))?", 120, help_string="Rebalance the game sides for Sentient Mushes: Warzone.")
    def smw_balance_teams(conn, message, custom):
        mushies = len([user for user in user_data.values() if user["mush"]])
        humans = len([user for user in user_data.values() if not user["mush"]])
        cured = []

        if mushies == humans:
            return ["Game already balanced!"]

        if mushies > 0:
            while True:
                mushies = len([user for user in user_data.values() if user["mush"]])
                humans = len([user for user in user_data.values() if not user["mush"]])

                if mushies > humans and ((mushies + humans) % 2 == 0 or mushies > humans + 1):
                    usa, item = choice(user_data.items())
                    user_data[usa]["mush"] = False
                    user_data[usa]["immune"] = 3
                    cured.append(usa)
                    continue

                if not cured:
                    return ["Game already balanced!"]

                break

            return ["Unmushed (for balancement): " + ", ".join(cured)]

        else:
            while True:
                mushies = len([user for user in user_data.values() if user["mush"]])
                humans = len([user for user in user_data.values() if not user["mush"]])

                if humans > mushies and ((humans + mushies) % 2 == 0 or humans > mushies + 1):
                    usa, item = choice(user_data.items())
                    user_data[usa]["mush"] = True
                    cured.append(usa)
                    continue

                if not cured:
                    return ["Game already balanced!"]

                break

            return ["Mushed (for balancement): " + ", ".join(cured)]

    @c.command("smw_shoot( (.+))?", help_string="Shoot someone on Sentient Mushes: Warzone!")
    def smw_shoot(conn, message, custom):
        global turn_index

        if len(custom[1].split()) < 2:
            return ["Syntax: smw_shoot <target> <weapon>"]

        user = message.message_data[0]
        target = custom[1].split()[0]
        weapon = custom[1].split()[1]

        if user.lower() not in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        if target.lower() not in user_data.keys():
            return ["Who is that? I don't think he's aboard either."]

        if weapon not in weapon_data.keys():
            return ["Uh, did you invent that shiny new weapon?"]

        if not user_data[user.lower()]["weapons"][weapon]:
            return ["You don't have that weapon, sorry!"]

        shoot_successful = True

        result = shoot(user, target, weapon)

        if not shoot_successful:
            pass_turn()

        return result + check_bot_turn()

    @c.command("smw_extract( (.+))?", help_string="Extract a spore on Sentient Mushes: Warzone.")
    def smw_extract_spore(conn, message, custom):
        global turn_index

        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        if not user_data[user.lower()]["mush"]:
            return ["You are not one of these yet! Hey, do you want to be one?..."]

        if user_data[user.lower()]["spores"] >= 15:
            return ["Max spores reached! (15)"]

        try:
            if turns[turn_index] != user.lower().lower():
                return ["Hey! It's not your turn! Stop breaking the queue!"]

        except IndexError:
            return ["Nobody's playing! There's no turn to pass!"]

        turn_index += 1

        print turn_index

        if turn_index >= len(turns):
            turn_index = 0

        print turn_index

        user_data[user.lower()]["spores"] += 1
        return ["Extracted a spore! (now with {})".format(user_data[user.lower()]["spores"])] + check_bot_turn()

    @c.command("smw_spike( (.+))?", help_string="Do it, do it! Spike somebody today and Make Daedalus Great Again! (wait, is this game even there yet? I though we moved) Only Sentient Mushes: Warzone.")
    def spike_user_with_spore(conn, message, custom):
        global turn_index

        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        try:
            target = custom[1].split()[0]

        except IndexError:
            return ["Syntax: smw_spike <target to mushify/infect/enlighten/gah>"]

        if target.lower() not in user_data.keys():
            return ["Who is your target? Is it even aboard?"]

        if not user_data[user.lower()]["mush"]:
            return ["Where do you think you'll get spores from?"]

        if user_data[target.lower()]["mush"]:
            return ["He's already one!"]

        if user_data[user.lower()]["spores"] < 1:
            return ["You're out of spores!"]

        try:
            if turns[turn_index] != user.lower():
                return ["Hey! It's not your turn! Stop breaking the queue!"]

        except IndexError:
            return ["Nobody's playing!"]

        turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

        user_data[user.lower()]["spores"] -= 1
        user_data[target.lower()]["immune"] -= 1

        if user_data[target.lower()]["immune"] <= 0:
            user_data[target.lower()]["fungushealth"] = 72
            user_data[target.lower()]["mush"] = True
            user_data[user.lower()]["money"] += 35
            user_data[user.lower()]["stats"]["Infections"] += 1

            return ["(+35) Infection successful! Now {} is a mush!".format(target)] + check_bot_turn()

        return ["Spiking successful! But, he will take more than that; his immune system is now already {} though!".format(user_data[target.lower()]["immune"])] + check_bot_turn()

    def hug_msg(player, other):
        if user_data[player.lower()]["health"] < 50:
            msg = "{} limps to {} for a hug"

        elif user_data[player.lower()]["health"] < 30:
            msg = "{} tries to reach {} for a hug"

        elif user_data[player.lower()]["health"] < 10:
            if user_data[other.lower()]["health"] < 50:
                msg = "{} crawlhugs {} while hurt"

            else:
                msg = "{} tries to hug {}... but it hurts way too much"

        else:
            msg = "{} runs and hugs {}"

        return msg.format(player, other)

    @c.command("smw_hug( (.+))?", help_string="Show your affection for someone. Interacts with Sentient Mushes: Warzone status.")
    def smw_hugging(conn, message, custom):
        player = message.message_data[0]

        try:
            target = custom[1].split()[0]

        except IndexError:
            return ["You are huggy! Hug who?"]

        if player.lower() not in user_data.keys():
            return ["Join first using ||smw_join !"]

        if target.lower() not in user_data.keys():
            return ["Uh? Hug who? Is he even joined?"]

        real_hug = user_data[player.lower()]["mush"] != user_data[target.lower()]["mush"]

        if not real_hug:
            return ["{}! They are indeed real friends.".format(hugmsg(player, target))]

        else:
            return ["{}! {} really wants to be friends with {}, despite the \'differences\'...".format(hugmsg(player, target), player, target)]

    @c.command("smw_turn?", help_string="Who's turn in Sentient Mushes: Warzone now?")
    def smw_whos_turn(conn, message, custom):
        if len(turns) < 1:
            return "No one's turn! Who's playing?"

        return "It's now {}'s turn!".format(capsname[turns[turn_index]])

    @c.command("smw_forcepass( (.+))?", 200, help_string="Force a turn on Sentient Mushes: Warzone.")
    def force_turn_pass(conn, message, custom):
        global turn_index

        turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

        return ["Turn passed! It's now {}'s turn!".format(capsname[turns[turn_index]])] + check_bot_turn()

    @c.command("smw_pass( (.+))?", help_string="Pass your turn at Sentient Mushes: Warzone.")
    def smw_pass_turn(conn, message, custom):
        global turn_index

        user = message.message_data[0]

        try:
            if turns[turn_index] != user.lower().lower():
                return ["Hey! It's not your turn! Stop breaking the queue!"]

        except IndexError:
            return ["Nobody's playing! There's no turn to pass!"]

        turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

        return ["Turn passed! It's now {}'s turn!".format(capsname[turns[turn_index]])] + check_bot_turn()

    @c.command("smw_quit( (.+))?", help_string="Quit Sentient Mushes: Warzone.")
    def smw_quit(conn, message, custom):
        global turn_index

        user = message.message_data[0]

        if not user.lower() in user_data.keys():
            return ["You are not joined either!"]

        user_data.__delitem__(user.lower())

        if turns[turn_index] == user:
            turn_index += 1

        if turn_index >= len(turns):
            turn_index = 0

        for i, x in enumerate(turns):
            if x == user.lower():
                turns.pop(i)

        return ["Suicide successful! :3"]

    @c.command("smw_surrender( (.+))?", help_string="Do you need some Motivation?")
    def smw_surrender(conn, message, custom):
        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return "What are you surrendering from?"

        data = user_data[user.lower()]

        if data["mush"]:
            return "You could surrender to evil, but it'd not be good for you..."

        return [
                "You surrender. You want your friends back. You are fed of doing this. You aren't meant to be evil. You are just scared.",
                "Suddenly you feel like something's watching you. Like a heart has been touched, at last."
        ]

    @c.command("smw_status( (.+))?", help_string="Your status at Sentient Mushes: Warzone.")
    def smw_user_status(conn, message, custom):
        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        return " | ".join([
                "{} Status:".format(user),
                "You have {} money.".format(user_data[user.lower()]["money"]),
                "You are{}a mush.".format((" not " if not user_data[user.lower()]["mush"] else " ")),
                "You have {} health{}.".format(user_data[user.lower()]["health"], (" ({} fungus health)".format(user_data[user.lower()]["fungushealth"]) if user_data[user.lower()]["mush"] else "")),
                "You have immune system of {} in the Rehermann scale.".format(user_data[user.lower()]["immune"]),
                ("You have the following weapons: " + ", ".join(["{} ({})".format(weapon, user_data[user.lower()]["ammo"][weapon_data[weapon]["ammotype"]]) for weapon, data in user_data[user.lower()]["weapons"].items() if data]) if True in user_data[user.lower()]["weapons"].values() else "You have no guns! :("),
                ("" if not user_data[user.lower()]["mush"] else
                "You have {} spores.".format(user_data[user.lower()]["spores"]))
        ])

    @c.command("smw_getstatus( (.+))?", help_string="Get someone else's status at Sentient Mushes: Warzone.")
    def smw_get_user_status(conn, message, custom):
        try:
            target = custom[1].split()[0]

        except IndexError:
            return ["Syntax: smw_getstatus <user>"]

        if target.lower() not in user_data.keys():
            return ["Error: Target didn't join!"]

        return " | ".join([
                "{} Status:".format(target),
                "He/she has {} money.".format(user_data[target.lower()]["money"]),
                "He/she is{}a mush.".format((" not " if not user_data[target.lower()]["mush"] else " ")),
                "He/she has {} health{}.".format(user_data[target.lower()]["health"], (" ({} fungus health)".format(user_data[target.lower()]["fungushealth"]) if user_data[target.lower()]["mush"] else "")),
                "He/she has immune system of {} in the Rehermann scale.".format(user_data[target.lower()]["immune"]),
                ("He/she has the following weapons: " + ", ".join(["{} ({})".format(weapon, user_data[target.lower()]["ammo"][weapon_data[weapon]["ammotype"]]) for weapon, data in user_data[target.lower()]["weapons"].items() if data]) if True in user_data[target.lower()]["weapons"].values() else "He/she has got no guns!"),
        ] + ([] if not user_data[target.lower()]["mush"] else [
                "He/she has {} spores.".format(user_data[target.lower()]["spores"])
        ]))

    @c.command("smw_savedata( (.+))?", 85, help_string="Save Sentient Mushes: Warzone data.")
    def save_user_data(conn, message, custom):
        open("smw2_data/{}.cson".format(custom[1] if custom[1] else "default"), "w").write(dumps([user_data, turns, capsname, turn_index]))
        return "User data saved successfully!"

    @c.command("smw_loaddata( (.+))?", 85, help_string="Save Sentient Mushes: Warzone data.")
    def load_user_data(conn, message, custom):
        global user_data, turns, capsname, turn_index

        data = load(open("smw2_data/{}.cson".format(custom[1] if custom[1] else "default")))
        user_data = data[0]
        turns = data[1]
        capsname = data[2]
        turn_index = data[3]

        return "User data loaded successfully!"

    @c.command("smw_about( (.+))?", help_string="About the game..")
    def smw_about(conn, message, custom):
        return [
                "Sentient Mushes: Warzone (c) 2016 Gustavo Ramos \"Gustavo6046\" Rehermann.    Source code is MIT License.",
                "Source code at: https://www.github.com/Gustavo6046/GusBot-2 .   Sentient Mushes series; Inspired by another Twinoidian game."
        ]

    @c.command("smw_buygun( (.+))?", help_string="Buy another gun at Sentient Mushes: Warzone.")
    def smw_buy_a_big_weapon(conn, message, custom):
        user = message.message_data[0]

        if not user.lower() in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        try:
            weapon = custom[1].split()[0]

        except IndexError:
            return ["Syntax: smw_buygun <gun's name>"]

        money = user_data[user.lower()]["money"]

        if weapon not in weapon_data.keys():
            return ["You can't buy your inventions; they're already yours!", "Well, maybe of your imagination, that is... :3"]

        try:
            if user_data[user.lower()]["weapons"][weapon]:
                return ["You already have that weapon!"]

        except KeyError:
            pass

        if user_data[user.lower()]["money"] < weapon_data[weapon]["cost"]:
            return ["Too little money!"]

        user_data[user.lower()]["stats"]["Buys"] += 1
        user_data[user.lower()]["money"] -= weapon_data[weapon]["cost"]
        user_data[user.lower()]["weapons"][weapon] = True
        return "Bought weapon successfully!"

    @c.command("smw_buyammo( (.+))?", help_string="Buy ammo at Sentient Mushes: Warzone.")
    def smw_buy_some_ammo(conn, message, custom):
        user = message.message_data[0]

        if not user.lower() in user_data.keys():
            return ["Join the game first using ||smw_join !"]

        try:
            ammo_type = custom[1].split()[0]

        except IndexError:
            return ["Syntax: smw_buyammo <ammo type>"]

        money = user_data[user.lower()]["money"]

        if ammo_type not in ammo_data.keys():
            return ["You can't buy your inventions; they're already yours!", "Well, maybe of your imagination, that is... :3"]

        if user_data[user.lower()]["money"] < ammo_data[ammo_type]["cost"]:
            return ["Too little money!"]

        user_data[user.lower()]["stats"]["Buys"] += 1
        user_data[user.lower()]["money"] -= ammo_data[ammo_type]["cost"]
        user_data[user.lower()]["ammo"][ammo_type] += ammo_data[ammo_type]["amount"]
        return "Bought ammunition successfully!"

    @c.command("smw_listweaponry( (.+))?", help_string="List your guns at Sentient Mushes: Warzone.")
    def list_weaponry(conn, message, custom):
        return ["Weapons: " + ", ".join(weapon_data.keys())]

    @c.command("smw_listammotypes( (.+))?", help_string="List kinds of ammo available at Sentient Mushes: Warzone.")
    def list_ammos(conn, message, custom):
        return ["Ammo types: " + ", ".join(ammo_data.keys())]

    @c.command("smw_hide( (.+))?", help_string="Are you losing? Because this game is very unpredictable.")
    def hide_frowning_as_always(conn, message, custom):
        user = message.message_data[0]

        if user.lower() not in user_data.keys():
            return ["You hide... but why? Are you really hiding or did you mean to hide inminigame?"]

        if user_data[user.lower()]["mush"]:
            return ["You hide somewhere, frowning. You want to get out of the confusion.", "You didn't want to be enemy of anyone.", "Suddenly, you realize. Hearts are emotionally weak. With this in mind, there must be a way out!"]

        return ["You hide somewhere, frowning. You miss your friends.", "Maybe if you show your sadness and maybe surrender, since you might not be able to fight back..."]

    @c.global_receiver(r"([^\!])\![^@]@[^ ] NICK :(.+)")
    def get_nick_changes(conn, msg, custom):
        if not raw:
            return

        old_nick = custom[1].split()[0]

        try:
            new_nick = custom[1].split()[1]

        except IndexError:
            return

        print "{} -> {}".format(old_nick, new_nick)

        while True:
            if old_nick not in user_data.keys():
                break

            user_data[new_nick.lower()] = user_data[old_nick.lower()]
            user_data.__delitem__(old_nick.lower())

            capsname[new_nick.lower()] = new_nick
            del caps_name[old_nick.lower()]

            break

        for i, user in enumerate(turns):
            if user == old_nick:
                turns.pop(i)
                turns.insert(i, new_nick)

    @c.command("smw_resetmatch( (.+))?", 160, help_string="Reset Sentient Mushes: Warzone.")
    def reset_smw_match(conn, message, custom):
        global turn_index

        user_data = {}
        turns = []
        turn_index = 0

        return ["Reset with success!", "...Anyone gonna join now?"]

    @c.command("smw_cost( (.+))?", help_string="Get cost of something Sentient Mushes: Warzone.")
    def get_smw_gun_cost(conn, message, custom):
        object = " ".join(custom[1].split())

        if object in ammo_data.keys():
            return ["That ammo costs {}.".format(ammo_data[object]["cost"])]

        elif object in weapon_data.keys():
            return ["That weapon costs {}.".format(weapon_data[object]["cost"])]

        elif object in user_data.keys():
            return ["A friendship is for free! :D <3"]

        else:
            return ["What's that?"]

    @c.command("smw_kick( (.+))?", 180, help_string="Clear Sentient Mushes: Warzone of actual spambaddies!")
    def kick_smw_player(conn, message, custom):
        global turn_index

        try:
            user = " ".join(custom[1].split())

        except IndexError:
            return ["Syntax: smw_kick <user to kick from game>"]

        if not user.lower() in user_data.keys():
            return ["He's not joined either!"]

        user_data.__delitem__(user.lower())

        if turns[turn_index] == user:
            turn_index += 1

            if turn_index >= len(turns):
                turn_index = 0

        for i, x in enumerate(turns):
            if x == user.lower():
                turns.pop(i)

        return ["User kicked successfully!"]

    @c.command("smw_addnames( (.+))?", help_string="Contribute another new bot name for Sentient Mushes: Warzone.")
    def add_bot_name(conn, message, custom):
        open("botnames.txt", "a").writelines(["\n{}".format(l) for l in custom[1].split()])
        return "Names added successfully!"

    @c.command("smw_forcejoin( (.+))?", 235, help_string="Force someone to join Sentient Mushes: Warzone! (NOT RECOMMENDED)")
    def force_player_join(conn, message, custom):
        if len(custom[1].split()) < 1:
            return "Syntax: smw_forcejoin <user> [user [...]]"

        users = custom[1].split()

        messages = []

        for user in users:
            is_mush = percent_chance(48)

            if user.lower() in user_data.keys():
                messages.append("{user} already joined the game!".format(user=user))
                continue

            turns.append(user.lower())

            user_data[user.lower()] = {
                    "host": "{}!{}@{}".format(*message.message_data[:3]),
                    "money": 30,
                    "mush": is_mush,
                    "spores": 6,
                    "immune": 3,
                    "ammo": {x: y["defaultvalue"] for x, y in ammo_data.items()},
                    "weapons": {x: False for x in weapon_data.keys()},
                    "capsname": message.message_data[0],
                    "health": 100,
                    "bot": False,
                    "fungushealth": 72,
                    "stats": {
                            "Kills": 0,
                            "AIDS Overdoses": 0,
                            "Infections": 0,
                            "Buys": 0,
                            "Turns Survived": 0,
                            "Cures": 0,
                    },
            }
            capsname[user.lower()] = user

            messages.append("{User} was added to the game! He's{}a mush!".format(" not " if not is_mush else " ", User=user))

        return messages


    @c.command("smw_togglemush( (.+))?", 240, help_string="Toggle someone's mushiness Sentient Mushes: Warzone.")
    def toggle_mush(conn, message, custom):
        if len(custom[1].split()) < 1:
            return "Syntax: smw_togglemush <number of people to turn into mush>"

        user_data = dict({x: dict(user_data[x], mush=not user_data[x]["mush"]) for x in custom[1].split()}, **{x: y for x, y in user_data.items() if x not in custom[1].split()})

        return "Toggled users successfully!"

    @c.command("smw_help( (.+))?", help_string="Get help at Sentient Mushes: Warzone.")
    def smw_help(conn, message, custom):
        def send_notices(mesgs):
            for item in mesgs:
                conn.send_command("NOTICE {} :{}".format(message.message_data[0], item.encode("utf-8")))

        conn.send_message(message.message_data[3] if message.message_data[3].startswith("#") else message.message_data[0], "Sending you help via notice.")

        send_notices((
                "Join using smw_join. If you are mush, use smw_extract to get more spores (or smw_findspore) and smw_spike to in--I mean \"enlighten\". Or else, buy some good gun using smw_buygun and smw_buyammo. (List them and ammo using smw_listweaponry and smw_listammotypes!)",
                "Use smw_about for etc stuff or use smw_hide for a consolation message!", "Use smw_cost to get cost of stuff. Always remember: friendship is for FREE! <3",
                "Use smw_shoot <target> <weapon> to shoot at someone. Use smw_eat to regain immune/fungushealth. And smw_status to get your status and smw_getstatus to get other people's status!",
                "Some commands are turn-only. Check who's turn using smw_turn and check the turn queue using smw_turns! And check who is playing (and whether they're mush) using smw_players. Remember: instead of paranoia like in the original, use strategy! ;)"
        ))

        conn.send_message(message.message_data[3] if message.message_data[3].startswith("#") else message.message_data[0], "Sent you help!")

    @c.command("smw_cbm( (.+))?", 190, help_string="Make uglier (but compact) bot messages at Sentient Mushes: Warzone.")
    def condense_them(conn, message, custom):
        global condense_bot_messages

        condense_bot_messages = not condense_bot_messages
        return "Now {}condensing bot messages!".format(("not " if not condense_bot_messages else ""))
