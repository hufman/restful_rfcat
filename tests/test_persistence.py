from restful_rfcat import config, persistence
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
