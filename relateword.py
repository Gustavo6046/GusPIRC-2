import time

from tfidf import get_top
from sys import maxunicode
from pybrain.tools.shortcuts import buildNetwork
from cson import dumps, loads


common_filter = "abcdefghijklmnopqrstuvwxyz-_123456789"

def filter_string(s, chars, lower=True):
    if lower:
        s = s.lower()

    return "".join([l for l in s if l in chars])

class AutoDictionary(object):
    def __init__(self, max_time=172800):
        self.historic = []
        self.times = []
        self.def_cache = {}
        self.perm_def = {}

        self.max_time = max_time

    def parse(self, string, ratio=0.4, relation_ratio=0.6):
        self.load_in("autodict.cson")

        self.historic.append(string)
        self.times.append(time.time())

        self.def_cache = self.perm_def

        important_words = get_top(int(float(len(string.split(" "))) * ratio), string, self.historic)
        important_words_2 = get_top(int(float(len(string.split(" "))) * relation_ratio), string, self.historic)

        for i in important_words.keys():
            i = filter_string(i, common_filter)

            for i2 in important_words_2.keys():
                i2 = filter_string(i2, common_filter)

                if i != i2:
                    if i in self.def_cache:
                        self.def_cache[i].append(i2)

                    else:
                        self.def_cache[i] = [i2]

    def cache_historic(self, ratio=0.325, relation_ratio=0.4):
        h = [x for i, x in enumerate(self.historic) if time.time() - self.times[i] < self.max_time]
        t = [self.times[i] for i, x in enumerate(self.historic) if time.time() - self.times[i] < self.max_time]

        for h in self.historic:
            important_words = get_top(int(float(len(h.split(" "))) * ratio), h, self.historic)
            important_words_2 = get_top(int(float(len(h.split(" "))) * relation_ratio), h, self.historic)

            for i in important_words.keys():
                i = filter_string(i, common_filter)

                for i2 in important_words_2.keys():
                    i2 = filter_string(i2, common_filter)

                    if i != i2:
                        if i in self.def_cache:
                            self.def_cache[i].append(i2)

                        else:
                            self.def_cache[i] = [i2]

    def perm_parse(self, string, ratio=0.325, relation_ratio=0.75):
        self.load_in("autodict.cson")

        self.historic.append(string)
        self.times.append(time.time())

        self.historic = [x for i, x in enumerate(self.historic) if time.time() - self.times[i] < self.max_time]

        important_words = get_top(int(float(len(string.split(" "))) * ratio), string, self.historic)
        important_words_2 = get_top(int(float(len(string.split(" "))) * relation_ratio), string, self.historic)

        for i in important_words.keys():
            i = filter_string(i, common_filter)

            for i2 in important_words_2.keys():
                i2 = filter_string(i2, common_filter)

                if i != i2:
                    if i in self.def_cache:
                        self.perm_def[i].append(i2)

                    else:
                        self.perm_def[i] = [i2]

    def define(self, word, sync=None):
        if sync:
            this = type(self).load(sync)

            self.historic = this.historic
            self.times = this.times
            self.perm_def = this.perm_def

        else:
            this = self

        try:
            return this.def_cache[word.lower()]

        except KeyError:
            return []

    def load_in(self, filename, empty_default=True):
        try:
            self.historic, self.times, self.perm_def = loads(open(filename).read())

        except IOError:
            if empty_default:
                self.historic, self.times, = [], []
                self.perm_def = {}

            else:
                return False

        return True

    def load_me(self, filename):
        self.historic, self.times, self.perm_def = loads(open(filename).read())

    @classmethod
    def load(cls, filename):
        _new = cls()

        try:
            _new.historic, _new.times, _new.perm_def = loads(open(filename).read())

        except IOError:
            return None

        return _new

    def save(self, filename):
        open(filename, "w").write(dumps([self.historic, self.times, self.perm_def]))
