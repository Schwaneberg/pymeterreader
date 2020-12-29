# pymeterreader
## Summary
A flexible and easy to configure service to collect and forward readings from smart meters and other sensors.
It supports the Volkszaehler middleware and can be used as a replacement of vzlogger.

## Supported Devices
- Meters with SML protocol, tested with EMH electricity meters
- Meters with plain serial protocols such as Landis+Gyr ULTRAHEAT T550 (UH50…)
- Bosch BME280 sensor for air humidity, temperature and pressure

## Installation
Install using pip on Raspberry Pi:
```
sudo python3 -m pip install pymeterreader
sudo pymeterreader-wizard
```
Use the wizard to test the connection to the Volkszähler middleware and map meters to channels,
if the wizard is able to detect them.
The wizard uses default baudrates and interfaces nodes only.
Please try to manually configure your meters according to the example yaml file, if the wizard fails to detect them.
Be sure to call the menu items 'Save current mapping' and 'Register PyMeterReader as systemd service' before you close the wizard.
```
sudo systemctl enable pymeterreader
```
Check the generated configuration file at `/etc/pymeterreader.yaml`.
Note that all channels are configured with a default interval of `30m`.
The interval can be modified individually for all channels.
```
sudo systemctl start pymeterreader
```
You can follow the log using
```
journalctl -f
```
