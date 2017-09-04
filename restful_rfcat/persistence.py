import os.path

class HideyHole(object):
	def __init__(self, basepath):
		self.basepath = basepath

	def _key_path(self, key):
		safe_name = key.replace('/', u'\uff0f')
		return os.path.join(self.basepath, safe_name)

	def set(self, key, value):
		try:
			with open(self._key_path(key), 'w') as handle:
				handle.write(value)
		except:
			pass

	def get(self, key, default=None):
		try:
			with open(self._key_path(key), 'r') as handle:
				return handle.read()
		except:
			return default

def set(key, value):
	# deferred import to sidestep circular import
	from restful_rfcat.config import PERSISTENCE
	for driver in PERSISTENCE:
		driver.set(key, value)

def get(key):
	# deferred import to sidestep circular import
	from restful_rfcat.config import PERSISTENCE
	for driver in PERSISTENCE:
		found_value = driver.get(key)
		if found_value is not None:
			return found_value
	return None
