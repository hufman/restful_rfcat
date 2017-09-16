from restful_rfcat import drivers, pubsub
import Queue
import unittest

class TestPubSubDriver(unittest.TestCase):
	""" Tests that drivers properly send to pubsub when changed """
	def tearDown(self):
		# release the lock
		pubsub.queue_management_lock.acquire(False)
		pubsub.queue_management_lock.release()
		# clear all the subscribers
		pubsub.topic_subscribers.clear()

	def test_publish_no_subscriptions(self):
		device = drivers.FakeLight(name="test", label="Test")
		device.set_state("ON")

	def test_publish_subscriptions(self):
		device = drivers.FakeLight(name="test", label="Test")
		with pubsub.subscribe() as event_source:
			self.assertEqual(0, event_source.qsize())
			device.set_state("ON")
			self.assertEqual(1, event_source.qsize())
			event = event_source.get(False)
			self.assertEqual(device, event['device'])
			self.assertEqual("ON", event['state'])

