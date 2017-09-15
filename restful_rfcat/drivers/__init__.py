# All of the available drivers to use in config files
from restful_rfcat.drivers.hunter import HunterCeilingFan, HunterCeilingLight, HunterCeilingEavesdropper
from restful_rfcat.drivers.hamptonbay import HamptonCeilingFan, HamptonCeilingLight
from restful_rfcat.drivers.feit import FeitElectricLights

# example implementation
from restful_rfcat.drivers._utils import DeviceDriver
class FakeDevice(DeviceDriver):
	def get_class(self):
		return self.CLASS
	def set_state(self, state):
		return self._set(state)

class FakeLight(FakeDevice):
	CLASS = "lights"
	def get_available_states(self):
		return ["OFF", "ON"]

class FakeFan(FakeDevice):
	CLASS = "fans"
	def get_available_states(self):
		return ["OFF", "LOW", "MED", "HI"]

# clean up the namespace
del DeviceDriver, FakeDevice
