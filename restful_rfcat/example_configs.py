import json
import random

try:
	import collections
	dict = collections.OrderedDict
except:
	pass

from restful_rfcat import config

# used for testing
from restful_rfcat.drivers import FakeFan, FakeLight
import mock

def _inclusive_devices():
	for d in config.DEVICES:
		yield d
		for s in d.subdevices.values():
			yield s

def get_curl(http_host):
	config = dict()
	config['CLI Fetch'] = '\n'.join((
			'curl http://%s/%s' % (http_host, d._state_path())
			for d in _inclusive_devices()
		))
	config['CLI Update'] = '\n'.join((
			'curl -X POST -d %s http://%s/%s' % (
				random.choice(d.get_available_states()),
				http_host,
				d._state_path()
			)
			for d in _inclusive_devices()
		))
	config['CLI Stream'] = "curl http://%s/stream" % (http_host,)
	return config

def _openhab_item(d):
	"""
	>>> print(_openhab_item(FakeFan(name="fake", label="Fake")))
	Dimmer rfcat_fans_fake "Fake" <fan_ceiling> [Switchable]
	>>> print(_openhab_item(FakeLight(name="fake", label="Fake")))
	Switch rfcat_lights_fake "Fake" <light> [Lighting]

	>>> weird = FakeLight(name="fake", label="Fake")
	>>> weird.CLASS = "custom"
	>>> print(_openhab_item(weird))
	Switch rfcat_custom_fake "Fake"
	"""
	if d.get_class() == 'fans':
		return 'Dimmer rfcat_%s_%s "%s" <fan_ceiling> [Switchable]' % (d.get_class(), d.name, d.label)
	if d.get_class() == 'lights':
		return 'Switch rfcat_%s_%s "%s" <light> [Lighting]' % (d.get_class(), d.name, d.label)
	return 'Switch rfcat_%s_%s "%s"' % (d.get_class(), d.name, d.label)

def _openhab_http_get(http_host, d):
	"""
	>>> print(_openhab_http_get("localhost:3350", FakeFan(name="fake", label="Fake")))
	<[http://localhost:3350/fans/fake/command:300:REGEX((.*))]
	>>> print(_openhab_http_get("localhost:3350", FakeLight(name="fake", label="Fake")))
	<[http://localhost:3350/lights/fake:300:REGEX((.*))]
	"""
	if 'command' in d.subdevices:
		d = d.subdevices['command']
	return '<[http://%s/%s:300:REGEX((.*))]' % (
			http_host,
			d._state_path()
		)

def _openhab_http_post(http_host, d):
	"""
	>>> print(_openhab_http_post("localhost:3350", FakeFan(name="fake", label="Fake")))
	>[0:POST:http://localhost:3350/fans/fake/command:0] >[1:POST:http://localhost:3350/fans/fake/command:1] >[2:POST:http://localhost:3350/fans/fake/command:2] >[3:POST:http://localhost:3350/fans/fake/command:3]
	>>> print(_openhab_http_post("localhost:3350", FakeLight(name="fake", label="Fake")))
	>[OFF:POST:http://localhost:3350/lights/fake:OFF] >[ON:POST:http://localhost:3350/lights/fake:ON]
	"""
	if 'command' in d.subdevices:
		d = d.subdevices['command']
	return ' '.join((
		'>[%s:POST:http://%s/%s:%s]' % (
			s,
			http_host,
			d._state_path(),
			s
		) for s in d.get_available_states()
	))

def get_openhab_poll(http_host):
	"""
	>>> config.DEVICES = [FakeLight(name="fake", label="Fake")]
	>>> print(get_openhab_poll('localhost:3350')['conf/items/rfcat.items'])
	Switch rfcat_lights_fake "Fake" <light> [Lighting] { http="<[http://localhost:3350/lights/fake:300:REGEX((.*))] >[OFF:POST:http://localhost:3350/lights/fake:OFF] >[ON:POST:http://localhost:3350/lights/fake:ON]" }
	"""
	configs = {}
	configs['conf/items/rfcat.items'] = '\n'.join((
		'%s { http="%s %s" }' % (
			_openhab_item(d),
			_openhab_http_get(http_host, d),
			_openhab_http_post(http_host, d)
		) for d in config.DEVICES
	))
	return configs

