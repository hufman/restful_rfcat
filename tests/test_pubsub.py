from restful_rfcat import pubsub
import Queue
import unittest

class TestPubSub(unittest.TestCase):
	def tearDown(self):
		# release the lock
		pubsub.queue_management_lock.acquire(False)
		pubsub.queue_management_lock.release()
		# clear all the subscribers
		pubsub.topic_subscribers.clear()

	def test_empty_subscribe(self):
		with pubsub.subscribe() as event_source:
			assert True

	def test_empty_publish(self):
		pubsub.publish("Data")

	def test_simple_publish(self):
		with pubsub.subscribe() as event_source:
			pubsub.publish("data")
			self.assertEqual("data", event_source.get(False))

	def test_early_publish(self):
		pubsub.publish("data", topic="queuename")
		with pubsub.subscribe("queuename") as event_source:
			self.assertEqual(0, event_source.qsize())

	def test_late_publish(self):
		with pubsub.subscribe("queuename") as event_source:
			self.assertEqual(0, event_source.qsize())
		pubsub.publish("data", topic="queuename")
		with pubsub.subscribe("queuename") as event_source:
			self.assertEqual(0, event_source.qsize())

	def test_named_publish(self):
		with pubsub.subscribe("queuename") as event_source:
			pubsub.publish("data", topic="queuename")
			self.assertEqual("data", event_source.get(False))

	def test_named_mismatch_publish(self):
		with pubsub.subscribe("queuename") as event_source:
			pubsub.publish("data")
			try:
				data = event_source.get(False)
				assert False, "Should not have received data %s"%(data,)
			except Queue.Empty:
				assert True

	def test_dropped_queue(self):
		with pubsub.subscribe() as event_source:
			pubsub.publish("data")
			self.assertEqual(1, event_source.qsize())
		with pubsub.subscribe() as event_source:
			self.assertEqual(0, event_source.qsize())
			try:
				data = event_source.get(False)
				assert False, "Should not have seen data %s"%(data,)
			except Queue.Empty:
				assert True
