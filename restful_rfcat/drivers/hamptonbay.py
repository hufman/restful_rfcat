# A device driver to interact with Hampton ceiling fans
from operator import itemgetter
import logging
import struct
import re
from restful_rfcat import radio
from restful_rfcat.drivers._utils import DeviceDriver, PWMThreeSymbolMixin, ThreeSpeedFanMixin, LightMixin

logger = logging.getLogger(__name__)

class HamptonCeiling(DeviceDriver, PWMThreeSymbolMixin):
	devices = {}
	commands = {
		'fan0': '1111',
		'fan1': '1001',
		'fan2': '1011',
		'fan3': '1101',
		'lighton': '0011',
		'lightoff': '1011'
	}
	radio = radio.OOKRadio(303700000, 3324)

	def __init__(self, dip_switch, **kwargs):
		""" dip_switch is the jumper settings from the remote
		Left (1) to right (4)
		"""
		# save the name and label
		super(HamptonCeiling, self).__init__(**kwargs)
		self.dip_switch = dip_switch
		self._remember_device()

	def _remember_device(self):
		# magical registration of devices for eavesdropping
		class_name = self.__class__.__name__
		device_type = class_name[len('HamptonCeiling'):].lower()
		device_name = '%s-%s' % (self.dip_switch, device_type)
		self.devices[device_name] = self

	@classmethod
	def _get_device(klass, device_type, dip_switch):
		device_name = '%s-%s' % (dip_switch, device_type.lower())
		return klass.devices.get(device_name)

	@staticmethod
	def _encode(bin_key):
		"""
		>>> print(HamptonCeiling._encode("00110011"))
		\x00\x00\x00\x00\x00%\xb2[
		"""
		pwm_str_key = HamptonCeiling._encode_pwm_symbols(bin_key)
		pwm_str_key = "" + pwm_str_key #added leading 0 for clock
		#print "Binary (PWM) key:",pwm_str_key
		dec_pwm_key = int(pwm_str_key, 2);
		#print "Decimal (PWN) key:",dec_pwm_key
		key_packed = ''
		while dec_pwm_key > 0:
			key_packed = struct.pack(">Q", dec_pwm_key & (2**64-1)) + key_packed
			dec_pwm_key = dec_pwm_key >> 64
		return key_packed

	@classmethod
	def _send(klass, bits):
		symbols = klass._encode(bits)
		klass.radio.send(symbols)

	def _send_command(self, bits):
		logger.info("Sending bits %s to %s" % (bits, self.dip_switch))
		self._send(self._get_bin_key(bits))

	def _get_bin_key(self, bits):
		"""
		>>> HamptonCeiling(name='test', label='Test', dip_switch='1011')._get_bin_key('1011')
		'01111101111111101110100000000000000000000000'
		>>> HamptonCeiling(name='test', label='Test', dip_switch='0010')._get_bin_key('0011')
		'01110100111111001110100000000000000000000000'
		"""
		bin_key = '0111%s111111%s1010' % (self.dip_switch[::-1], bits)
		bin_key = bin_key + '0'*22
		return bin_key

	def set_state_combined(self, light=None, fan=None):
		""" light should be on or off
		    fan should be 0,1,2,3
		"""
		if light is None:
			device = self._get_device(device_type='Light', dip_switch=self.dip_switch)
			light = device.get_state().lower()
			light = 'on' if light is None else light
		if fan is None:
			device = self._get_device(device_type='Fan', dip_switch=self.dip_switch)
			fan = device.get_state()
			fan = '0' if fan is None else fan
		light_command = '0' if light == 'on' else '1'
		fan_command = self.commands['fan%s'%fan][1:]
		command = light_command + fan_command
		self._send_command(command)

class HamptonCeilingFan(ThreeSpeedFanMixin, HamptonCeiling):
	def set_state(self, state):
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		command = self._state_to_command(state)
		super(HamptonCeilingFan, self).set_state_combined(light=None, fan=command)
		self._set(state)
		return state

class HamptonCeilingLight(LightMixin, HamptonCeiling):
	def set_state(self, state):
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		command = self._state_to_command(state)
		super(HamptonCeilingLight, self).set_state_combined(light=command.lower(), fan=None)
		self._set(state)
		return state
