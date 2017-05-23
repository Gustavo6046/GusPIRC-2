import queue
import threading
import re
import requests
import os
import time
import traceback
import urlparse
from bs4 import BeautifulSoup
no_ext=re.compile(r"^\/([a-zA-Z0-9_]+\.php)(\/)?(.*)?$")
def is_absolute(url):
 return bool(urlparse.urlparse(url).netloc)
def ensure_url(u,default_schema="http",base=""):
 if((not is_absolute(u))or u.startswith("/"))and base:
  u=urlparse.urljoin(ensure_url(base),u)
 if not(u.startswith("http://")or u.startswith("https://")or u.startswith(default_schema)):
  u="{}://{}".format(default_schema,u)
 return u
class WebSpider(object):
 max_level=2
 link_regex=r"http\:\/\/.*"
 exclude_regex="a^"
 name="DataSpider"
 non_webpages=False
 verbose=False
 max_threads=12
 def __init__(self):
  self.link_regex=re.compile(type(self).link_regex)
  self.raw_regex=type(self).link_regex
  self.exclude_regex=re.compile(type(self).exclude_regex)
  self.raw_exregex=type(self).exclude_regex
  self.link_queue=queue.LifoQueue()
  self.iter_queue=[]
  self.stop=False
  self.threads=0
 def next_link(self):
  return self.link_queue.get()
 def parse(self,soup,url,level):
  pass 
 def try_link(self,link,base,level):
  url=link['href']
  if url in("","/","#"):
   return
  m=self.link_regex.match(url)
  em=self.exclude_regex.match(url)
  if m is None or em is not None:
   return
  try:
   response=requests.head(ensure_url(link["href"],"http",base),timeout=15)
  except BaseException as err:
   return
  if url in self.iter_queue:
   return
  try:
   if not("text/html" in response.headers["content-type"]or "text/php" in response.headers["content-type"]or getattr(type(self),"non_webpages",False)):
    return
  except KeyError:
   return
  if type(self).verbose:print "{}Queuing {}!".format(") "*level,url)
  self.link_queue.put({"link":ensure_url(link["href"],"http",base),"level":level+1})
  self.iter_queue.append(url)
 def get_links(self,soup,url,level=0):
  for link in soup.find_all('a',href=True):
   threading.Thread(target=self.try_link,args=(link,url,level)).start()
 def __del__(self):
  self.terminate()
 def next(self,max_level):
  try:
   l=self.next_link()
  except queue.empty:
   return True
  if l["level"]<=max_level:
   try:
    response=requests.get(l["link"],timeout=10)
   except BaseException:
    return False
   threading.Thread(target=self.crawl,args=(response,l["link"],max_level,l["level"]+1)).start()
   return True
  return False
 def crawl(self,response,url,max_level=2,level=0):
  url=response.url
  if self.stop:
   return
  while self.threads>getattr(type(self),"max_threads",6):
   time.sleep(0.3)
  if getattr(type(self),"verbose",False):
   print "{}Crawled to {}!".format(") "*level,url)
  self.threads+=1
  soup=BeautifulSoup(response.content)
  self.parse(soup,url,level)
  self.get_links(soup,url,level)
  self.threads-=1
  while self.threads<=type(self).max_threads:self.next(max_level)
 def run(self,url):
  print "## Running crawler at {}".format(url)
  req=requests.get(ensure_url(url),timeout=10)
  t=threading.Thread(target=self.crawl,args=(req,url,getattr(type(self),"max_level",2)))
  t.start()
  return t
 def post_crawl(self):
  self.iter_queue=[]
 def terminate(self):
  self.stop=True
  while self.threads>0:time.sleep(0.4)
  self.stop=False
class DemoSpider(WebSpider):
 max_level=1
 def parse(self,soup,url,level):
  print "{}Hello {}!".format(") "*level,url)
if __name__=="__main__":
 DemoSpider().parse()
# Created by pyminifier (https://github.com/liftoff/pyminifier)
