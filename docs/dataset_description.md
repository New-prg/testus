## Dataset description

The project supports local dataset import through:

```bash
python -m app.cli import-dataset --path <path>
```

Supported formats:

- `.csv`
- `.json`
- `.jsonl`

The importer accepts either flat telemetry rows or expanded records derived from Pilot-GPS-style chunk exports.

### Minimal row fields

Recommended fields for a flat dataset row:

- `timestamp` or `time` or `recorded_at`
- `value`
- `sensor_name` or `name`
- one of `sensor_id`, `fieldname`, `analytics_key`
- one of `vehicle_id`, `pilot_agent_id`, `agentid`, `imei`, `plate_number`

Optional fields:

- `speed`
- `vin`
- `vehicle_type`
- `car_type`
- `unit`

### Nested import format

The importer also supports rows shaped like a `sensor_day_chunk` record:

- `record_type = sensor_day_chunk`
- `vehicle` object
- `sensor` object
- `sensor_data` list with timestamped points

It also accepts the reduced long-form telematics layout used by the demo dataset, including fields such as:

- `vehicle_key`
- `vehicle_agentid`
- `vehiclenumber`
- `canonical_feature`
- `local_sensor_id`
- `speed_from_point`

### Import behavior

- Vehicles are upserted into `Vehicle`.
- Sensors are upserted into `VehicleSensor`.
- Readings are inserted into `SensorReading` with duplicate protection by vehicle, sensor, and timestamp.
- After import, daily `VehicleMetricWindow` and `VehicleRatingWindow` records are recalculated for the imported time span.

### Research note

Pilot-GPS is only one possible source of telemetry. In the thesis framing, the central object of study is the ML analytics pipeline over telematics data, not the external provider itself.

The default demo seed uses the reduced weekly dataset (`telematics_reduced_long.csv`) as the reproducible source of operational statistics, with `sensor_profile_canonical.json` kept beside it as the matching sensor profile sidecar.
