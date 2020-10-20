# pymeterreader
## Summary
A flexible and easy to configure service to collect and forward readings from smart meters and other sensors.
It supports the Volkszaehler middleware and can be used as a replacement of vzlogger.

## Supported Devices
- Meters with SML protocol, tested with EMH electricity meters
- Meters with plain serial protocols such as Landis+Gyr ULTRAHEAT T550 (UH50…)
- Bosch BME280 sensor for air humidity, temperature and pressure

## Installation
[WIP] Install using pip on Raspberry Pi:
```
sudo python3 -m pip install pymeterreader
sudo systemctl enable pymeterreader
```
Configure /etc/pymeterreader.yaml
```
sudo systemctl start pymeterreader
```
You can follow the log using
```
journalctl -f
```
