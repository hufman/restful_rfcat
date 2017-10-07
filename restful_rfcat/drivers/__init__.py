# All of the available drivers to use in config files
from restful_rfcat.drivers.hunter import HunterCeilingFan, HunterCeilingLight, HunterCeilingEavesdropper
from restful_rfcat.drivers.hamptonbay import HamptonCeilingFan, HamptonCeilingLight
from restful_rfcat.drivers.feit import FeitElectricLights
from restful_rfcat.drivers.lirc import LircLight, LircThreeWayFan

# example implementation
from restful_rfcat.drivers._utils import DeviceDriver, LightMixin, ThreeSpeedFanMixin
class FakeDevice(DeviceDriver):
	def get_class(self):
		return self.CLASS
	def _send_command(self, command):
		# nop
		pass
	def set_state(self, state):
		return self._set(state)

class FakeLight(LightMixin, FakeDevice):
	pass

class FakeFan(ThreeSpeedFanMixin, FakeDevice):
	pass

# clean up the namespace
del DeviceDriver, FakeDevice, LightMixin, ThreeSpeedFanMixin
