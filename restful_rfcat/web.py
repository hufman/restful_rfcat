import bottle
import os
import time
from markup import markup
from restful_rfcat.config import DEVICES, SENTRY_DSN
import restful_rfcat.pubsub
import Queue

# sentry integration
import raven
from raven.contrib.bottle import Sentry

device_list = {}

script_path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

# define all the devices
def rest_get_state(device):
	""" Inside an HTTP GET, return a device's state """
	def _wrapped(*args, **kwargs):
		bottle.response.content_type = 'text/plain'
		return device.get_state() + '\n'
	_wrapped.__name__ = 'get_%s' % (device.get_name(),)
	return _wrapped
def rest_set_state(device):
	""" Inside an HTTP PUT, set a device's state """
	def _wrapped(*args, **kwargs):
		state = bottle.request.body.read()
		bottle.response.content_type = 'text/plain'
		try:
			return device.set_state(state) + '\n'
		except ValueError:
			return bottle.HTTPError(400, "Invalid state: %s" % (state,))
	_wrapped.__name__ = 'put_%s' % (device.get_name(),)
	return _wrapped
def rest_list_states(device):
	""" Inside an HTTP OPTIONS, list a device's acceptable inputs """
	def _wrapped(*args, **kwargs):
		bottle.response.content_type = 'text/plain'
		return '\n'.join(device.get_acceptable_states()) + '\n'
	_wrapped.__name__ = 'options_%s' % (device.get_name(),)
	return _wrapped
for device in DEVICES:
	path = '/' + device._state_path()
	bottle.get(path)(rest_get_state(device))
	bottle.post(path)(rest_set_state(device))  # openhab can only post
	bottle.put(path)(rest_set_state(device))
	bottle.route(path, method='OPTIONS')(rest_list_states(device))
	# check for subdevices
	for name,subdev in device.subdevices.items():
		subpath = '/' + subdev._state_path()
		bottle.get(subpath)(rest_get_state(subdev))
		bottle.post(subpath)(rest_set_state(subdev))  # openhab can only post
		bottle.put(subpath)(rest_set_state(subdev))
		bottle.route(subpath, method='OPTIONS')(rest_list_states(subdev))
	# save to index
	klass = device.get_class()
	name = device.get_name()
	klass_devices = device_list.get(klass, {})
	klass_devices[name] = device
	device_list[klass] = klass_devices

@bottle.get('/')
def index():
	page = markup.page()
	page.init(script=['app.js'], css=['style.css'])
	for klass in sorted(device_list.keys()):
		klass_devices = device_list[klass]
		page.h2(klass)
		for name in sorted(klass_devices.keys()):
			device = klass_devices[name]
			path = device._state_path()
			state = device.get_state()
			if state is None:
				state = "Unknown"
			page.li.open()
			page.span("%s - " % (path,))
			page.span(state, id='%s-state'%(path,), class_='state')
			page.li.close()
			for name,subdev in device.subdevices.items():
				path = subdev._state_path()
				state = subdev.get_state()
				if state is None:
					state = "Unknown"
				page.li.open()
				page.span("%s - " % (path,))
				page.span(state, id='%s-state'%(path,), class_='state')
				page.li.close()
	return str(page)

@bottle.get('/app.js')
def appjs():
	return bottle.static_file('app.js', root=script_path)

@bottle.get('/style.css')
def stylecss():
	return bottle.static_file('style.css', root=script_path)

@bottle.get('/stream')
def stream():
	# example code from https://gist.github.com/werediver/4358735
	bottle.response.content_type = 'text/event-stream'
	bottle.response.cache_control = 'no-cache'

	yield 'retry: 10\n\n'

	# output the current state
	for klass in sorted(device_list.keys()):
		klass_devices = device_list[klass]
		for name in sorted(klass_devices.keys()):
			device = klass_devices[name]
			path = device._state_path()
			state = device.get_state()
			if state is None:
				state = "Unknown"
			yield 'data: %s=%s\n\n' % (path, state)

	with restful_rfcat.pubsub.subscribe() as events:
		end = time.time() + 3600
		while time.time() < end:
			try:
				data = events.get(block=True, timeout=30)
			except Queue.Empty:
				yield ':\n\n'
				continue
			device = data['device']
			path = device._state_path()
			yield 'data: %s=%s\n\n' % (path, data['state'])

def run_webserver():
	app = bottle.app()
	app.catchall = False
	app = Sentry(app, raven.Client(SENTRY_DSN))
	bottle.run(app, server='paste', host='0.0.0.0', port=3350)

if __name__ == '__main__':
	run_webserver()
