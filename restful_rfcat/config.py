import restful_rfcat.persistence

DEVICES = [
]

EAVESDROPPER = None

PERSISTENCE = [
	restful_rfcat.persistence.HideyHole('/tmp/')
]

try:
	from restful_rfcat.localconfig import *
except Exception as e:
	print("Error while loading localconfig: %s\nUsing default config" % (e,))
