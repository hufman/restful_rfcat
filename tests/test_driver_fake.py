from restful_rfcat import config, drivers, persistence
import shutil
import tempfile
import unittest

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
		self.assertEqual(set(["OFF", "LOW", "MED", "HI"]), set(fan.get_available_states()))
