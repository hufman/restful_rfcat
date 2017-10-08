# A device driver to interact with devices with LIRC definitions
from operator import itemgetter
import itertools
import logging
import os.path
import struct
import re
from restful_rfcat import radio
from restful_rfcat.drivers._utils import DeviceDriver, SubDeviceDriver, LightMixin, ThreeSpeedFanMixin

logger = logging.getLogger(__name__)

def _parse_lirc_config(config_filename, config_file=None):
	def parse(config_file):
		blank_line_matcher = re.compile(r'^\s*(#.*)?$')
		clean_line_matcher = re.compile(r'^\s*([^#]*)(?:#.*)?$')
		whitespace_splitter = re.compile(r'\s*')
		data = {}
		parent_contexts = []
		context = data
		for line in config_file:
			if blank_line_matcher.match(line):
				continue
			line = clean_line_matcher.sub(r'\1', line).strip()
			if line.startswith('begin'):
				parent_contexts.append(context)
				context_name = line[6:]
				context[context_name] = {}
				context = context[context_name]
			elif line.startswith('end'):
				context = parent_contexts.pop()
			else:
				splits = whitespace_splitter.split(line, 1)
				if len(splits) == 2:
					context[splits[0].strip()] = splits[1].strip()
		return data

	if config_file is None:
		current_dir = os.path.dirname(os.path.realpath(__file__))
		config_dir = os.path.join(current_dir, '..', '..', 'lirc_remotes')
		abs_config_filename = os.path.join(config_dir, config_filename)
		with open(abs_config_filename, 'r') as config_file:
			# automatically close this file after parsing
			return parse(config_file)
	elif config_file is not None:
		return parse(config_file)
	else:
		raise ValueError("Must pass a config file to parse")

def _understand_lirc_config(config):
	# common types
	decimal_integer = int
	hexadecimal_number = lambda s: int(s, 16)
	duple = lambda s: tuple(s.split(' ', 1))
	duple_ints = lambda s: tuple([decimal_integer(i) for i in s.split(' ', 1)])
	flags = lambda s: [f.strip() for f in s.split('|')]
	dict_hexadecimal_numbers = lambda c: dict([(k, hexadecimal_number(v)) for k,v in c.items()])
	# field definitions
	parsers = {
		# taken from http://winlirc.sourceforge.net/technicaldetails.html
		'bits': decimal_integer,
		'flags': flags,
		'eps': decimal_integer,
		'aeps': decimal_integer,
		'header': duple_ints,
		'three': duple_ints,
		'two': duple_ints,
		'one': duple_ints,
		'zero': duple_ints,
		'ptrail': decimal_integer,
		'plead': decimal_integer,
		'foot': duple_ints,
		'repeat': duple_ints,
		'pre_data_bits': decimal_integer,
		'pre_data': hexadecimal_number,
		'post_data_bits': decimal_integer,
		'post_data': hexadecimal_number,
		'pre': duple_ints,
		'post': duple_ints,
		'gap': decimal_integer,
		'repeat_gap': decimal_integer,
		'min_repeat': decimal_integer,
		'toggle_bit': decimal_integer,
		'frequency': decimal_integer,
		'duty_cycle': decimal_integer,
		'codes': dict_hexadecimal_numbers,
		'raw_codes': dict_hexadecimal_numbers,
	}
	result = {}
	for k,v in config['remote'].items():
		if k in parsers:
			result[k] = parsers[k](v)
		else:
			result[k] = v
	return result

