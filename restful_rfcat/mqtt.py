""" This module implements commanding over MQTT """

import paho.mqtt as mqtt
import paho.mqtt.client

import logging
logger = logging.getLogger(__name__)

class MQTTCommanding(object):
	def __init__(self, hostname="localhost", port=1883, prefix=None, username=None, password=None, tls=None):
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

	def _on_message(self, mqttc, obj, msg):
		from restful_rfcat.web import device_list
		topic = msg.topic
		data = msg.payload
		if self.prefix is not None:
			prefix = "%s/" % (self.prefix.rstrip('/'),)
			topic = topic[len(prefix):]
		parts = topic.split('/', 1)
		class_devices = device_list.get(parts[0], {})
		device = class_devices.get(parts[1], None)
		if device is not None:
			try:
				logger.info("Setting state for %s to %s" % (topic, data))
				device.set_state(data)
			except ValueError:
				logger.warning("Invalid state for %s: %s" % (topic, data))

	def run(self):
		self.client.connect(self.hostname, self.port, 60)
		if self.prefix is not None:
			self.client.subscribe("%s/#" % (self.prefix.rstrip('/'),))
		else:
			self.client.subscribe("#")
		self.client.loop_forever()
		
	def stop(self):
		self.client.disconnect()
