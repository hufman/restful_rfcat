"""
This module implements a shared PubSub bus.
Each topic has a list of Queue objects that will receive published data.
The subscribe() method acts as a context manager, to facilitate
clean disposal of the Queue at exit.
The standard Queue object methods apply, such as get(blocking, timeout)
The module has a .publish() method, to send data to every queues for a topic
"""
import Queue
import threading

# hold to change the subscribers
queue_management_lock = threading.Lock()

topic_subscribers = {}

class PubsubSubscription():
	def __init__(self, topic=""):
		self.topic = topic
		self.queue = None
	def __enter__(self):
		# add a queue to the list of subscribers for a topic
		with queue_management_lock:
			if self.topic not in topic_subscribers:
				topic_subscribers[self.topic] = []
			self.queue = Queue.Queue()
			topic_subscribers[self.topic].append(self.queue)
			return self.queue
	def __exit__(self, *args):
		# remove the queue from the list of subscribers
		with queue_management_lock:
			if self.queue is not None and \
			   self.topic in topic_subscribers and \
			   self.queue in topic_subscribers[self.topic]:
				topic_subscribers[self.topic].remove(self.queue)
		self.queue = None

def subscribe(topic=""):
	"""
	Subscribes to a topic, as a context manager, returning a queue

	with pubsub.subscribe() as event_queue:
		data = event_queue.get()
	"""
	return PubsubSubscription(topic)

def publish(data, topic=""):
	"""
	Publishes data to all of the queues for a given topic
	No serialization is provided, raw Python objects are supported

	pubsub.publish(data)
	"""
	# get a coherent list of subscribers
	with queue_management_lock:
		topic_subs = list(topic_subscribers.get(topic, []))
	# send the data
	for sub in topic_subs:
		sub.put_nowait(data)
