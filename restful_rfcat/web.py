import bottle
from markup import markup
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
		return device.set_state(state)
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
	bottle.put(path)(rest_set_state(device))
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

def run_webserver():
	bottle.run(server='paste', host='0.0.0.0', port=3350)

if __name__ == '__main__':
	run_webserver()
