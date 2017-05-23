import base64
import struct
from PIL import Image as img
from itertools import product
debug=False
class Heighter(object):
 def __init__(self,size=(3,3),default=0):
  self.size=list(size[:2])
  try:
   self.data=[[default(x,y)for x in xrange(size[0])]for y in xrange(size[1])]
  except TypeError:
   try:
    self.data=[[default((x,y))for x in xrange(size[0])]for y in xrange(size[1])]
   except TypeError:
    if hasattr(default,"__call__"):
     self.data=[[default()for x in xrange(size[0])]for y in xrange(size[1])]
    else:
     try:
      self.data=[[float(default)]*size[0]for _ in xrange(size[1])]
     except TypeError:
      self.data=default
 def render(self,chars=(".",",","-","+","o","O","@"),specials=()):
  specials=dict(specials)
  res=""
  for y,r in enumerate(self.data):
   for x,s in enumerate(r):
    if(x,y)not in specials:
     ind=int(((float(s)-min(v for g in self.data for v in g))/(max(v for g in self.data for v in g)-min(v for g in self.data for v in g)))*len(chars))-1
     if debug:print ind,
     res+=chars[ind]
    else:
     res+=specials[x,y]
   if y<len(self.data)-1:
    res+="\n"
   if debug:print
  return res
 def __str__(self):
  return self.render()
 def binary(self):
  res=struct.pack("II",*self.size)
  for r in self.data:
   for s in r:
    res+=struct.pack("f",s)
  return res
 def serialize(self):
  return base64.b64encode(self.binary())
 def to_image(self,filename):
  i=img.new("F",self.size)
  i.putdata(self.data)
  i.save(filename)
  return i
 @classmethod
 def unbinary(cls,bindata):
  width,height=struct.unpack("II",bindata[:8])
  line=struct.unpack("f"*(width*height),bindata[8:])
  h=cls((width,height))
  h.data=[line[i:i+height]for i in xrange(0,len(line),height)]
  return h
 @classmethod
 def deserialize(cls,stuff):
  return cls.unbinary(base64.b64decode(stuff))
 @classmethod
 def from_image(cls,filename):
  i=img.open(open(filename))
  i.convert("F")
  h=cls(i.size)
  for x,y in[(x,y)for x in xrange(i.size[0])for y in xrange(i.size[1])]:
   h.map[x,y]=i.getpixel((x,y))
  return h
 def resize(self,x,y):
  self.size=[x,y]
# Created by pyminifier (https://github.com/liftoff/pyminifier)
