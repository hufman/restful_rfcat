import re
import threading
import time
import rflib
from rflib import RfCat, MOD_ASK_OOK

import logging
logger = logging.getLogger(__name__)

class Radio(object):
	power = 90
	# use the same lock for all instances of the Radio class
	lock = threading.Lock()
	device = None
	claimed = None	# which instance has claimed the radio
	mode = None	# whether we are in send/receive mode

	@staticmethod
	def _create_device():
		if Radio.device is None:
			Radio.device = rflib.RfCat()

class OOKRadio(Radio):
	def __init__(self, frequency, baudrate, bandwidth=100000):
		self.frequency = frequency
		self.baudrate = baudrate
		self.bandwidth = bandwidth

	def _prepare_device(self):
		Radio._create_device()
		Radio.device.setMdmModulation(rflib.MOD_ASK_OOK)
		Radio.device.setFreq(self.frequency)
		Radio.device.setMdmSyncMode(0)
		Radio.device.setMdmDRate(self.baudrate)
		Radio.device.setMdmChanSpc(100000)
		Radio.device.setMdmChanBW(self.bandwidth)
		Radio.device.setChannel(0)
		Radio.device.setPower(self.power)

	def _release_device(self):
		logger.info("Releasing radio")
		if Radio.mode is not None:
			logger.info("Turning off radio mode %s" % (Radio.mode,))
			release = getattr(self, '_release_%s' % (Radio.mode,))
			release()
		Radio.mode = None
		self.device.setModeIDLE()

	def reset_device(self):
		try:
			self._release_device()
		except:
			pass
		Radio.claimed = None

	def _change_mode(self, mode):
		if Radio.claimed == self and \
		   Radio.mode == mode:
			# already in the correct mode
			return
		if Radio.claimed != self:
			if Radio.claimed is not None:
				logger.info("Claiming radio from other config")
				Radio.claimed._release_device()
			self._prepare_device()
			Radio.claimed = self
		if Radio.mode is not None and Radio.mode != mode:
			logger.info("Switching radio mode from %s" % (Radio.mode,))
			release = getattr(self, '_release_%s' % (Radio.mode,))
			release()
		Radio.mode = mode
		if mode is not None:
			logger.info("Setting radio mode to %s" % (mode,))
			prepare = getattr(self, '_prepare_to_%s' % (mode,))
			prepare()
		#self.device.printRadioConfig()

	def _prepare_to_send(self):
		time.sleep(0.05)

	def _release_send(self):
		time.sleep(0.05)

	def _prepare_to_receive(self):
		time.sleep(0.05)
		Radio.device.setModeRX()
		Radio.device.lowball(0)

	def _release_receive(self):
		if hasattr(Radio.device, '_last_radiocfg'):
			Radio.device.lowballRestore()
		time.sleep(0.05)
		self.device.setModeIDLE()

	def send(self, bytes, repeat=25):
		with Radio.lock:
			try:
				self._change_mode('send')
				Radio.device.RFxmit(bytes, repeat=repeat)
			except rflib.chipcon_usb.ChipconUsbTimeoutException:
				logger.warning("USB Timeout")
				self.reset_device()
				raise Exception("RFCat failure")

	def receive(self):
		with Radio.lock:
			self._change_mode('receive')
			try:
				(data, time) = Radio.device.RFrecv()
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
		if bits.startswith('0b'):
			bits = bits[2:]
		packets = re.split('0{%i,}' % (gap,), bits)
		return packets

class OOKRadioChannelHack(OOKRadio):
	def __init__(self, frequency, baudrate, mhz_adjustment, bandwidth=100000):
		self.frequency = frequency
		self.baudrate = baudrate
		self.mhz_adjustment = mhz_adjustment
		self.bandwidth = bandwidth

	def _prepare_device(self):
		Radio._create_device()
		Radio.device.setMdmModulation(rflib.MOD_ASK_OOK)
		Radio.device.setFreq(self.frequency)
		Radio.device.setMdmSyncMode(0)
		Radio.device.setMdmDRate(self.baudrate)
		Radio.device.setMdmChanSpc(100000)
		Radio.device.setChannel(int(self.mhz_adjustment * 10))
		Radio.device.setMdmChanBW(self.bandwidth)
		Radio.device.setPower(self.power)

