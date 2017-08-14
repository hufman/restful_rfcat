import re
import threading
import time
import rflib
from rflib import RfCat, MOD_ASK_OOK

import logging
logger = logging.getLogger(__name__)

class Radio(object):
	# use the same lock for all instances of the Radio class
	lock = threading.Lock()
	power = 50
	setup = None
	mode = None

	def _create_device(self):
		if not hasattr(self, 'device'):
			self.device = rflib.RfCat()

class OOKRadio(Radio):
	def __init__(self, frequency, baudrate):
		self.frequency = frequency
		self.baudrate = baudrate

	def _prepare_device(self, keylen):
		self._create_device()
		self.device.setMdmModulation(rflib.MOD_ASK_OOK)
		self.device.setFreq(self.frequency)
		self.device.setMdmSyncMode(0)
		self.device.setMdmDRate(self.baudrate)
		self.device.setMdmChanSpc(100000)
		self.device.setChannel(0)
		self.device.setPower(self.power)

	def _release_device(self):
		self.device.setModeIDLE()

	def r_eset_device(self):
		self._change_mode(None, None)
		self.setup = None
		self.device.RESET()

	def _change_mode(self, mode, keylen):
		if self.setup == self and \
		   self.mode == mode:
			return
		if self.setup != self:
			if self.setup is not None:
				self._release_device()
			self._prepare_device(keylen)
			self.setup = self
		if keylen is not None:
			self.device.makePktFLEN(keylen)
		if self.mode is not None and self.mode != mode:
			release = getattr(self, '_release_%s' % (self.mode,))
			release()
		self.mode = mode
		if self.mode is not None:
			prepare = getattr(self, '_prepare_to_%s' % (self.mode,))
			prepare(keylen)
		#self.device.printRadioConfig()

	def _prepare_to_send(self, keylen):
		time.sleep(0.05)

	def _release_send(self):
		time.sleep(0.05)

	def _prepare_to_receive(self, keylen):
		time.sleep(0.05)
		self.device.setModeRX()
		self.device.lowball(1)

	def _release_receive(self):
		self.device.lowballRestore()
		time.sleep(0.05)
		self._release_device()

	def send(self, bytes, repeat=25):
		with self.lock:
			self._change_mode('send', len(bytes))
			self.device.RFxmit(bytes, repeat=repeat)

	def receive(self):
		with self.lock:
			self._change_mode('receive', 50)
			try:
				(data, time) = self.device.RFrecv()
			except rflib.chipcon_usb.ChipconUsbTimeoutException:
				logger.warning("USB Timeout")
				self.reset_device()
				return (None, None)
		return (data, time)

	def receive_packets(self, gap=20):
		(data, time) = self.receive()
		if data is None:
			return None
		hex = data.encode('hex')
		bits = bin(int(hex,16))
		packets = re.split('0{%i,}' % (gap,), bits)
		return packets

class OOKRadioChannelHack(OOKRadio):
	def __init__(self, frequency, baudrate, mhz_adjustment):
		self.frequency = frequency
		self.baudrate = baudrate
		self.mhz_adjustment = mhz_adjustment

	def _prepare_device(self, keylen):
		self._create_device()
		self.device.setMdmModulation(rflib.MOD_ASK_OOK)
		self.device.setFreq(self.frequency)
		self.device.makePktFLEN(keylen)
		self.device.setMdmSyncMode(0)
		self.device.setMdmDRate(self.baudrate)
		self.device.setMdmChanSpc(100000)
		self.device.setChannel(self.mhz_adjustment * 10)
		self.device.setPower(self.power)

