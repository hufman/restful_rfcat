from restful_rfcat.drivers import lirc
import unittest

class TestLircConfig(unittest.TestCase):
	def test_load_hampton(self):
		desired = {'remote': {
			'name': 'UC7078T',
			'bits': '7',
			'flags': 'SPACE_FIRST|REVERSE',
			'eps': '30',
			'aeps': '100',
			'pre_data_bits': '4',
			'pre_data': '0x0b',
			'header': '400 300',
			'plead': '700',
			'zero': '300 700',
			'one': '700 300',
			'min_repeat': '5',
			'gap': '12000',
			'codes': {
				# first KEY_LIGHTS_TOGGLE gets overwritten
				'FAN_HIGH': '0x02',
				'FAN_MED': '0x04',
				'FAN_LOW': '0x08',
				'FAN_OFF': '0x20',
				'KEY_LIGHTS_TOGGLE': '0x40'
			}
		}}
		conf = lirc._parse_lirc_config('hampton_bay_UC7078T')
		self.assertEqual(desired, conf)

	def test_understand_hampton(self):
		desired = {
			'name': 'UC7078T',
			'bits': 7,
			'flags': ['SPACE_FIRST', 'REVERSE'],
			'eps': 30,
			'aeps': 100,
			'pre_data_bits': 4,
			'pre_data': 0x0b,
			'header': (400, 300),
			'plead': 700,
			'zero': (300, 700),
			'one': (700, 300),
			'min_repeat': 5,
			'gap': 12000,
			'codes': {
				# first KEY_LIGHTS_TOGGLE gets overwritten
				'FAN_HIGH': 0x02,
				'FAN_MED': 0x04,
				'FAN_LOW': 0x08,
				'FAN_OFF': 0x20,
				'KEY_LIGHTS_TOGGLE': 0x40,
			}
		}
		conf = lirc._parse_lirc_config('hampton_bay_UC7078T')
		understood = lirc._understand_lirc_config(conf)
		self.assertEqual(desired, understood)

	def test_understand_hunter(self):
		desired = {
			'name': 'TX28',
			'bits': 7,
			'flags': ['SPACE_FIRST'],
			'eps': 30,
			'aeps': 100,
			'pre_data_bits': 4,
			'pre_data': 0x0b,
			'header': (190, 380),
			'plead': 190,
			'zero': (190, 380),
			'one': (380, 190),
			'min_repeat': 5,
			'gap': 6650,
			'codes': {
				# first KEY_LIGHTS_TOGGLE gets overwritten
				'FAN_HIGH': 0x74,
				'FAN_MED': 0x72,
				'FAN_LOW': 0x71,
				'FAN_OFF': 0x79,
				'LIGHT_TOGGLE': 0x78,
			}
		}
		conf = lirc._parse_lirc_config('hunter_fan_TX28')
		understood = lirc._understand_lirc_config(conf)
		self.assertEqual(desired, understood)

class TestLircBaudrate(unittest.TestCase):
	def test_guess_hampton_baudrate(self):
		conf = lirc._parse_lirc_config('hampton_bay_UC7078T')
		understood = lirc._understand_lirc_config(conf)
		baudrate_divisor = lirc.LircRemote.guess_baudrate_divisor(understood)
		self.assertEqual(100, baudrate_divisor)

	def test_guess_max_baudrate(self):
		baudrate_divisor = lirc.LircRemote.guess_baudrate_divisor({
			'gap': 500
		})
		self.assertEqual(500, baudrate_divisor)

		baudrate_divisor = lirc.LircRemote.guess_baudrate_divisor({
			'gap': 2000
		})
		self.assertEqual(2000, baudrate_divisor)

		baudrate_divisor = lirc.LircRemote.guess_baudrate_divisor({
			'gap': 2000000
		})
		self.assertEqual(1000000, baudrate_divisor)

		baudrate_divisor = lirc.LircRemote.guess_baudrate_divisor({
			'gap': 900000
		})
		self.assertEqual(100000, baudrate_divisor)

