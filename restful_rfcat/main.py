import signal
import sys
import threading
import restful_rfcat.drivers
import restful_rfcat.web

import logging
logging.basicConfig(level=logging.INFO)

def sniff():
	eavesdropper = restful_rfcat.drivers.HunterCeilingEavesdropper()
	while not radio_loop_stop.is_set():
		eavesdropper.eavesdrop()
	eavesdropper.radio.reset_device()

def shutdown(*args):
        radio_loop_stop.set()
        sniffer.join(2)
        sys.exit()
signal.signal(signal.SIGINT, shutdown)

radio_loop_stop = threading.Event()
sniffer = threading.Thread(target=sniff)
sniffer.daemon = True
sniffer.start()

restful_rfcat.web.run_webserver()
