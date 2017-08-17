# Useful utilities or classes for drivers
class DeviceDriver(object):
	def __init__(self, name, label):
		""" Save a name and display label """
		self.name = name
		self.label = label

	def get_class(self):
		raise NotImplementedError
		return "light"

	def get_available_states(self):
		raise NotImplementedError
		return ["OFF", "1", "2", "3"]

	def _get(self, key):
		return hideyhole.get(key)
	def _set(self, key, value):
		hideyhole.set(key, value)

	def get_state(self):
		raise NotImplementedError
	def set_state(self, state):
		raise NotImplementedError

