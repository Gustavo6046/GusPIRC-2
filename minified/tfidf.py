from __future__ import division
import math
def tf(word,text):
 return text.split(" ").count(word)/len(text.split(" "))
def n_containing(word,text,textlist):
 return sum(1 for atxt in textlist if word in atxt.split(" ")and atxt!=text)
def idf(word,text,textlist):
 return math.log(len(textlist)/(1+n_containing(word,text,textlist)))
def tfidf(word,text,textlist):
 return tf(word,text)*idf(word,text,textlist)
def get_top(num_words,text,all_texts):
 scores={word:tfidf(word,text,all_texts)for word in text.split(" ")}
 return dict(sorted(scores.items(),key=lambda x:x[1],reverse=True)[:num_words])
# Created by pyminifier (https://github.com/liftoff/pyminifier)
