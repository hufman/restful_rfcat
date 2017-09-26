import json
import logging
import mock
import os.path

try:
	import collections
	dict = collections.OrderedDict
except:
	pass

logger = logging.getLogger(__name__)

class HideyHole(object):
	""" A simple object that stores state in individual files in a directory """
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
	""" Publishes state changes over MQTT
	This can be used to update software instantly
	For example, OpenHab can receive state updates with the MQTT binding
	"""
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
		"""
		>>> print(MQTT(_publish=mock.Mock())._set_topic('fans/fake'))
		fans/fake
		>>> print(MQTT(prefix="test", _publish=mock.Mock())._set_topic('fans/fake'))
		test/fans/fake
		"""
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
	HomeAssistant device configs are posted to homeassistant/{fans_fake}/config
	This config describes how to control the devices
	For full effect, use the mqtt.MQTTHomeAssistantCommanding background thread to
	actually respond to HomeAssistant commands
	"""
	def __init__(self, hostname="localhost", port=1883, username=None, password=None, tls=None, retain=True, discovery_prefix="homeassistant", discovery_devices=[], _publish=None):
		super(MQTTHomeAssistant, self).__init__(hostname=hostname, port=port, retain=retain, username=username, password=password, tls=tls, _publish=_publish)
		self.discovery_prefix = discovery_prefix
		if len(discovery_devices) > 0:
			self.initial_announcement(discovery_prefix, discovery_devices)

	def _device_config(self, device):
		klass = device.get_class()
		key = device._state_path()
		topic = self._hass_topic(key)
		state_topic = '%s/state' % (topic,)
		command_topic = '%s/set' % (topic,)
		config = dict()
		config['name'] = device.label
		config['state_topic'] = state_topic
		config['command_topic'] = command_topic
		if klass == 'lights':
			states = device.get_available_states()
			config['payload_off'] = states[0]
			config['payload_on'] = states[1]
		if klass == 'fans':
			states = device.get_available_states()
			speed_states = device.subdevices['speed'].get_available_states()
			topic = self._hass_topic(device.subdevices['speed']._state_path())
			state_topic = '%s/state' % (topic,)
			command_topic = '%s/set' % (topic,)
			config['speed_state_topic'] = state_topic
			config['speed_command_topic'] = command_topic
			config['payload_off'] = states[0]	# main device
			config['payload_low_speed'] = speed_states[0]	# speed device
			config['payload_medium_speed'] = speed_states[1]	# speed device
			config['payload_high_speed'] = speed_states[2]	# speed device
			config['speeds'] = ['low', 'medium', 'high']
		return config

	def initial_announcement(self, discovery_prefix="homeassistant", discovery_devices=[]):
		announcements = []
		for device in discovery_devices:
			key = device._state_path()
			topic = self._hass_topic(key)
			config_topic = '%s/config' % (topic,)
			config = self._device_config(device)
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

class MQTTStateful(object):
	""" A MQTT client that stays connected and retains state
	Useful for loading state back out of a retained MQTT topic
	"""
	def __init__(self, hostname="localhost", port=1883, prefix=None, retain=True, username=None, password=None, tls=None, _client=None):
		self.hostname = hostname
		self.port = port
		self.prefix = prefix
		self.retain = retain

		if _client is None:
			import paho.mqtt as mqtt
			self.client = mqtt.client.Client()
			self.client.on_message = self._on_message
		else:
			self.client = _client
		if username is not None:
			self.client.username_pw_set(username, password)
		if tls is not None:
			self.client.tls_set(**tls)

		self.states = {}

		self.run()

	# helper functions
	def _set_topic(self, key):
		"""
		>>> print(MQTTStateful(_client=mock.Mock())._set_topic('fans/fake'))
		fans/fake
		>>> print(MQTTStateful(prefix="test", _client=mock.Mock())._set_topic('fans/fake'))
		test/fans/fake
		"""
		topic = key
		if self.prefix is not None:
			topic = self.prefix + '/' + key
		return topic

	def _subscription_topics(self):
		"""
		Returns a list of topics for this stateful mqtt client
		>>> MQTTStateful(_client=mock.Mock())._subscription_topics()
		['+/+', '+/+/+']
		>>> MQTTStateful(prefix="test", _client=mock.Mock())._subscription_topics()
		['test/+/+', 'test/+/+/+']
		"""
		if self.prefix is not None:
			return [
				"%s/+/+" % (self.prefix.rstrip('/'),),
				"%s/+/+/+" % (self.prefix.rstrip('/'),),
			]
		else:
			return ["+/+", "+/+/+"]

	def _publish_multiple(self, msgs):
		if len(msgs) > 0:
			for msg in msgs:
				if isinstance(msg, dict):
					msg.setdefault('retain', self.retain)
					self.client.publish(**msg)
				else:
					self.client.publish(*msg)

	def _publish_single(self, topic, payload):
		self.client.publish(topic, payload, retain=self.retain)

	def _on_connect(self, client, userdata, flags, rc):
		if rc != 0:
			raise mqtt.MQTTException(mqtt.client.connack_string(rc))

	def _on_message(self, mqttc, obj, msg):
		topic = msg.topic
		data = msg.payload
		logger.info("Incoming MQTT broadcast: %s %s" % (msg.topic, msg.payload))
		self.states[topic] = data

	# connect to the broker
	def run(self):
		self.client.connect(self.hostname, self.port, 60)
		for topic in self._subscription_topics():
			self.client.subscribe(topic)
		self.client.loop_start()  # start a thread
		
	def stop(self):
		self.client.disconnect()

	# act like a persistence object
	def get(self, key, default=None):
		# use _set_topic to figure out where we would've saved before
		return self.states.get(self._set_topic(key), default)

	def set(self, key, value):
		topic = self._set_topic(key)
		self._publish_single(topic, value)

class MQTTStatefulHomeAssistant(MQTTStateful, MQTTHomeAssistant):
	""" A variant of MQTT publishing that supports HomeAssistant's discovery protocol
	Combined with using MQTTStateful to reload retained state on start
	HomeAssistant device configs are posted to homeassistant/{fans_fake}/config
	This config describes how to control the devices
	For full effect, use the mqtt.MQTTHomeAssistantCommanding background thread to
	actually respond to HomeAssistant commands
	"""
	def __init__(self, hostname="localhost", port=1883, username=None, password=None, tls=None, retain=True, discovery_prefix="homeassistant", discovery_devices=[], _client=None):
		self.discovery_devices = discovery_devices
		self.discovery_prefix = discovery_prefix
		super(MQTTStatefulHomeAssistant, self).__init__(hostname=hostname, port=port, retain=retain, username=username, password=password, tls=tls, prefix=discovery_prefix, _client=_client)

	def _on_connect(self, client, userdata, flags, rc):
		super(MQTTStatefulHomeAssistant, self)._on_connect(client, userdata, flags, rc)
		if len(self.discovery_devices) > 0:
			self.initial_announcement(self.prefix, self.discovery_devices)

	def _set_topic(self, key):
		# Use HASS's topic for setting things
		return self._hass_topic(key) + '/state'

	def _subscription_topics(self):
		"""
		Returns a list of topics for this stateful mqtt client
		>>> MQTTStatefulHomeAssistant(_client=mock.Mock())._subscription_topics()
		['homeassistant/+/+/state']
		>>> MQTTStatefulHomeAssistant(discovery_prefix="test", _client=mock.Mock())._subscription_topics()
		['test/+/+/state']
		"""
		return ["%s/+/+/state" % (self.prefix.rstrip('/'),)]

class Redis(object):
	""" Stores/loads state from a Redis server
	The db flag can be set to None to not actually store or load data in Redis
	The publish flag will additionally send data through Redis PUBSUB
	"""
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
	# module level accessor method
	# deferred import to sidestep circular import
	from restful_rfcat.config import PERSISTENCE
	for driver in PERSISTENCE:
		driver.set(key, value)

def get(key):
	# module level accessor method
	# deferred import to sidestep circular import
	from restful_rfcat.config import PERSISTENCE
	for driver in PERSISTENCE:
		found_value = driver.get(key)
		if found_value is not None:
			return found_value
	return None