class LircRemote(object):
	def __init__(self, config_filename, **kwargs):
		if config_filename != None:
			self.config = _understand_lirc_config(_parse_lirc_config(config_filename))
		else:
			self.config = {}	# specify everything with kwargs
		self.config.update(kwargs)	# any custom things, like remote-specific predata
		self.baud_divisor = self.guess_baudrate_divisor(self.config)

	@classmethod
	def guess_baudrate_divisor(klass, config):
		""" Given a config, with millisecond times entered in
		    Figure out a millisecond length that can be divided into each
		    without loosing too much precision
		    For example, [400,300] have 100 as the common denominator
		    Baudrate would then be 1000000/100 = 10000, and each time value
		    should be divided by 100 to get the number of symbol slots
		    to output that symbol at that baudrate
		"""
		# build a list of all the millisecond time values to check
		times_tuples_keys = ['header', 'three', 'two', 'one', 'zero',
		                     'foot', 'repeat', 'pre', 'post']
		times_keys = ['ptrail', 'phead', 'gap', 'repeat_gap']
		times = []
		times.append(1000000)	# can't have a baudrate of less than 1
		for k in times_tuples_keys:
			if k in config:
				times.append(config[k][0])
				times.append(config[k][1])
		for k in times_keys:
			if k in config:
				times.append(config[k])
		# try finding a common factor among them all
		total_factor = 1
		factored = True
		while factored:
			factored = False
			factor_errors = {}
			for factor in [2,3,5,7,11,17,19,23]:
				new_factor = 1.0 * total_factor * factor
				int_times = [int(t / new_factor) for t in times]
				rounded_times = [t * new_factor for t in int_times]
				errors = [abs(o-n)*1.0/o for o,n in zip(times, rounded_times)]
				factor_errors[factor] = max(errors)
			# figure out which factor had the least error
			new_factor = None
			min_error = 0.05
			for f,e in factor_errors.items():
				if e < min_error:
					min_error = e
					new_factor = total_factor * f
			if new_factor:
				factored = True
				total_factor = new_factor
		return total_factor

	def _encode_bit(self, bit, length):
		"""
		Using this remote's guessed baudrate,
		turn the millisecond length into a sequence of repeated bits

		>>> LircRemote(config_filename=None, one=(300, 700))._encode_bit('0', 300)
		'000'
		>>> LircRemote(config_filename=None, one=(300, 700))._encode_bit('0', 260)
		'000'
		>>> LircRemote(config_filename=None, one=(300, 700))._encode_bit('0', 340)
		'000'
		"""
		periods = int(round(length * 1.0 / self.baud_divisor))
		return bit * periods

	def _encode_tuple(self, time_tuple):
		"""
		Given a tuple of (pulse_ms, space_ms)
		Return the encoded bits

		>>> LircRemote(config_filename=None, one=(300, 700))._encode_tuple((300, 400))
		'1110000'
		"""
		return self._encode_bit('1', time_tuple[0]) + self._encode_bit('0', time_tuple[1])

	def _encode_pwm_bit(self, bit):
		"""
		When inside _encode_data, encode a 0 or a 1 by using the
		configured zero/one lengths

		>>> LircRemote(config_filename=None, zero=(300, 700), one=(700, 300))._encode_pwm_bit('0')
		'1110000000'
		>>> LircRemote(config_filename=None, zero=(300, 700), one=(700, 300))._encode_pwm_bit('1')
		'1111111000'
		>>> LircRemote(config_filename=None, zero=(300, 700), one=(700, 300), flags=['SPACE_FIRST'])._encode_pwm_bit('0')
		'0000000111'
		>>> LircRemote(config_filename=None, zero=(300, 700), one=(700, 300), flags=['SPACE_FIRST'])._encode_pwm_bit('1')
		'0001111111'
		"""
		mode = {"0": "zero", "1": "one"}[bit]
		time_tuple = self.config[mode]
		if 'SPACE_FIRST' in self.config.get('flags', []):
			return ''.join(reversed(self._encode_tuple(time_tuple)))
		else:
			return self._encode_tuple(time_tuple)

	def _encode_data(self, data, data_len):
		"""
		Encode a numeric value into a bitstring

		LIRC has a complicated way of looking at the data bits in the code
		It reverses the bits of the data, so that the first bit to send is on the right,
		sends that right-most bit, and then right-shifts the next bit into place
		If the REVERSE flag is set, then it pre-reverses all the commands as it loads the config
		This means that the data_len starts counting at the right-most bit and extends to the left
		
		>>> LircRemote(config_filename=None, zero=(300, 700), one=(700, 300))._encode_data(0x0b, 4)
		'1111111000111000000011111110001111111000'
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100))._encode_data(0x0b, 16)
		'100100100100100100100100100100100100110100110110'

		>>> LircRemote(config_filename=None, zero=(300, 700), one=(700, 300), flags=['REVERSE'])._encode_data(0x0b, 4)
		'1111111000111111100011100000001111111000'
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), flags=['REVERSE'])._encode_data(0x0b, 16)
		'110110100110100100100100100100100100100100100100'
		"""
		conf_bitstring = bin(data)
		if conf_bitstring.startswith('0b'):
			conf_bitstring = conf_bitstring[2:]
		given_length = len(conf_bitstring)
		extra_length = max(0, data_len-given_length)
		bitstring = '0'*extra_length + conf_bitstring
		if 'REVERSE' in self.config.get('flags', []):
			bitstring = reversed(bitstring)
		encoded_data_bits = (self._encode_pwm_bit(b) for b in bitstring)
		return ''.join(itertools.chain(*encoded_data_bits))

	def _encode_header(self):
		"""
		>>> LircRemote(config_filename=None)._encode_header()
		>>> LircRemote(config_filename=None, header=(100, 200))._encode_header()
		'100'
		"""
		header = self.config.get('header')
		if header is not None:
			return self._encode_tuple(header)

	def _encode_lead(self):
		"""
		>>> LircRemote(config_filename=None)._encode_lead()
		>>> LircRemote(config_filename=None, one=(200, 100), plead=100)._encode_lead()
		'1'
		"""
		plead = self.config.get('plead')
		if plead is not None:
			return self._encode_bit('1', plead)

	def _encode_pre(self):
		"""
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100))._encode_pre()
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), pre_data=0x0b, pre_data_bits=4)._encode_pre()
		'110100110110'
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), pre_data=0x0b, pre_data_bits=4, pre=(300, 200))._encode_pre()
		'11010011011011100'

		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), pre_data=0x0b, pre_data_bits=4, flags=['REVERSE'])._encode_pre()
		'110110100110'
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), pre_data=0x0b, pre_data_bits=4, pre=(300, 200), flags=['REVERSE'])._encode_pre()
		'11011010011011100'
		"""
		pre_data = self.config.get('pre_data')
		if pre_data is not None:
			pre_data = self._encode_data(pre_data, self.config.get('pre_data_bits'))
			if self.config.get('pre'):
				pre_pulse = self._encode_tuple(self.config['pre'])
				return pre_data + pre_pulse
			else:
				return pre_data

	def _encode_post(self):
		"""
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100))._encode_post()
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), post_data=0x0b, post_data_bits=4)._encode_post()
		'110100110110'
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), post_data=0x0b, post_data_bits=4, post=(300, 200))._encode_post()
		'11100110100110110'

		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), post_data=0x0b, post_data_bits=4, flags=['REVERSE'])._encode_post()
		'110110100110'
		>>> LircRemote(config_filename=None, zero=(100, 200), one=(200, 100), post_data=0x0b, post_data_bits=4, post=(300, 200), flags=['REVERSE'])._encode_post()
		'11100110110100110'
		"""
		post_data = self.config.get('post_data')
		if post_data is not None:
			post_data = self._encode_data(post_data, self.config.get('post_data_bits'))
			if self.config.get('post'):
				post_pulse = self._encode_tuple(self.config['post'])
				return post_pulse + post_data
			else:
				return post_data

	def _encode_trail(self):
		"""
		>>> LircRemote(config_filename=None)._encode_trail()
		>>> LircRemote(config_filename=None, one=(200, 100), ptrail=100)._encode_trail()
		'1'
		"""
		ptrail = self.config.get('ptrail')
		if ptrail is not None:
			return self._encode_bit('1', ptrail)

	def _encode_foot(self):
		"""
		>>> LircRemote(config_filename=None)._encode_foot()
		>>> LircRemote(config_filename=None, foot=(100, 200))._encode_foot()
		'100'
		"""
		foot = self.config.get('foot')
		if foot is not None:
			return self._encode_tuple(foot)

	def _encode_gap(self):
		"""
		>>> LircRemote(config_filename=None)._encode_gap()
		''
		>>> LircRemote(config_filename=None, foot=(100, 200), repeat_gap=1500)._encode_gap()
		'000000000000000'
		>>> LircRemote(config_filename=None, foot=(100, 200), gap=200)._encode_gap()
		'00'
		>>> LircRemote(config_filename=None, foot=(100, 200), gap=200, repeat_gap=1500)._encode_gap()
		'000000000000000'
		"""
		gap_length = self.config.get('repeat_gap',
		             self.config.get('gap',
		             0))
		return self._encode_bit('0', gap_length)

	def _encode_button(self, command):
		"""
		Yields bitstrings to represent a button press
		Each yielded string contains a single transmission
		Fetch the next generated string for the next repeat
		Depending on the remote settings, it might be different!
		Roughly based on https://sourceforge.net/p/lirc/git/ci/master/tree/lib/transmit.c

		>>> remote = LircRemote(config_filename='hampton_bay_UC7078T', gap=500)
		>>> remote.encode_button('FAN_HIGH')
		'111100011111110001111111000111111100000001110001111111000000011100011111110000000111000000011100000001110000000111000000011100000'

		"""
		max_repeat = 20
		order = ['header', 'lead', 'pre', 'data', 'post', 'trail', 'foot', 'gap']
		# if flags are in place to not send head/foot when repeating
		# clear the segments out
		if 'NO_HEAD_REP' in self.config['flags']:
			order.remove('header')
		if 'NO_FOOT_REP' in self.config['flags']:
			order.remove('foot')
		pieces = []
		for step_name in order:
			step_func = getattr(self, '_encode_%s' % (step_name,))
			if step_name == 'data':
				piece = self._encode_data(self.config['codes'][command], self.config['bits'])
			else:
				piece = step_func()
			if piece is not None:
				pieces.append(piece)
		for encoded in itertools.repeat(''.join(pieces), max_repeat):
			yield encoded

	def encode_button(self, command):
		""" Like _encode_button, but as a simple string instead of iterator """
		return next(self._encode_button(command))

