import signal
import sys
import threading
import traceback
import restful_rfcat.config
import restful_rfcat.drivers
import restful_rfcat.radio
import restful_rfcat.web

import logging
logging.basicConfig(level=logging.INFO)

import raven

threads = []

def check_preconditions():
	needs_radio = False
	for dev in restful_rfcat.config.DEVICES:
		needs_radio = needs_radio or hasattr(dev, 'radio')
	if needs_radio:
		import rflib
		if len(rflib.getRfCatDevices()) == 0:
			print("Could not find any RFCat devices!")
			return False
		else:
			restful_rfcat.radio.Radio._create_device()
			working = restful_rfcat.radio.Radio.ping()
			if not working:
				print("Could not communicate to RFCat device!")
			return working
	return True

def thread_logger(target):
	""" Automatically adds a raven client to a thread """
	client = raven.Client(restful_rfcat.config.SENTRY_DSN)
	threading.local().raven_client = client
	running = True
	while running:
		try:
			target()
			running = False
		except:
			client.captureException()
			traceback.print_exc()

def shutdown(*args):
	# try to gracefully shut down all the background threads
	for thread_info in threads:
		if hasattr(thread_info['runnable'], 'stop'):
			thread_info['runnable'].stop()
	for thread_info in threads:
		thread_info['thread'].join(1)
	sys.exit()

if __name__ == '__main__':
	if check_preconditions():
		signal.signal(signal.SIGINT, shutdown)
		for runnable_object in restful_rfcat.config.THREADS:
			runner = runnable_object.run
			thread = threading.Thread(target=thread_logger, args=(runner,))
			thread.daemon = True
			thread.start()
			threads.append({
				'thread': thread,
				'runnable': runnable_object
			})

		restful_rfcat.web.run_webserver()
