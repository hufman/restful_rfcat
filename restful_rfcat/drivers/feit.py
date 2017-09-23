# A device driver to interact with Feit Electric LED lights
from operator import itemgetter
import logging
import struct
import re
from restful_rfcat import radio
from restful_rfcat.drivers._utils import DeviceDriver, SubDeviceDriver

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
	radio = radio.OOKRadio(433920000, 4880)

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
		FeitElectric lights have a precise gap of 22.5-24 zeros between each command
		Which is hard to line up to byte boundaries

		>>> FeitElectric._encode("01100110")
		'\\xa0\\xa0\\x00\\x00\\x14\\x14\\x00\\x00\\x02\\x82\\x80\\x00\\x00PP\\x00\\x00\\n\\n\\x00\\x00\\x01A@\\x00\\x00\\x00'
		"""
		pwm_str_key = FeitElectric._encode_pwm(bin_key)
		# Each command bitstring has a gap of 22.5 0s, measured to be 20
		pwm_str_key = pwm_str_key.strip('0') + '0' * 24
		#print "Binary (PWM) key:",pwm_str_key
		key_packed = ''
		pwm_index = 0
		iterations = 5
		while pwm_index != len(pwm_str_key) and iterations >= 0:
			str_byte = pwm_str_key[pwm_index:pwm_index+8]
			pwm_index = pwm_index + 8
			if len(str_byte) < 8:
				if iterations > 0:
					# wrap around the string
					pwm_index = pwm_index - len(pwm_str_key)
					str_byte = str_byte + pwm_str_key[0:pwm_index]
					# make sure we don't get stuck
					iterations = iterations - 1
				else:
					# fill out with 0s
					pwm_index = pwm_index - len(pwm_str_key)
					str_byte = str_byte + '0'*pwm_index
					# make sure we don't get stuck
					iterations = iterations - 1
			int_byte = int(str_byte, 2)
			key_packed = key_packed + struct.pack(">B", int_byte)
		return key_packed

	@classmethod
	def _send(klass, bits):
		symbols = klass._encode(bits)
		klass.radio.send(symbols, repeat=5)

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
		'lights'
		"""
		return self.CLASS

	def get_state(self):
		return self._get()

class FeitElectricLightsColor(SubDeviceDriver):
	STATE_COMMANDS = {
		"RED": "RED",
		"GREEN": "GREEN",
		"BLUE": "BLUE",
		"WHITE": "WHITE"
	}

	@classmethod
	def get_name(klass):
		return "color"

	def set_state(self, state):
		command = self._state_to_command(state)
		self.parent._send_command(command.lower())
		self._set(state)
		return state

class FeitElectricLights(FeitElectric):
	CLASS = 'lights'

	SUBDEVICES = [FeitElectricLightsColor]

	def get_acceptable_states(self):
		return ["OFF", "ON"] + FeitElectricLightsColor.get_acceptable_states()

	def get_available_states(self):
		return ["OFF", "ON"]

	def set_state(self, state):
		if state in self.subdevices['color'].get_acceptable_states():
			return self.subdevices['color'].set_state(state)
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		self._send_command(state.lower())
		self._set(state)
		return state

