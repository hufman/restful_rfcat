from restful_rfcat import config, drivers, persistence
import json
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

	def test_retain_default_true(self):
		settings = {
			"_publish": self.mock,
		}
		config.PERSISTENCE = [persistence.MQTT(**settings)]
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "lights/fan")
		self.assertEqual(call_args[1]['retain'], True)

	def test_retain_false(self):
		settings = {
			"_publish": self.mock,
			"retain": False
		}
		config.PERSISTENCE = [persistence.MQTT(**settings)]
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "lights/fan")
		self.assertEqual(call_args[1]['retain'], False)

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

class TestMQTTHomeAssistant(unittest.TestCase):
	def setUp(self):
		self.mock = mock.Mock()
		settings = {
			"_publish": self.mock
		}
		config.PERSISTENCE = [persistence.MQTTHomeAssistant(**settings)]

	def test_discovery_empty(self):
		self.mock.multiple.assert_not_called()

	def test_discovery(self):
		device_settings = {
			"name": "fake",
			"label": "Fake Device"
		}
		settings = {
			"_publish": self.mock,
			"discovery_devices": [
				drivers.FakeFan(**device_settings),
				drivers.FakeLight(**device_settings)
			]
		}
		config.PERSISTENCE = [persistence.MQTTHomeAssistant(**settings)]
		msgs = self.mock.multiple.call_args[0][0]
		self.assertEqual(2, len(msgs))	# two devices were announced
		self.assertEqual('homeassistant/fan/fans_fake/config', msgs[0]['topic'])
		self.assertEqual('homeassistant/light/lights_fake/config', msgs[1]['topic'])
		fan = json.loads(msgs[0]['payload'])
		desired_fan = {
			'name': 'Fake Device',
			'state_topic': 'homeassistant/fan/fans_fake/state',
			'command_topic': 'homeassistant/fan/fans_fake/set',
		}
		self.assertEqual(desired_fan, fan)

	def test_discovery_custom_prefix(self):
		device_settings = {
			"name": "fake",
			"label": "Fake Device"
		}
		settings = {
			"_publish": self.mock,
			"discovery_prefix": "myhass",
			"discovery_devices": [
				drivers.FakeFan(**device_settings),
				drivers.FakeLight(**device_settings)
			]
		}
		config.PERSISTENCE = [persistence.MQTTHomeAssistant(**settings)]
		msgs = self.mock.multiple.call_args[0][0]
		self.assertEqual(2, len(msgs))	# two devices were announced
		self.assertEqual('myhass/fan/fans_fake/config', msgs[0]['topic'])
		self.assertEqual('myhass/light/lights_fake/config', msgs[1]['topic'])
		fan = json.loads(msgs[0]['payload'])
		desired_fan = {
			'name': 'Fake Device',
			'state_topic': 'myhass/fan/fans_fake/state',
			'command_topic': 'myhass/fan/fans_fake/set',
		}
		self.assertEqual(desired_fan, fan)

	def test_get(self):
		self.assertEqual(None, persistence.get("keyname"))

	def test_set(self):
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "homeassistant/light/lights_fan/state")
		self.assertEqual(call_args[1]['payload'], "value")

	def test_set_custom_prefix(self):
		settings = {
			"_publish": self.mock,
			"discovery_prefix": "myhass",
		}
		config.PERSISTENCE = [persistence.MQTTHomeAssistant(**settings)]
		persistence.set("lights/fan", "value")
		call_args = self.mock.single.call_args
		self.assertEqual(call_args[0][0], "myhass/light/lights_fan/state")
		self.assertEqual(call_args[1]['payload'], "value")

	def test_failure(self):
		# should swallow errors when setting
		import paho.mqtt
		self.mock.single.side_effect = paho.mqtt.MQTTException("Failure")
		persistence.set("lights/fan", "value")

class TestRedis(unittest.TestCase):
	def setUp(self):
		self.mock = mock.Mock()
		settings = {
			"client": self.mock
		}
		config.PERSISTENCE = [persistence.Redis(**settings)]

	def test_get(self):
		self.mock.get.side_effect = lambda key:None
		self.assertEqual(None, persistence.get("keyname"))
		self.mock.get.assert_called_once_with("keyname")

	def test_set(self):
		persistence.set("lights/fan", "value")
		self.mock.set.assert_called_once_with("lights/fan", "value")
		self.mock.publish.assert_called_once_with("lights/fan", "value")

	def test_set_no_publish(self):
		settings = {
			"client": self.mock,
			"publish": False,
		}
		config.PERSISTENCE = [persistence.Redis(**settings)]
		persistence.set("lights/fan", "value")
		self.mock.set.assert_called_once_with("lights/fan", "value")
		self.mock.publish.assert_not_called()

	def test_set_only_publish(self):
		settings = {
			"client": self.mock,
			"db": None,
		}
		config.PERSISTENCE = [persistence.Redis(**settings)]
		persistence.set("lights/fan", "value")
		self.assertEqual(None, persistence.get("lights/fan"))
		self.mock.set.assert_not_called()
		self.mock.get.assert_not_called()
		self.mock.publish.assert_called_once_with("lights/fan", "value")

	def test_prefix(self):
		settings = {
			"client": self.mock,
			"prefix": "testname"
		}
		config.PERSISTENCE = [persistence.Redis(**settings)]
		persistence.set("lights/fan", "value")
		self.mock.set.assert_called_once_with("testname/lights/fan", "value")
		self.mock.publish.assert_called_once_with("testname/lights/fan", "value")

	def test_prefix_slash(self):
		settings = {
			"client": self.mock,
			"prefix": "/testname/"
		}
		config.PERSISTENCE = [persistence.Redis(**settings)]
		persistence.set("lights/fan", "value")
		self.mock.set.assert_called_once_with("/testname/lights/fan", "value")
		self.mock.publish.assert_called_once_with("/testname/lights/fan", "value")

	def test_failure(self):
		# should swallow errors when setting
		self.mock.get.side_effect = IOError("Failure")
		self.mock.set.side_effect = IOError("Failure")
		persistence.get("lights/fan")
		persistence.set("lights/fan", "value")
