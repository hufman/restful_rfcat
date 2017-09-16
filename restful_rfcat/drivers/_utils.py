import inspect
import re
from restful_rfcat import persistence, pubsub

# Useful utilities or classes for drivers
class DeviceDriver(object):
	# a list of subdevice classes to expose
	SUBDEVICES = []

	def __init__(self, name, label):
		""" Save a name and display label """
		self.name = name
		self.label = label

	def get_name(self):
		return self.name

	def get_class(self):	# pragma: no cover
		""" Get the namespace in the api to place this device """
		raise NotImplementedError('%s.%s' % (self.__class__.__name__, inspect.currentframe().f_code.co_name))
		return "lights"

	def get_acceptable_states(self):	# pragma: no cover
		""" Get all states accepted by the device, including synonyms
		    Used mainly for api documentation
		"""
		return self.get_available_states()

	def get_available_states(self):	# pragma: no cover
		""" Get the main states accepted by the device, without synonyms """
		raise NotImplementedError('%s.%s' % (self.__class__.__name__, inspect.currentframe().f_code.co_name))
		return ["OFF", "LO", "MID", "HI"]

	def _state_path(self):
		""" Where to save the device in persistence layers """
		return '%s/%s' % (self.get_class(), self.name)

	def _get(self):
		""" Loads the current state from persistence """
		return persistence.get(self._state_path())
	def _set(self, state):
		""" Saves the given state to persistence """
		persistence.set(self._state_path(), state)
		pubsub.publish({'device':self, 'state':state})

	def get_state(self):
		return self._get()
	def set_state(self, state):	# pragma: no cover
		raise NotImplementedError('%s.%s' % (self.__class__.__name__, inspect.currentframe().f_code.co_name))

	@property
	def subdevices(self):
		return dict(((dev.get_name(), dev(self)) for dev in self.SUBDEVICES))

class SubDeviceDriver(DeviceDriver):
	""" Common functionality to make it easy to implement subdevices

	Each subdevice should provide a list of STATE_COMMANDS, which
	maps a POSTed state to the actual command to run
	This allows for multiple state aliases
	"""
	STATE_COMMANDS = {}

	@classmethod
	def _state_to_command(klass, state):
		"""
		>>> SubDeviceDriver(None)._state_to_command('OFF')
		Traceback (most recent call last):
		    ...
		ValueError: OFF
		"""
		try:
			return klass.STATE_COMMANDS[state.upper()]
		except KeyError:
			raise ValueError(state)

	def __init__(self, parent):
		self.parent = parent

	@classmethod
	def get_name(klass):	# pragma: no cover
		""" Get the subdevice name in the api to place this device """
		raise NotImplementedError('%s.%s' % (self.__class__.__name__, inspect.currentframe().f_code.co_name))
		return "color"

	def _state_path(self):
		return '%s/%s' % (self.parent._state_path(), self.get_name())

	def get_acceptable_states(self):
		"""
		>>> SubDeviceDriver(None).get_acceptable_states()
		[]
		"""
		return sorted(self.STATE_COMMANDS.keys())

	def get_available_states(self):
		"""
		>>> SubDeviceDriver(None).get_available_states()
		[]
		"""
		return sorted(list(set(self.STATE_COMMANDS.values())))