def _openhab_mqtt_get(mqtt, d):
	"""
	>>> mqtt = mock.Mock()
	>>> mqtt._set_topic = lambda x: x
	>>> print(_openhab_mqtt_get(mqtt, FakeFan(name="fake", label="Fake")))
	<[broker:fans/fake/command:state:REGEX((.*))]
	>>> print(_openhab_mqtt_get(mqtt, FakeLight(name="fake", label="Fake")))
	<[broker:lights/fake:state:REGEX((.*))]
	"""
	if 'command' in d.subdevices:
		d = d.subdevices['command']
	return '<[broker:%s:state:REGEX((.*))]' % (mqtt._set_topic(d._state_path()),)

def _openhab_mqtt_post(mqtt_commanding, d):
	"""
	>>> mqtt = mock.Mock()
	>>> mqtt.prefix = "command"
	>>> print(_openhab_mqtt_post(mqtt, FakeFan(name="fake", label="Fake")))
	>[broker:command/fans/fake/command:command:0:0] >[broker:command/fans/fake/command:command:1:1] >[broker:command/fans/fake/command:command:2:2] >[broker:command/fans/fake/command:command:3:3]
	>>> print(_openhab_mqtt_post(mqtt, FakeLight(name="fake", label="Fake")))
	>[broker:command/lights/fake:command:OFF:OFF] >[broker:command/lights/fake:command:ON:ON]
	"""
	def prefixed_path(path):
		if mqtt_commanding.prefix:
			return '%s/%s' % (mqtt_commanding.prefix.rstrip('/'), path)
		else:
			return path
	if 'command' in d.subdevices:
		d = d.subdevices['command']
	return ' '.join((
		'>[broker:%s:command:%s:%s]' % (
			prefixed_path(d._state_path()),
			s,
			s
		) for s in d.get_available_states()
	))

def get_openhab_mqtt(http_host, mqtt):
	"""
	>>> mqtt = mock.Mock()
	>>> mqtt._set_topic = lambda x: x
	>>> config.DEVICES = [FakeLight(name="fake", label="Fake")]
	>>> print(get_openhab_mqtt('localhost:3350', mqtt)['conf/items/rfcat.items'])
	Switch rfcat_lights_fake "Fake" <light> [Lighting] { mqtt="<[broker:lights/fake:state:REGEX((.*))]" http=">[OFF:POST:http://localhost:3350/lights/fake:OFF] >[ON:POST:http://localhost:3350/lights/fake:ON]" }
	"""
	configs = {}
	configs['conf/items/rfcat.items'] = '\n'.join((
		'%s { mqtt="%s" http="%s" }' % (
			_openhab_item(d),
			_openhab_mqtt_get(mqtt, d),
			_openhab_http_post(http_host, d)
		) for d in config.DEVICES
	))
	return configs

def get_openhab_mqtt_commanding(mqtt, mqtt_commanding):
	"""
	>>> mqtt = mock.Mock()
	>>> mqtt._set_topic = lambda x: x
	>>> mqtt_commanding = mock.Mock()
	>>> mqtt_commanding.prefix = 'command'
	>>> config.DEVICES = [FakeLight(name="fake", label="Fake")]
	>>> print(get_openhab_mqtt_commanding(mqtt, mqtt_commanding)['conf/items/rfcat.items'])
	Switch rfcat_lights_fake "Fake" <light> [Lighting] { mqtt="<[broker:lights/fake:state:REGEX((.*))] >[broker:command/lights/fake:command:OFF:OFF] >[broker:command/lights/fake:command:ON:ON]" }
	"""
	configs = {}
	configs['conf/items/rfcat.items'] = '\n'.join((
		'%s { mqtt="%s %s" }' % (
			_openhab_item(d),
			_openhab_mqtt_get(mqtt, d),
			_openhab_mqtt_post(mqtt_commanding, d)
		) for d in config.DEVICES
	))
	return configs

