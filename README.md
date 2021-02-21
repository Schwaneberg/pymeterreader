# pymeterreader
## Summary
A flexible and easy to configure service to collect and forward readings from smart meters and other sensors.
It supports the Volkszaehler middleware and can be used as a replacement of vzlogger.
Alternatively it supports exposing measurements in the OpenMetrics format for usage with monitoring tools like Prometheus.

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

## Metrics
To enable the metrics webserver the `metrics` section has to be present in the configuration.
Metrics are generated by retrieving and parsing a Sample from a meter for every http request.
Grafana can be used to easily create [Dashboards](https://snapshot.raintank.io/dashboard/snapshot/NRGy3wSguO55lgpnz73oDNHGJCBef4iu) to visualize the Metrics stored in Prometheus.

### Reccommendations
* To prevent queuing of multiple reads configure sample caching with the `cache_interval` option.
* If a meter supplies an energy consumption counter and a power measurement the power measurement can be discarded.
  The power measurement average can instead be calculated from the difference between energy consumption datapoints.

### Prometheus Configuration Example
```
scrape_configs:
  - job_name: 'pymeterreader'
    scrape_interval: 15s
    scrape_timeout: 5s
    static_configs:
      - targets: ['localhost:8080']
    relabel_configs:
      - source_labels: [ __name__ ]
        regex: pymeterreader_power_consumption_watts
        action: drop
```