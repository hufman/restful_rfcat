import re
from restful_rfcat import hideyhole

# Useful utilities or classes for drivers
class DeviceDriver(object):
	def __init__(self, name, label):
		""" Save a name and display label """
		self.name = name
		self.label = label

	def get_class(self):
		raise NotImplementedError
		return "light"

	def get_available_states(self):
		raise NotImplementedError
		return ["OFF", "1", "2", "3"]

	def _get(self, key):
		return hideyhole.get(key)
	def _set(self, key, value):
		hideyhole.set(key, value)

	def get_state(self):
		raise NotImplementedError
	def set_state(self, state):
		raise NotImplementedError

class FakeDevice(DeviceDriver):
	def get_class(self):
		return self.CLASS
	def get_state(self):
		return self._get("%s/%s" % (self.CLASS, self.name))
	def set_state(self, state):
		return self._set("%s/%s" % (self.CLASS, self.name), state)

class FakeLight(FakeDevice):
	CLASS = "light"
	def get_available_states(self):
		return ["OFF", "ON"]

class FakeFan(FakeDevice):
	CLASS = "fan"
	def get_available_states(self):
		return ["OFF", "LOW", "MED", "HI"]

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

