import restful_rfcat.persistence

DEVICES = [
]

THREADS = [
	# any threads that should run in the background
]

PERSISTENCE = [
	restful_rfcat.persistence.HideyHole('/tmp/')
]

SENTRY_DSN = None

try:
	from restful_rfcat.localconfig import *
except Exception as e:
	print("Error while loading localconfig: %s\nUsing default config" % (e,))
