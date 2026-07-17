# Reference

A trimmed fixture copy of the TODS spec's "TODS-Specific File Definitions"
section, used by `tests/test_spec_watch.py`. Presence cells and conditional
phrases preserve the upstream wording so the fixture exercises the same
parsing boundary as the live spec; unrelated description prose is shortened.

## TODS-Specific File Definitions

### `run_events.txt`

Primary Key: (`service_id`, `run_id`, `event_sequence`)

| **Field Name** | **Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| `service_id` | ID referencing `calendar.service_id` | Required | Identifies a set of dates when the run is scheduled to take place. |
| `run_id` | ID | Required | A run is uniquely determined by a `service_id`, `run_id` pair. |
| `event_sequence` | Non-negative integer | Required | The order of this event within a run. |
| `piece_id` | ID | Optional | Identifies the piece within the run that the event takes place. |
| `block_id` | ID referencing `trips.block_id` | Optional | Identifies the block to which the run event belongs. |
| `job_type` | Text | Optional | The type of job that the employee is doing. |
| `event_type` | Text | Required | The type of event that the employee is doing. |
| `trip_id` | ID referencing `trips.trip_id` | Optional | If this run event corresponds to working on a trip, identifies that trip. |
| `start_location` | ID referencing `stops.stop_id` | Required | Identifies where the employee starts working this event. |
| `start_time` | Time | Required | Identifies the time when the employee starts working this event. |
| `start_mid_trip` | Enum | Optional | `0` (or blank) - not mid-trip or unknown.<br />`1` - starts mid-trip.<br />`2` - does not start mid-trip. |
| `end_location` | ID referencing `stops.stop_id` | Required | Identifies where the employee stops working this event. |
| `end_time` | Time | Required | Identifies the time when the employee stops working this event. |
| `end_mid_trip` | Enum | Optional | `0` (or blank) - not mid-trip or unknown.<br />`1` - ends mid-trip.<br />`2` - does not end mid-trip. |

### `employee_run_dates.txt`

Primary Key: `*`

| **Field Name** | **Type** | **Required** | **Description** |
| --- | --- | --- | --- |
| `date` | Date | Required | Service date. |
| `service_id` | ID referencing `run_events.txt` | Required | Part of the Run ID. |
| `run_id` | ID referencing `run_events.txt` | Required | The run that's added to this employee's schedule. |
| `employee_id` | ID | Required | References an agency's external systems. |

### `vehicles.txt`

Primary Key: `vehicle_id`

| Field Name | Type | Required | Description |
|---|---|---|---|
| `vehicle_id` | ID, primary key | Required | Defines an ID for a vehicle. |
| `vehicle_label` | Text | Optional | Free text label for a vehicle. |
| `license_plate` | Text | Optional | License number or global identifier for the vehicle. |

### `vehicle_assignments.txt`

Primary Key: `(date, block_id, service_id)`

| Field Name | Type | Required | Description |
|---|---|---|---|
| `date` | Date | Required | |
| `service_id` | ID referencing `calendar.service_id` | Optional | Required if `block_id`s are repeated between different `service_id`s. |
| `block_id` | ID referencing `trips.block_id` | Required | Identifies the block. |
| `vehicle_id` | ID referencing `vehicles.vehicle_id` | Required | Refers to a specific vehicle in the transit fleet. |
