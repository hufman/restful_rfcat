# A device driver to interact with Feit Electric LED lights
from operator import itemgetter
import logging
import struct
import re
from restful_rfcat import radio
from restful_rfcat.drivers._utils import DeviceDriver

logger = logging.getLogger(__name__)

class FeitElectric(DeviceDriver):
	devices = {}
	commands = {
		'on': '11110100',
		'off': '11101100',
		'minus': '11011100',
		'plus': '10111100',
		'up': '11101010',
		'down': '11010101',
		'red': '11011010',
		'green': '10101110',
		'blue': '10110101',
		'white': '10111010'
	}
	radio = radio.OOKRadio(433900000, 4880)

	def __init__(self, address, **kwargs):
		""" address is the prefix before the command string
		"""
		# save the name and label
		super(FeitElectric, self).__init__(**kwargs)
		self.address = address
		self._remember_device()

	def _remember_device(self):
		# magical registration of devices for eavesdropping
		class_name = self.__class__.__name__
		device_type = class_name[len('FeitElectric'):].lower()
		device_name = '%s-%s' % (self.address, device_type)
		self.devices[device_name] = self

	@classmethod
	def _get_device(klass, device_type, address):
		device_name = '%s-%s' % (address, device_type.lower())
		return klass.devices.get(device_name)

	@staticmethod
	def _encode_pwm(bin_key):
		"""
		>>> FeitElectric._encode_pwm("00110011")
		'0000101000001010'
		"""
		pwm_str_key = []
		for k in bin_key:
			x = ""
			if(k == "0"):
				x = "00" #  A zero is encoded as a longer low pulse (low-low-high)
			if(k == "1"):
				x = "10" # and a one is encoded as a shorter low pulse (low-high-high)
			pwm_str_key.append(x)
		return ''.join(pwm_str_key)

	@staticmethod
	def _encode(bin_key):
		"""
		>>> FeitElectric._encode("01100110")
		'\\x00\\x00\\x00(('
		"""
		pwm_str_key = FeitElectric._encode_pwm(bin_key)
		pwm_str_key = "" + pwm_str_key #added leading 0 for clock
		#print "Binary (PWM) key:",pwm_str_key
		dec_pwm_key = int(pwm_str_key, 2);
		#print "Decimal (PWN) key:",dec_pwm_key
		key_packed = ''
		while dec_pwm_key > 0:
			key_packed = struct.pack(">Q", dec_pwm_key & (2**64-1)) + key_packed
			dec_pwm_key = dec_pwm_key >> 64
		# trim to the correct amount of white space
		key_packed = '\0\0\0' + key_packed.strip('\0')
		return key_packed

	@classmethod
	def _send(klass, bits):
		symbols = klass._encode(bits)
		klass.radio.send(symbols)

	def _send_command(self, command):
		logger.info("Sending command %s to %s" % (command, self.address))
		self._send(self._get_bin_key(command))

	def _get_bin_key(self, command):
		"""
		>>> FeitElectric(name='test', label='Test', address='0110110111110101011110101111')._get_bin_key('on')
		'011011011111010101111010111111110100'
		"""
		bin_key = '%s%s' % (self.address, self.commands[command])
		return bin_key

	def get_class(self):
		"""
		>>> FeitElectricLights(name='test', label='Test', address='0000').get_class()
		'light'
		"""
		return self.CLASS

	def _state_path(self):
		return '%s/%s' % (self.CLASS, self.name)

	def _get(self):
		""" Loads the given value from the remembered state """
		return super(FeitElectric, self)._get(self._state_path())
	def _set(self, state):
		""" Saves the given value to the remembered state """
		super(FeitElectric, self)._set(self._state_path(), state)

	def get_state(self):
		return self._get()

class FeitElectricLights(FeitElectric):
	CLASS = 'light'

	def subdevices(self):
		return {'color': FeitElectricLightsColor(name=self.name, label=self.label, address=self.address)}

	def get_available_states(self):
		return ["OFF", "ON"] + FeitElectricLightsColor.COLORS

	def set_state(self, state):
		if state in FeitElectricLightsColor.COLORS:
			return self.subdevices()['color'].set_state(state)
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		self._send_command(state.lower())
		self._set(state)
		return state

class FeitElectricLightsColor(FeitElectric):
	CLASS = 'light'
	COLORS = ["RED", "GREEN", "BLUE", "WHITE"]

	def _state_path(self):
		return '%s/%s/color' % (self.CLASS, self.name)

	def get_available_states(self):
		return self.COLORS

	def set_state(self, state):
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		self._send_command(state.lower())
		self._set(state)
		return state

