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
default_instance = HideyHole('/tmp')

def set(key, value):
	return default_instance.set(key, value)

def get(key):
	return default_instance.get(key)
