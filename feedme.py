import time
import functools
import feedparser
import requests
import threading


class RSSParser(object):
    def get_time(self, entry):
        return time.mktime(entry.published_parsed)

    def is_new(self, entry):
        return self.get_time(entry) > self.last

    def __init__(self, url, parse_func, old_too=True, interval=60):
        self.url = url
        self.interval = interval
        self.parse_func = parse_func
        self.last = (0 if old_too else time.time())

        self._stop = False

        if interval:
            threading.Thread(target=self.loop).start()

    def loop(self):
        while not self._stop:
            a = feedparser.parse(self.url)
            stuff = sorted([x for x in a.entries if self.is_new(x)], key=self.get_time)

            for s in stuff:
                self.parse_func(s)

            self.last = self.get_time(sorted(a.entries, key=self.get_time)[-1])
            time.sleep(self.interval)

    def stop(self):
        self._stop = True

    def set_func(self, f):
        self.parse_func = f

class RSSPool(object):
    def __init__(self, urls=(), interval=60):
        self.urls = list(urls)
        self.parsers = {n: RSSParser(u, functools.partial(self._get, n), interval) for n, u in dict(urls).items()}
        self.interval = interval
        self.hooks = []

    def _get(self, name, entry):
        for h in self.hooks:
            h(self, name, entry)

    def names(self):
        return self.parsers.keys()

    def hook(self, func):
        self.hooks.append(func)

    def add_urls(self, old_too=True, urls=()):
        urls = dict(urls)
        self.urls += list(urls)
        self.parsers.update({n: RSSParser(u, functools.partial(self._get, n), old_too, self.interval) for n, u in urls.items()})

    def remove_names(self, exclude):
        self.exclude = {a: b for a, b in self.urls.items() if a not in exclude}
        self.parsers = {a: b for a, b in self.parsers.items() if a not in exclude}

    def stop(self):
        for h in self.hooks:
            h.stop()
