import restful_rfcat.persistence

DEVICES = [
]

EAVESDROPPER = None

PERSISTENCE = [
	restful_rfcat.persistence.HideyHole('/tmp/')
]

try:
    from restful_rfcat.localconfig import *
except:
    pass