def get_hass_http_switches(http_host):
	"""
	>>> config.DEVICES = [FakeLight(name="fake", label="Fake Light"), FakeFan(name="fake", label="Fake Fan")]
	>>> print(get_hass_http_switches("localhost:3350"))['.homeassistant/configuration.yml']
	switch:
	 - platform: rest
	   name: Fake Light
	   resource: http://localhost:3350/lights/fake
	 - platform: rest
	   name: Fake Fan
	   resource: http://localhost:3350/fans/fake
	"""
	lines = []
	lines.append('switch:')
	for d in config.DEVICES:
		lines.append(' - platform: rest')
		lines.append('   name: %s' % (d.label,))
		lines.append('   resource: http://%s/%s' % (http_host, d._state_path()))
	return {'.homeassistant/configuration.yml': '\n'.join(lines)}

def get_hass(hass):
	"""
	>>> config.DEVICES = [FakeLight(name="fake", label="Fake"), FakeFan(name="fake", label="Fake")]
	>>> from restful_rfcat.persistence import MQTTHomeAssistant
	>>> print(get_hass(MQTTHomeAssistant(_publish=mock.Mock())))['.homeassistant/configuration.yml']  # doctest: +SKIP
	fan:
	 - platform: mqtt
	   name: "Fake"
	   state_topic: "homeassistant/fan/fans_fake/state"
	   command_topic: "homeassistant/fan/fans_fake/set"
	   speed_state_topic: "homeassistant/fan/fans_fake_speed/state"
	   speed_command_topic: "homeassistant/fan/fans_fake_speed/set"
	   payload_off: "OFF"
	   payload_low_speed: "1"
	   payload_medium_speed: "2"
	   payload_high_speed: "3"
	   speeds: ["low", "medium", "high"]
	light:
	 - platform: mqtt
	   name: "Fake"
	   state_topic: "homeassistant/light/lights_fake/state"
	   command_topic: "homeassistant/light/lights_fake/set"
	   payload_off: "OFF"
	   payload_on: "ON"
	"""
	fans = [hass._device_config(d)
	        for d in config.DEVICES
 	        if d.get_class() == 'fans']
	lights = [hass._device_config(d)
	          for d in config.DEVICES
	          if d.get_class() == 'lights']
	lines = []
	lines.append('fan:')
	for d in fans:
		lines.append(' - platform: mqtt')
		for k,v in d.items():
			lines.append('   %s: %s' % (k,json.dumps(v)))
	lines.append('light:')
	for d in lights:
		lines.append(' - platform: mqtt')
		for k,v in d.items():
			lines.append('   %s: %s' % (k,json.dumps(v)))

	configs = {}
	configs['.homeassistant/configuration.yml'] = '\n'.join(lines)
	return configs

def get(http_host):
	persistence_modules = dict(((p.__class__.__name__,p) for p in config.PERSISTENCE))
	thread_modules = dict(((t.__class__.__name__,t) for t in config.THREADS))
	configs = dict()
	configs['curl'] = get_curl(http_host)
	configs['OpenHAB HTTP Polling'] = get_openhab_poll(http_host)
	if 'MQTT' in persistence_modules:
		if 'MQTTCommanding' in thread_modules:
			configs['OpenHAB via MQTT'] = get_openhab_mqtt_commanding(persistence_modules['MQTT'], thread_modules['MQTTCommanding'])
		else:
			configs['OpenHAB via MQTT'] = get_openhab_mqtt(http_host, persistence_modules['MQTT'])

	configs['HomeAssistant HTTP Polling'] = get_hass_http_switches(http_host)
	if 'MQTTHomeAssistant' in persistence_modules:
		configs['HomeAssistant via MQTT'] = get_hass(persistence_modules['MQTTHomeAssistant'])
	return configs
