import json
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
	def __init__(self, hostname="localhost", port=1883, prefix=None, retain=True, username=None, password=None, tls=None, _publish=None):
		# save settings for later publishing
		self.hostname = hostname
		self.port = port
		self.prefix = prefix
		if self.prefix is not None:
			self.prefix = self.prefix.rstrip('/')
		self.retain = retain
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

	def _publish_multiple(self, msgs):
		if len(msgs) > 0:
			self._publish.multiple(msgs,
				hostname=self.hostname, port=self.port,
				auth=self.auth, tls=self.tls
			)

	def _publish_single(self, topic, payload):
		self._publish.single(topic, payload=payload, retain=self.retain,
			hostname=self.hostname, port=self.port,
			auth=self.auth, tls=self.tls
		)

	def _test_connect(self):
		self._publish_single('restful_rfcat', payload=None)

	def get(self, key, default=None):
		return default

	def _set_topic(self, key):
		topic = key
		if self.prefix is not None:
			topic = self.prefix + '/' + key
		return topic

	def set(self, key, value):
		try:
			topic = self._set_topic(key)
			self._publish_single(topic, payload=value)
		except Exception as e:
			logger.warning("Failure to persist to MQTT: %s" % (e.message,))

class MQTTHomeAssistant(MQTT):
	""" A variant of MQTT publishing that supports HomeAssistant's discovery protocol
	"""
	def __init__(self, hostname="localhost", port=1883, username=None, password=None, tls=None, retain=True, discovery_prefix="homeassistant", discovery_devices=[], _publish=None):
		super(MQTTHomeAssistant, self).__init__(hostname=hostname, port=port, username=username, password=password, tls=tls, _publish=_publish)
		self.discovery_prefix = discovery_prefix
		if len(discovery_devices) > 0:
			self.initial_announcement(discovery_prefix, discovery_devices)

	def initial_announcement(self, discovery_prefix="homeassistant", discovery_devices=[]):
		announcements = []
		for device in discovery_devices:
			klass = device.get_class()
			name = device.name
			key = '%s/%s' % (klass, name)
			topic = self._hass_topic(key)
			config_topic = '%s/config' % (topic,)
			state_topic = '%s/state' % (topic,)
			command_topic = '%s/set' % (topic,)
			config = {
				'name': device.label,
				'state_topic': state_topic,
				'command_topic': command_topic,
			}
			announcement = {
				'topic': config_topic,
				'payload': json.dumps(config),
				'retain': self.retain,
			}
			announcements.append(announcement)
		self._publish_multiple(announcements)

	@staticmethod
	def _device_component(klass):
		""" Transform a device class into a HomeAssistant component

		>>> MQTTHomeAssistant._device_component('lights')
		'light'
		>>> MQTTHomeAssistant._device_component('fans')
		'fan'
		>>> MQTTHomeAssistant._device_component('switch')
		'switch'
		"""
		component = klass[:-1] if klass.endswith('s') else klass
		return component

	def _hass_topic(self, key):
		""" Transform a device persistence path to an mqtt topic
		Include the device class into the object_id, which needs to be unique

		>>> import mock
		>>> MQTTHomeAssistant(_publish=mock.Mock())._hass_topic('lights/fake')
		'homeassistant/light/lights_fake'
		>>> MQTTHomeAssistant(_publish=mock.Mock())._hass_topic('lights/fake/color')
		'homeassistant/light/lights_fake_color'
		>>> MQTTHomeAssistant(_publish=mock.Mock())._hass_topic('fans/fake')
		'homeassistant/fan/fans_fake'
		"""
		klass = key.split('/')[0]
		component = self._device_component(klass)
		object_id = key.replace('/', '_')
		return '%s/%s/%s' % (self.discovery_prefix, component, object_id)

	def _set_topic(self, key):
		return self._hass_topic(key) + '/state'

class Redis(object):
	def __init__(self, hostname="localhost", port=6379, password=None, prefix=None, db=0, publish=True, client=None):
		self.prefix = prefix
		if self.prefix is not None:
			self.prefix = self.prefix.rstrip('/')
		self.db = db
		self.publish = publish
		if client is None:
			import redis
			self.client = redis.StrictRedis(host=hostname, port=port,
				password=password, db=db,
				socket_keepalive=60)
		else:
			# custom-connected or mock object
			self.client = client

	def _path(self, key):
		if self.prefix is not None:
			return self.prefix + '/' + key
		return key

	def get(self, key, default=None):
		if self.db is not None:
			found = None
			try:
				found = self.client.get(self._path(key))
			except Exception as e:
				logger.warning("Failure to load from Redis: %s" % (e.message,))
			if found is not None:
				return found
		return default

	def set(self, key, value):
		if self.db is not None:
			try:
				self.client.set(self._path(key), value)
			except Exception as e:
				logger.warning("Failure to persist to Redis: %s" % (e.message,))
		if self.publish:
			try:
				self.client.publish(self._path(key), value)
			except Exception as e:
				logger.warning("Failure to publish to Redis: %s" % (e.message,))

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