class PWMThreeSymbolMixin(object):
	@staticmethod
	def _encode_pwm_symbols(bit_string):
		"""
		>>> PWMThreeSymbolMixin._encode_pwm_symbols("00110011")
		'001001011011001001011011'
		"""
		pwm_str_key = []
		for k in bit_string:
			x = ""
			if(k == "0"):
				x = "001" #  A zero is encoded as a longer low pulse (low-low-high)
			if(k == "1"):
				x = "011" # and a one is encoded as a shorter low pulse (low-high-high)
			pwm_str_key.append(x)
		return ''.join(pwm_str_key)

	@staticmethod
	def _decode_pwm_symbols(symbols):
		""" Turns a string of radio symbols into a PCM-decoded packet
		>>> PWMThreeSymbolMixin._decode_pwm_symbols("001011001011")
		'0101'
		>>> PWMThreeSymbolMixin._decode_pwm_symbols( \
			PWMThreeSymbolMixin._encode_pwm_symbols("001001110101") \
		)
		'001001110101'

		# sometimes the 0 bits get held a little longer
		>>> PWMThreeSymbolMixin._decode_pwm_symbols("0010011001011")
		'0101'

		# invalid sequences return None
		>>> PWMThreeSymbolMixin._decode_pwm_symbols("1111")
		>>> PWMThreeSymbolMixin._decode_pwm_symbols("111101111")

		"""
		if len(symbols) < 6:
			return None
		bits = []
		found_bits = re.findall('0+(1+)', symbols)
		for one_bits in found_bits:
			ones = len(one_bits)
			if ones == 1:
				bits.append('0')
			elif ones == 2:
				bits.append('1')
			else:
				# invalid sequence
				return None
		return ''.join(bits)

class ThreeSpeedFanMixin(object):
	CLASS = 'fans'

	STATE_COMMANDS = {
		'0': '0',
		'1': '1',
		'2': '2',
		'3': '3',
		'O': '0',
		'OFF': '0',
		'L': '1',
		'LO': '1',
		'LOW': '1',
		'M': '2',
		'MED': '2',
		'MID': '2',
		'H': '3',
		'HI': '3',
		'HIGH': '3',
	}

	def get_class(self):
		"""
		>>> ThreeSpeedFanMixin().get_class()
		'fans'
		"""
		return self.CLASS

	@classmethod
	def _state_to_command(klass, state):
		"""
		>>> ThreeSpeedFanMixin()._state_to_command('MED')
		'fan2'
		>>> ThreeSpeedFanMixin()._state_to_command('BLUE')
		Traceback (most recent call last):
		    ...
		ValueError: BLUE
		"""
		try:
			return 'fan' + klass.STATE_COMMANDS[state.upper()]
		except KeyError:
			raise ValueError(state)

	def get_acceptable_states(self):
		"""
		>>> ThreeSpeedFanMixin().get_acceptable_states()
		['0', '1', '2', '3', 'H', 'HI', 'HIGH', 'L', 'LO', 'LOW', 'M', 'MED', 'MID', 'O', 'OFF']
		"""
		return sorted(self.STATE_COMMANDS.keys())

	def get_available_states(self):
		"""
		>>> ThreeSpeedFanMixin().get_available_states()
		['0', '1', '2', '3']
		"""
		return sorted(list(set(self.STATE_COMMANDS.values())))

class LightMixin(object):
	CLASS = 'lights'

	STATE_COMMANDS = {
		'ON': 'ON',
		'OFF': 'OFF',
		'1': 'ON',
		'0': 'OFF',
		'TRUE': 'ON',
		'FALSE': 'OFF',
	}

	@classmethod
	def _state_to_command(klass, state):
		"""
		>>> LightMixin()._state_to_command('OFF')
		'OFF'
		>>> LightMixin()._state_to_command('BLUE')
		Traceback (most recent call last):
		    ...
		ValueError: BLUE
		"""
		try:
			return klass.STATE_COMMANDS[state.upper()]
		except KeyError:
			raise ValueError(state)

	def get_class(self):
		"""
		>>> LightMixin().get_class()
		'lights'
		"""
		return self.CLASS

	def get_acceptable_states(self):
		"""
		>>> LightMixin().get_acceptable_states()
		['0', '1', 'FALSE', 'OFF', 'ON', 'TRUE']
		"""
		return sorted(self.STATE_COMMANDS.keys())

	def get_available_states(self):
		"""
		>>> LightMixin().get_available_states()
		['OFF', 'ON']
		"""
		return sorted(list(set(self.STATE_COMMANDS.values())))