class Lirc(DeviceDriver):
	devices = {}

	def __init__(self, config_filename, radio_frequency=None, custom_radio=None, **kwargs):
		""" Controls a device as described by an LIRC remote control config

		config_filename is a file relative to lirc_remotes configuration, or absolute path
		that describes a remote control's protocol
		radio_frequency is the hz to send the commands, or a custom_radio can be given
		Extra options can be passed to override the configuration, such as specifying
		custom pre_data options for different remote control dip switch settings
		"""
		parent_kwargs = {
			'name': kwargs.pop('name'),
			'label': kwargs.pop('label')
		}
		super(Lirc, self).__init__(**parent_kwargs)
		self.remote = LircRemote(config_filename, **kwargs)
		baudrate = 1000000 / self.remote.baud_divisor
		if radio_frequency is not None:
			self.radio = radio.OOKRadio(radio_frequency, baudrate)
		elif custom_radio is not None:
			self.radio = custom_radio
		else:
			raise ValueError("LIRC devices require a radio_frequency or custom_radio")
		self._remember_device()

	def _remember_device(self):
		# magical registration of devices for eavesdropping
		class_name = self.__class__.__name__
		device_type = class_name[len('Lirc'):].lower()
		device_name = '%s-%s' % (device_type, self.name)
		self.devices[device_name] = self

	@classmethod
	def _get_device(klass, device_type, name):
		device_name = '%s-%s' % (device_type.lower(), name)
		return klass.devices.get(device_name)

	@staticmethod
	def _chunk(iterable, size, fillvalue=None):
		"""
		Iterate through a list in multiple chunks
		Based on https://stackoverflow.com/a/434411

		>>> Lirc._chunk("01234567", 3, "x")
		['012', '345', '67x']
		"""
		args = [iter(iterable)] * size
		return [''.join(x) for x in itertools.izip_longest(*args, fillvalue=fillvalue)]

	@classmethod
	def _encode(klass, pwm_str_key):
		"""
		Convert a bitstring into a byte array for rflib to send
		#>>> Lirc._encode("01110011")
		#'s'
		>>> Lirc._encode("00000001001001011011001001011011")
		'\\x01%\\xb2['
		>>> Lirc._encode("000111000110100001110011")
		'\\x1chs'
		"""
		#print("Encoding pwm key %s" % (pwm_str_key,))
		dec_pwm_key = int(pwm_str_key, 2)
		#print "Decimal (PWN) key:",dec_pwm_key
		key_packed = ''
		for byte in Lirc._chunk(pwm_str_key, 8, '0'):
			dec_pwm_key = int(byte, 2)
			key_packed = key_packed + struct.pack(">B", dec_pwm_key)
		return key_packed

	def _send(self, bits):
		symbols = self._encode(bits)
		self.radio.send(symbols, repeat=5)

	def _send_command(self, command):
		logger.info("Sending command %s with LIRC remote %s" % (command,self.name))
		bitstring = self._get_bin_key(command)
		self._send(bitstring)

	def _get_bin_key(self, command):
		"""
		>>> Lirc(name='test', label='Test', config_filename='hampton_bay_UC7078T', radio_frequency=303000000, gap=500)._get_bin_key('FAN_HIGH')
		'111100011111110001111111000111111100000001110001111111000000011100011111110000000111000000011100000001110000000111000000011100000'

		Based on the code in https://sourceforge.net/p/lirc/git/ci/master/tree/lib/transmit.c
		"""
		return self.remote.encode_button(command)

	def get_class(self):
		"""
		>>> LircLight(name='test', label='Test', config_filename='hampton_bay_UC7078T', radio_frequency=303000000).get_class()
		'lights'
		"""
		return self.CLASS

	def get_state(self):
		return self._get()

	def _get_available_commands(self):
		return self.remote.config['codes'].keys()


