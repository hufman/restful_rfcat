""" This module implements commanding over MQTT """

import paho.mqtt as mqtt
import paho.mqtt.client

import logging
logger = logging.getLogger(__name__)

class MQTTCommanding(object):
	def __init__(self, hostname="localhost", port=1883, prefix='command', username=None, password=None, tls=None):
		self.hostname = hostname
		self.port = port
		self.prefix = prefix

		self.client = mqtt.client.Client()
		self.client.on_message = self._on_message
		if username is not None:
			self.client.username_pw_set(username, password)
		if tls is not None:
			self.client.tls_set(**tls)

	def _on_connect(self, client, userdata, flags, rc):
		if rc != 0:
			raise mqtt.MQTTException(mqtt.client.connack_string(rc))

	def _find_device(self, path):
		from restful_rfcat.web import device_list
		parts = path.split('/', 1)
		class_devices = device_list.get(parts[0], {})
		device = class_devices.get(parts[1], None)
		return device

	def _set_device_state(self, path, state):
		device = self._find_device(path)
		if device is not None:
			try:
				logger.info("Setting state for %s to %s" % (path, state))
				device.set_state(state)
			except ValueError:
				logger.warning("Invalid state for %s: %s" % (path, state))
		else:
			logger.warning("Could not find device at %s" % (path, ))

	def _on_message(self, mqttc, obj, msg):
		topic = msg.topic
		data = msg.payload
		logger.info("Incoming MQTT broadcast: %s %s" % (msg.topic, msg.payload))
		if self.prefix is not None:
			prefix = "%s/" % (self.prefix.rstrip('/'),)
			topic = topic[len(prefix):]
		self._set_device_state(topic, data)

	def run(self):
		self.client.connect(self.hostname, self.port, 60)
		if self.prefix is not None:
			self.client.subscribe("%s/+/+" % (self.prefix.rstrip('/'),))
		else:
			self.client.subscribe("+/+")
		self.client.loop_forever()
		
	def stop(self):
		self.client.disconnect()

class MQTTHomeAssistantCommanding(MQTTCommanding):
	def __init__(self, hostname="localhost", port=1883, discovery_prefix="homeassistant", username=None, password=None, tls=None):
		super(MQTTHomeAssistantCommanding, self).__init__(hostname=hostname, port=port, username=username, password=password, tls=tls, prefix=discovery_prefix)

	def _on_message(self, mqttc, obj, msg):
		topic = msg.topic
		data = msg.payload
		logger.info("Incoming MQTT broadcast: %s %s" % (topic, data))
		topic_parts = topic.split('/')
		if len(topic_parts) > 2:
			object_id = topic_parts[-2]
			path = object_id.replace('_', '/')
			self._set_device_state(path, data)

	def run(self):
		self.client.connect(self.hostname, self.port, 60)
		self.client.subscribe("%s/+/+/set" % (self.prefix.rstrip('/'),))
		self.client.loop_forever()
