from restful_rfcat import config, persistence
import mock
import os
import shutil
import tempfile
import Queue
import unittest

class TestHideyHole(unittest.TestCase):
	def setUp(self):
		self._dirname = tempfile.mkdtemp()
		config.PERSISTENCE = [persistence.HideyHole(self._dirname)]

	def tearDown(self):
		shutil.rmtree(self._dirname)

	def test_empty(self):
		self.assertEqual(None, persistence.get('nonexistent'))

	def test_save(self):
		key = "key_name"
		data = "Test"
		persistence.set(key, data)
		self.assertEqual(data, persistence.get(key))

	def test_get_wrong_name(self):
		key = "key_name"
		data = "Test"
		persistence.set(key, data)
		self.assertEqual(None, persistence.get(key+"Wrong"))

	def test_saved_to_right_place(self):
		key = "key_name"
		data = "Test"
		persistence.set(key, data)
		dir_contents = os.listdir(self._dirname)
		self.assertEqual(set([key]), set(dir_contents))

class TestMQTT(unittest.TestCase):
	def setUp(self):
		self.mock = mock.Mock()
		settings = {
			"_publish": self.mock
		}
		config.PERSISTENCE = [persistence.MQTT(**settings)]

	def test_get(self):
		self.assertEqual(None, persistence.get("keyname"))

	def test_set(self):
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "lights/fan")
		self.assertEqual(call_args[1]['payload'], "value")

	def test_prefix(self):
		settings = {
			"_publish": self.mock,
			"prefix": "testname"
		}
		config.PERSISTENCE = [persistence.MQTT(**settings)]
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "testname/lights/fan")
		self.assertEqual(call_args[1]['payload'], "value")

	def test_prefix_slash(self):
		settings = {
			"_publish": self.mock,
			"prefix": "/testname/"
		}
		config.PERSISTENCE = [persistence.MQTT(**settings)]
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "/testname/lights/fan")
		self.assertEqual(call_args[1]['payload'], "value")

	def test_failure(self):
		# should swallow errors when setting
		import paho.mqtt
		self.mock.single.side_effect = paho.mqtt.MQTTException("Failure")
		persistence.set("lights/fan", "value")
