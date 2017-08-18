# A device driver to interact with Hunter ceiling fans
from operator import itemgetter
import logging
import struct
import re
from restful_rfcat import radio, hideyhole
from restful_rfcat.drivers._utils import DeviceDriver

logger = logging.getLogger(__name__)

class HunterCeiling(DeviceDriver):
	devices = {}
	commands = {
		'fan0': '1001',
		'fan1': '0001',
		'fan2': '0010',
		'fan3': '0100',
		'light': '1000'
	}
	commands_rev = dict([(v,k) for k,v in commands.items()])
	radio = radio.OOKRadioChannelHack(347999900, 5280, 2)

	def __init__(self, dip_switch, **kwargs):
		""" dip_switch is the jumper settings from the remote
		Left (4) to right (1), with connected jumpers as 1 and others as 1
		"""
		# save the name and label
		super(HunterCeiling, self).__init__(**kwargs)
		self.dip_switch = dip_switch
		self._remember_device()

	def _remember_device(self):
		# magical registration of devices for eavesdropping
		class_name = self.__class__.__name__
		device_type = class_name[len('HunterCeiling'):].lower()
		device_name = '%s-%s' % (self.dip_switch, device_type)
		self.devices[device_name] = self

	@staticmethod
	def _encode_pwm(bin_key):
		"""
		>>> HunterCeiling._encode_pwm("00110011")
		'001001011011001001011011'
		"""
		pwm_str_key = []
		for k in bin_key:
			x = ""
			if(k == "0"):
				x = "001" #  A zero is encoded as a longer low pulse (low-low-high)
			if(k == "1"):
				x = "011" # and a one is encoded as a shorter low pulse (low-high-high)
			pwm_str_key.append(x)
		return ''.join(pwm_str_key)

	@staticmethod
	def _encode(bin_key):
		"""
		>>> print(HunterCeiling._encode("00110011"))
		\x00\x00\x00\x00\x01%\xb2[
		"""
		pwm_str_key = HunterCeiling._encode_pwm(bin_key)
		pwm_str_key = "001" + pwm_str_key #added leading 0 for clock
		#print "Binary (PWM) key:",pwm_str_key
		dec_pwm_key = int(pwm_str_key, 2);
		#print "Decimal (PWN) key:",dec_pwm_key
		key_packed = struct.pack(">Q", dec_pwm_key)
		return key_packed

	@classmethod
	def _send(klass, bits):
		symbols = klass._encode(bits)
		klass.radio.send(symbols + '\x00')

	def _send_command(self, command):
		logger.info("Sending command %s to %s" % (command, self.dip_switch))
		self._send(self._get_bin_key(command))

	def _get_bin_key(self, command):
		"""
		>>> HunterCeiling(name='test', label='Test', dip_switch='1011')._get_bin_key('fan2')
		'011011110010'
		>>> HunterCeiling(name='test', label='Test', dip_switch='0010')._get_bin_key('light')
		'001001111000'
		"""
		bin_key = '0%s111%s' % (self.dip_switch[::-1], self.commands[command])
		return bin_key

	def get_class(self):
		"""
		>>> HunterCeilingFan(name='test', label='Test', dip_switch='0000').get_class()
		'fan'
		>>> HunterCeilingLight(name='test', label='Test', dip_switch='0000').get_class()
		'light'
		"""
		return self.CLASS

	def _get(self):
		""" Loads the given value from the remembered state """
		return super(HunterCeiling, self)._get('%s/%s' % (self.CLASS, self.name))
	def _set(self, state):
		""" Saves the given value to the remembered state """
		super(HunterCeiling, self)._set('%s/%s' % (self.CLASS, self.name), state)

	def get_state(self):
		return self._get()

class HunterCeilingFan(HunterCeiling):
	CLASS = 'fan'

	def get_available_states(self):
		return ["OFF", "0", "1", "2", "3"]

	@staticmethod
	def _state_to_command(state):
		"""
		>>> HunterCeilingFan._state_to_command('1')
		'fan1'
		>>> HunterCeilingFan._state_to_command('0')
		'fan0'
		>>> HunterCeilingFan._state_to_command('OFF')
		'fan0'
		"""
		command = 'fan%s' % (state,)
		if state == 'OFF':
			command = 'fan0'
		return command
	@staticmethod
	def _normalize_state(state):
		"""
		>>> HunterCeilingFan._normalize_state('1')
		'1'
		>>> HunterCeilingFan._normalize_state('0')
		'OFF'
		"""
		if state == '0':
			state = 'OFF'
		return state

	def set_state(self, state):
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		command = self._state_to_command(state)
		self._send_command(command)
		state = self._normalize_state(state)
		self._set(state)
		return state

