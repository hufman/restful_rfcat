import bottle
from bottle_swagger import SwaggerPlugin
from markup import markup
import os
import yaml
from restful_rfcat.config import DEVICES

device_list = {}

# define all the devices
def rest_get_state(device):
	""" Inside an HTTP GET, return a device's state """
	def _wrapped(*args, **kwargs):
		bottle.response.content_type = 'text/plain'
		return device.get_state()
	_wrapped.__name__ = 'get_%s' % (device.name,)
	return _wrapped
def rest_set_state(device):
	""" Inside an HTTP PUT, set a device's state """
	def _wrapped(*args, **kwargs):
		state = bottle.request.body.read()
		bottle.response.content_type = 'text/plain'
		if state not in device.get_available_states():
			return bottle.HTTPError(400, "Invalid state")
		return device.set_state(state)
	_wrapped.__name__ = 'put_%s' % (device.name,)
	return _wrapped
def rest_list_states(device):
	""" Inside an HTTP PUT, set a device's state """
	def _wrapped(*args, **kwargs):
		bottle.response.content_type = 'text/plain'
		return '\n'.join(device.get_available_states())
	_wrapped.__name__ = 'put_%s' % (device.name,)
	return _wrapped
def device_path(device):
	klass = device.get_class()
	name = device.name
	path = '/%s/%s' % (klass+'s', name)
	return path
for device in DEVICES:
	path = device_path(device)
	bottle.get(path)(rest_get_state(device))
	bottle.post(path)(rest_set_state(device))  # openhab can only post
	bottle.put(path)(rest_set_state(device))
	bottle.route(path, method='OPTIONS')(rest_list_states(device))
	# check for subdevices
	if hasattr(device, 'subdevices'):
		for name,subdev in device.subdevices().items():
			subpath = '%s/%s' % (path, name)
			bottle.get(subpath)(rest_get_state(subdev))
			bottle.post(subpath)(rest_set_state(subdev))  # openhab can only post
			bottle.put(subpath)(rest_set_state(subdev))
			bottle.route(subpath, method='OPTIONS')(rest_list_states(subdev))
	# save to index
	klass = device.get_class()
	name = device.name
	klass_devices = device_list.get(klass, {})
	klass_devices[name] = device
	device_list[klass] = klass_devices

@bottle.get('/')
def index():
	page = markup.page()
	page.init()
	for klass in sorted(device_list.keys()):
		klass_devices = device_list[klass]
		page.h2(klass)
		for name in sorted(klass_devices.keys()):
			device = klass_devices[name]
			path = device_path(device)
			state = device.get_state()
			if state is None:
				state = "Unknown"
			page.ul("%s - %s" % (path, state))
	return str(page)

# add swagger interface
def load_swagger():
	path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
	swagger_path = os.path.join(path, 'api.swagger')
	with open(swagger_path, 'r') as swagger_file:
		return yaml.load(swagger_file)

def run_webserver():
	bottle.install(SwaggerPlugin(load_swagger(), ignore_undefined_routes=True))
	bottle.run(server='paste', host='0.0.0.0', port=3350)

if __name__ == '__main__':
	run_webserver()
