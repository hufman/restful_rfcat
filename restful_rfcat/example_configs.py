import json
import random

try:
	import collections
	dict = collections.OrderedDict
except:
	pass

from restful_rfcat import config

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
	if d.get_class() == 'fans':
		return 'Dimmer rfcat_%s_%s "%s" <fan_ceiling> [Switchable]' % (d.get_class(), d.name, d.label)
	if d.get_class() == 'lights':
		return 'Switch rfcat_%s_%s "%s" <light> [Lighting]' % (d.get_class(), d.name, d.label)
	return 'Switch rfcat_%s_%s "%s"' % (d.get_class(), d.name, d.label)

def _openhab_http_get(http_host, d):
	if 'command' in d.subdevices:
		d = d.subdevices['command']
	return '<[http://%s/%s:300:REGEX((.*))]' % (
			http_host,
			d._state_path()
		)

def _openhab_http_post(http_host, d):
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
	if 'command' in d.subdevices:
		d = d.subdevices['command']
	return '<[broker:%s:state:REGEX((.*))]' % (mqtt._set_topic(d._state_path),)

def _openhab_mqtt_post(mqtt_commanding, d):
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
	configs = {}
	configs['conf/items/rfcat.items'] = '\n'.join((
		'%s { mqtt="%s %s" }' % (
			_openhab_item(d),
			_openhab_mqtt_get(mqtt, d),
			_openhab_mqtt_post(mqtt_commanding, d)
		) for d in config.DEVICES
	))
	return configs

def get_hass(hass):
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
	if 'MQTTHomeAssistant' in persistence_modules:
		configs['HomeAssistant via MQTT'] = get_hass(persistence_modules['MQTTHomeAssistant'])
	return configs
