from restful_rfcat import config, drivers, persistence, pubsub
import shutil
import tempfile
import unittest

def events_summary(queue):
	""" Consumes all of a Queue full of device:state announcements
	    and remembers the last state of each
	"""
	states = {}
	while not queue.empty():
		event = queue.get_nowait()
		device_name = event['device']._state_path()
		states[device_name] = event['state']
	return states

class TestDriverFake(unittest.TestCase):
	def setUp(self):
		self._dirname = tempfile.mkdtemp()
		config.PERSISTENCE = [persistence.HideyHole(self._dirname)]

	def tearDown(self):
		shutil.rmtree(self._dirname)

	def test_create(self):
		dev = drivers.FakeFan(name="test", label="Test")
		dev = drivers.FakeLight(name="test", label="Test")

	def test_class(self):
		fan = drivers.FakeFan(name="test", label="Test")
		self.assertEqual('fans', fan.get_class())
		light = drivers.FakeLight(name="test", label="Test")
		self.assertEqual('lights', light.get_class())

	def test_state(self):
		light = drivers.FakeLight(name="test", label="Test")
		light.set_state("ON")
		self.assertEqual("ON", light.get_state())
		light.set_state("OFF")
		self.assertEqual("OFF", light.get_state())
		self.assertEqual(set(["ON", "OFF"]), set(light.get_available_states()))
		fan = drivers.FakeFan(name="test", label="Test")
		self.assertEqual(set(["OFF", "ON"]), set(fan.get_available_states()))
		self.assertEqual(set(["OFF", "ON"]), set(fan.subdevices['power'].get_available_states()))
		self.assertEqual(set(["1", "2", "3"]), set(fan.subdevices['speed'].get_available_states()))
		self.assertEqual(set(["0", "1", "2", "3"]), set(fan.subdevices['command'].get_available_states()))

	# test out new subdevices
	def test_fan_root_firsttime(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan.set_state("ON")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("1", fan.subdevices['speed'].get_state())
			self.assertEqual("1", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("1", events['fans/test/speed'])
		self.assertEqual("1", events['fans/test/command'])

	def test_fan_power_firsttime(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan.subdevices['power'].set_state("ON")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("1", fan.subdevices['speed'].get_state())
			self.assertEqual("1", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("1", events['fans/test/speed'])
		self.assertEqual("1", events['fans/test/command'])

	def test_fan_speed_firsttime(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan.subdevices['speed'].set_state("2")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("2", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("2", events['fans/test/speed'])
		self.assertEqual("2", events['fans/test/command'])

	def test_fan_root_resumespeed(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan.subdevices['speed'].set_state("2")
			fan.set_state("OFF")
			self.assertEqual("OFF", fan.get_state())
			self.assertEqual("OFF", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("0", fan.subdevices['command'].get_state())
			fan.set_state("ON")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("2", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("2", events['fans/test/speed'])
		self.assertEqual("2", events['fans/test/command'])

	def test_fan_power_resumespeed(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan.subdevices['speed'].set_state("2")
			fan.subdevices['power'].set_state("OFF")
			self.assertEqual("OFF", fan.get_state())
			self.assertEqual("OFF", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("0", fan.subdevices['command'].get_state())
			fan.subdevices['power'].set_state("ON")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("2", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("2", events['fans/test/speed'])
		self.assertEqual("2", events['fans/test/command'])

	def test_fan_command(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan.subdevices['command'].set_state("2")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("2", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("2", events['fans/test/speed'])
		self.assertEqual("2", events['fans/test/command'])

	def test_fan_eavesdrop(self):
		with pubsub.subscribe() as event_source:
			fan = drivers.FakeFan(name="test", label="Test")
			fan._handle_state_update("2")
			self.assertEqual("ON", fan.get_state())
			self.assertEqual("ON", fan.subdevices['power'].get_state())
			self.assertEqual("2", fan.subdevices['speed'].get_state())
			self.assertEqual("2", fan.subdevices['command'].get_state())
			# collect events
			events = events_summary(event_source)
		self.assertEqual("ON", events['fans/test'])
		self.assertEqual("ON", events['fans/test/power'])
		self.assertEqual("2", events['fans/test/speed'])
		self.assertEqual("2", events['fans/test/command'])
