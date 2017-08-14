from restful_rfcat.drivers import *

hunter_dip_switches = {
	'bedroom': '1111',
	'office': '1101',
	'livingroom': '1011',
	'diningroom': '0111'
}
name_labels = {
	'bedroom': 'Bedroom',
	'office': 'Office',
	'livingroom': 'Living Room',
	'diningroom': 'Dining Room'
}

DEVICES = []

for name, dip in hunter_dip_switches.items():
	DEVICES.append(
		HunterCeilingFan(name=name, label=name_labels[name], dip_switch=dip)
	)
	DEVICES.append(
		HunterCeilingLight(name=name, label=name_labels[name], dip_switch=dip)
	)