class LircLight(LightMixin, Lirc):
	def _send_command(self, command):
		# LightMixin will send a command of ON/OFF
		# Try to find the lirc command to handle it
		commands = self._get_available_commands()
		code = None

		code_name = 'LIGHT_%s' % (state.upper(),)  # look for LIGHT_ON or LIGHT_OFF
		if code_name in commands:
			code = code_name

		toggle_commands = ['LIGHT_TOGGLE', 'LIGHTS_TOGGLE',
		                   'KEY_LIGHT_TOGGLE', 'KEY_LIGHTS_TOGGLE']
		found_toggle_commands = [c for c in toggle_commands if c in commands]
		if len(found_toggle_commands) > 0:
			code = found_toggle_commands[0]

		if code is None:
			raise ValueError("Could not determine remote control command for logical command %s" % (command,))
		super(LircLight, self)._send_command(code)

class LircThreeWayFan(ThreeSpeedFanMixin, Lirc):
	COMMAND_NAMES = {
		'0': 'FAN_OFF',
		'1': 'FAN_LOW',
		'2': 'FAN_MED',
		'3': 'FAN_HIGH',
	}

	def _send_command(self, command, repeat=None):
		# ThreeSpeedFanMixin will send a command of 0,1,2,3
		# Change this to LIRC command names
		super(LircThreeWayFan, self)._send_command(self.COMMAND_NAMES[command])