class HunterCeilingLight(HunterCeiling):
	CLASS = 'light'

	def get_available_states(self):
		return ["OFF", "ON"]

	def set_state(self, state):
		if state not in self.get_available_states():
			raise ValueError("Invalid state: %s" % (state,))
		self._send_command('light')
		self._set(state)
		return state

class HunterCeilingEavesdropper(HunterCeiling):
	def __init__(self):
		# don't register as a device with the regular super constractor
		self.packets_seen = {}

	@staticmethod
	def _decode_symbols(symbols):
		""" Turns a string of radio symbols into a PCM-decoded packet
		>>> HunterCeilingEavesdropper._decode_symbols("1001011001011")
		'0101'
		>>> HunterCeilingEavesdropper._decode_symbols( \
			'1'+HunterCeiling._encode_pwm("001001110101") \
		)
		'001001110101'
		"""
		if len(symbols) < 6:
			return None
		if symbols[0] != '1':
			return None
		bits = []
		for counter in range(1, len(symbols), 3):
			encoded_bit = symbols[counter:counter+3]
			if encoded_bit == '001':
				bits.append('0')
			elif encoded_bit == '011':
				bits.append('1')
			else:
				# invalid sequence
				return None
		return ''.join(bits)

	@staticmethod
	def _parse_packet(packet):
		""" Returns (dip_switch, command) for a valid packet
		    else returns (None, None)
		>>> HunterCeilingEavesdropper._parse_packet("001001110101")
		('0010', '0101')
		"""
		if len(packet) == 12:
			match = re.match('0([01]{4})111([01]{4})', packet)
			if match is not None:
				return (match.group(1)[::-1], match.group(2))
		return (None, None)

	@classmethod
	def validate_packet(klass, packet):
		""" Given a decoded packet
		    check that the given packet is syntactical
		>>> HunterCeilingEavesdropper.validate_packet("001001110101")
		False
		>>> HunterCeilingEavesdropper.validate_packet("001001110100")
		True
		"""
		if packet is None:
			return False
		(dip_switch, command) = klass._parse_packet(packet)
		return command is not None and command in klass.commands_rev

	@classmethod
	def handle_packet(klass, packet, count):
		(dip_switch, command) = klass._parse_packet(packet)
		logger.info("Overheard command %s to %s" % (command, dip_switch))
		if command is not None and command in klass.commands_rev:
			# find device
			command = klass.commands_rev[command]
			if command.startswith('fan'):
				device_type = 'fan'
			elif command.startswith('light'):
				device_type = 'light'
			device_name = '%s-%s' % (dip_switch, device_type)
			found_device = klass.devices.get(device_name)
			# find new state
			state = None
			if command.startswith('fan'):
				# idempotent state set
				state = command[3]
				if state == '0':
					state = 'OFF'
			elif command.startswith('light') and found_device is not None:
				# toggle light
				old_state = found_device._get()
				available_states = found_device.get_available_states()
				try:
					old_state_index = available_states.index(old_state)
					new_state_index = len(available_states) - 1 - old_state_index
					state = available_states[new_state_index]
				except ValueError:
					# don't know current state, don't guess new state
					pass
			if found_device is not None and state is not None:
				found_device._set(state)

	def eavesdrop(self):
		saw_packet = False
		packets = self.radio.receive_packets(20)
		if packets is None:
			# error, try again next time
			return None
		logical_packets = [self._decode_symbols(p) for p in packets]
		for p in logical_packets:
			if not self.validate_packet(p):
				continue
			count = self.packets_seen.get(p, 0)
			self.packets_seen[p] = count + 1
			saw_packet = True

		if not saw_packet:
			if len(self.packets_seen) > 0:
				# end of an existing transmission
				key, count = max(self.packets_seen.items(), key=itemgetter(1))
				self.handle_packet(key, count)
				self.packets_seen.clear()
