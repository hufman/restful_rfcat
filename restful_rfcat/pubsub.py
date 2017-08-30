import Queue
import threading

queue_management_lock = threading.Lock()

topic_subscribers = {}

class Pubsub():
	def __init__(self, topic=""):
		self.topic = topic
		self.queue = None
	def __enter__(self):
		# add a queue to a bucket
		with queue_management_lock:
			if self.topic not in topic_subscribers:
				topic_subscribers[self.topic] = []
			self.queue = Queue.Queue()
			topic_subscribers[self.topic].append(self.queue)
			return self.queue
	def __exit__(self, *args):
		# remove the queue
		with queue_management_lock:
			if self.queue is not None and self.topic in topic_subscribers and self.queue in topic_subscribers[self.topic]:
				topic_subscribers[self.topic].remove(self.queue)

def subscribe(topic=""):
	return Pubsub(topic)

def publish(topic="", data=None):
	if data is None:
		raise ValueError("Empty data to publish")
	with queue_management_lock:
		topic_subs = list(topic_subscribers[topic])
	for sub in topic_subs:
		sub.put_nowait(data)
