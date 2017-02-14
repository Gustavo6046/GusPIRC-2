from Queue import Queue, Empty


class IterableQueue(Queue, object):
	def __init__(self):
		super(IterableQueue, self).__init__()
		self.past_items = []
		
	def __iter__(self):
		return self
		
	def next(self):
		x = self.iterate()
		
		if x == None:
			raise StopIteration
			
		return x
		
	def iterate(self):
		try:
			new = self.get_nowait()
			self.past_items.append(new)

			return new
			
		except Empty:
			for x in self.past_items:
				self.put_nowait(x)
		
			return None

	def flush(self):
		while not self.empty():
			self.get_nowait()

	def set_to_iterator(self, iterator=(), flush_before_putting_iterator=False):
		if flush_before_putting_iterator:
			self.flush()

		for x in iterator:
			self.put_nowait(x)

		return self

	def __len__(self):
		return self.qsize()
