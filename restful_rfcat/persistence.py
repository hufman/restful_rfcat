import logging
import os.path

logger = logging.getLogger(__name__)

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
		except Exception as e:
			logger.warning("Failure to persist to HideyHole: %s" % (e.message,))

	def get(self, key, default=None):
		try:
			with open(self._key_path(key), 'r') as handle:
				return handle.read()
		except:
			return default

class MQTT(object):
	def __init__(self, hostname="localhost", port=1883, username=None, password=None, tls=None, _publish=None):
		# save settings for later publishing
		self.hostname = hostname
		self.port = port
		self.auth = None
		if username is not None:
			self.auth = {'username': username, 'password': password}
		self.tls = tls
		# test mqtt connectivity
		if _publish is None:
			import paho.mqtt.publish as publish
			self._publish = publish
		else:
			# mock object
			self._publish = _publish
		self._test_connect()

	def _test_connect(self):
		self._publish.single('restful_rfcat', payload=None,
			hostname=self.hostname, port=self.port,
			auth=self.auth, tls=self.tls
		)

	def get(self, key, default=None):
		return default

	def set(self, key, value):
		try:
			self._publish.single(key, payload=value,
				hostname=self.hostname, port=self.port,
				auth=self.auth, tls=self.tls
			)
		except Exception as e:
			logger.warning("Failure to persist to MQTT: %s" % (e.message,))

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
