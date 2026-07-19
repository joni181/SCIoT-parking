# Hardware bring-up layer

This folder owns **physical wiring, controller firmware, and bring-up tools**.  It is
deliberately separate from `parking/`: the application layer should later consume
stable, typed events and commands rather than opening serial ports or knowing GPIO
numbers.

## Layout

- `pinmap.yaml` is the single source of truth for physical connections.
- `mega/firmware/mega_controller/` contains the Mega firmware: `mega_controller.c`
  (the real, combined controller - rotary, LCD, NFC, ultrasonic, servo) plus
  standalone bring-up/test sketches (`servo_test.c`, `i2c_scan.c`, etc.) built
  with the same Makefile.
- `pi/bringup/` contains non-production Pi utilities.  They confirm the serial
  protocol before a future `parking.sensors` adapter publishes MQTT events.

When a device is added, first update `pinmap.yaml`, add a focused bring-up program
here, and only then add its application-facing driver under `parking/sensors` or
`parking/actuators`.

## Pull and run the latest changes

Do this on both the Pi (firmware + `apps/pi_node.py`) and the laptop
(`apps/laptop_node.py`) whenever the repo has moved:

```bash
git checkout feature/hardware-compatibility
git pull origin feature/hardware-compatibility
```

**On the Pi**, if `hardware/mega/firmware/mega_controller/mega_controller.c`
changed, reflash the Mega before running anything against it:

```bash
cd hardware/mega/firmware/mega_controller
make TARGET=mega_controller
make upload TARGET=mega_controller PORT=/dev/ttyACM0
```

Then run the node that changed:

```bash
pip install -r requirements/pi.txt         # only if requirements changed
PARKING_SENSORS=hardware python apps/pi_node.py                                # default: stable by-id path
PARKING_MEGA_PORT=/dev/ttyACM1 PARKING_SENSORS=hardware python apps/pi_node.py  # override the port
```

`MegaLink` defaults to the Mega's stable `/dev/serial/by-id/...` path (keyed to
its USB serial number), so it keeps working across reflashes/replugs even as
the `/dev/ttyACM<N>` number changes. Set `PARKING_MEGA_PORT` only if that
default doesn't resolve correctly (different board, udev quirk, etc.) - check
`ls -la /dev/ttyACM*` for the actual device.

**On the laptop**, in two terminals:

```bash
pip install -r requirements/laptop.txt     # only if requirements changed
python deploy/broker.py                    # 1) keep running
python apps/laptop_node.py                 # 2) dashboard at http://127.0.0.1:8050
```

See the root [README.md](../README.md#getting-started) for the full
first-time setup (config, no-hardware dry run, tests).

## Current rotary + LCD bring-up

The Mega firmware reads the incremental rotary encoder, writes its signed position
to the Grove LCD, and emits serial lines such as `ROTARY position=3`.  The current
encoder has no usable mechanical press, so its `SW` lead is deliberately not an
application input.  The firmware toggles the LED on D22 whenever the displayed
position changes.

```bash
cd ~/SCIoT-parking/hardware/mega/firmware/mega_controller
make TARGET=rotary_lcd_pcf8574
make upload TARGET=rotary_lcd_pcf8574 PORT=/dev/ttyACM0
python3 ../../../pi/bringup/monitor_rotary_lcd.py
```

`make upload` deliberately replaces the current Mega firmware.  Keep the backup
created under `/home/group4/arduino-backups/` before using it.

## Current Mega wiring

| Device | Mega connection | Notes |
| --- | --- | --- |
| Pi link | USB (`/dev/ttyACM0`) | Firmware + serial events |
| Status LED | D22 | Lot-full indicator: `LED ON`/`LED OFF` over serial, off by default. Was a rotary-tick heartbeat before this |
| Rotary encoder | CLK D23, DT D25, 5V, GND | D27/SW is unused on the current no-click encoder |
| LCD (`0x27`) | SDA D20, SCL D21, 5V, GND | PCF8574/HD44780-compatible display |
| RC522 reader 1 | SCK D52, MISO D50, MOSI D51, SS D10, RST D8, 3.3V, GND | IRQ unused; level-shift Mega outputs to 3.3V |
| RC522 reader 2 | Shared SPI/RST; SS D9, 3.3V, GND | Optional; not currently connected |
| Photoresistors | A15 (B1), A12 (P1), A13 (P2), A14 (P3) | Same LDR + 10kΩ divider per spot; each calibrates independently |
| HC-SR04P ultrasonic ranger | Trig D7, Echo D24, 5V, GND | Separate trigger and echo signals |
| Modelcraft RS-2 servo | Signal D6 | Power from a separate regulated 4.8-6V supply; join its GND to Mega GND. Commanded over serial (`GATE OPEN`/`GATE CLOSE`), closed by default |

### LCD wiring note

The active replacement display is detected at I2C address `0x27` and uses a
PCF8574 I2C backpack with an HD44780-compatible character LCD.  It is wired to
the Mega's native I2C bus: `SDA -> D20`, `SCL -> D21`, plus 5V and GND.  The
firmware for it is `rotary_lcd_pcf8574.c`; the previous Grove RGB v4 firmware is
kept separately as a legacy example.

## Future Pi integration boundary

The future serial adapter should open the stable path under `/dev/serial/by-id/`,
parse the `READY`, `ROTARY`, and `BUTTON` lines, and translate them into the
existing application messages.  It should not live in the Mega firmware, and the
firmware must not contain MQTT configuration.  That makes additional Mega pins,
GrovePi devices, and Pi-native SPI/I2C devices plug-and-play additions.

`parking/mega_link.py`'s `MegaLink` is that adapter: it owns the one Mega serial
port and fans each line out to every registered listener, since distance
readings, NFC scans, light readings, and (as a write) gate commands all share
the same connection. `parking/sensors/drivers.py`'s `DistanceSensor`,
`NfcReader`, and `OccupancySensor` listen on it and republish `DistanceEvent`
/ `NfcScanEvent` / `OccupancyEvent`; `parking/actuators/drivers.py`'s
`GateServo` writes `GATE OPEN` / `GATE CLOSE` to it. The remaining drivers in
those modules (motion, duration dial, buffer LED, vehicle move) still need
the same treatment.

## NFC + photoresistor controller

`mega_controller.c` combines the active LCD/rotary behavior with two RC522
reader slots and four photoresistors (A15/A12/A13/A14, one per buffer/parking
spot). It emits the following serial contract:

```text
NFC reader=1 uid=DEADBEEF
LIGHT sensor=photoresistor_a15 raw=512
LIGHT sensor=photoresistor_a12 raw=340
```

Build it with `make TARGET=mega_controller`.  Reader 1 uses SS D10; reader 2 uses
SS D9 and is optional. RST is shared on D8. The controller probes both the supplied
Uno/Nano wiring (D11/D12/D13) and the Mega's native SPI wiring (D51 MOSI, D50 MISO,
D52 SCK), then selects the bus where reader 1 responds.

The RC522 is a 3.3V device.  Give it 3.3V power and use 5V-to-3.3V level shifting
on Mega outputs MOSI, SCK, SS, and RST before uploading/running the controller.

Each reader reports a raw 0-1023 ADC value.  A bare photoresistor must be wired
as a voltage divider: `5V -> LDR -> A<pin> -> 10kΩ resistor -> GND`; otherwise
the pin floats and the output has no useful meaning.

To pick `parking.sensors.OccupancySensor`'s threshold for a given spot, run
`hardware/pi/bringup/test_photoresistor_threshold.py --sensor <label>` and
watch the raw value (plus running min/max/midpoint) while covering/uncovering
that spot - each sensor's threshold is calibrated independently:

```bash
python3 hardware/pi/bringup/test_photoresistor_threshold.py --sensor photoresistor_a15  # B1
python3 hardware/pi/bringup/test_photoresistor_threshold.py --sensor photoresistor_a12  # P1
```

All four sensors read low when covered and high when empty; each has its own
calibrated default threshold baked into `apps/pi_node.py`'s
`DEFAULT_LIGHT_THRESHOLDS` (also recorded per-sensor in `pinmap.yaml`):

| Spot | Covered | Empty | Threshold |
|---|---|---|---|
| B1 (A15) | ~300 | ~860 | 600 |
| P1 (A12) | ~0-5 | ~105-112 | 55 |
| P2 (A13) | ~284-305 | ~780-787 | 535 |
| P3 (A14) | ~58-67 | ~633-659 | 360 |

P1's whole range is much narrower than the others - watch it for noise/false
positives. Override per spot, or all of them, if a gap turns out different
later or ambient light shifts things:

```bash
PARKING_LIGHT_THRESHOLD_P1=430 PARKING_SENSORS=hardware python apps/pi_node.py  # just P1
PARKING_LIGHT_THRESHOLD=650 PARKING_SENSORS=hardware python apps/pi_node.py     # every spot
```

## Duration dial

`mega_controller.c` still emits `ROTARY ticks=<n>` on every detent (unchanged
from the plain rotary+LCD bring-up target), but the LCD now shows the mapped
duration instead of the raw tick count - `Duration` / `NN min` - matching
what `parking.sensors.DurationDial` actually derives from those ticks on the
Pi side (`default_minutes=30`, `minutes_per_tick=-5`, clamped 5-180 -
negative because the physical rotation direction is reversed from what the
raw quadrature decode produces). The mapping is duplicated in both places
(`DIAL_*` constants in `mega_controller.c`, the same-named constructor args
in `apps/pi_node.py`) - keep them in sync if either changes, since nothing
enforces that automatically.

## Status LED (lot-full indicator)

D22's external LED, previously the rotary-tick heartbeat, is now commanded
directly: `LED ON` / `LED OFF` over serial, off by default on boot. The Mega
replies with a confirmation line the same way the gate does:

```text
LED ON
LED state=on

LED OFF
LED state=off
```

`parking.dispatching.LotFullIndicator` runs on the Pi (not the laptop, unlike
most control logic) and watches `OccupancyEvent` for the configured parking
spots - it's deliberately Pi-local end to end (`OccupancySensor` already
publishes locally, and `StatusLed` writes to the same local `MegaLink`) so
the LED keeps working even if the broker/laptop is briefly unreachable. It
publishes `LotFullCommand(full=True)` only when every parking spot becomes
occupied, and `full=False` the moment any one frees up - not on every
reading, so it doesn't flood the bus. `parking.actuators.StatusLed` turns
that into the serial command.

## Servo behavior and power

`mega_controller.c` also drives the Modelcraft RS-2 on D6, commanded over serial
rather than by the rotary encoder. The Pi sends a text line and the Mega replies
with the angle it applied:

```text
GATE OPEN
GATE state=open angle=180 pulse_us=2000

GATE CLOSE
GATE state=closed angle=0 pulse_us=1000
```

The gate is closed (0 degrees) on boot and stays there until a `GATE OPEN` /
`GATE CLOSE` line arrives. `parking.actuators.GateServo` sends these lines over
the shared `MegaLink` (see `parking/mega_link.py`) whenever a `GateCommand`
message is published on the bus.

There is no gate motion sensor in the current hardware, so closing isn't
reactive to "a vehicle passed through." `parking.dispatching.GateSafetyController`
closes the gate 5 seconds after it opens, unless the ultrasonic ranger reports
something within 8cm - it then waits for a clear reading before closing. Both
values are constructor parameters (`close_delay_s`, `clear_distance_cm`) if they
need retuning.

For manual calibration, `mega_controller.c` also accepts `SERVO ANGLE=<0-180>`
to drive the servo to an arbitrary angle directly, without going through the
open/closed vocabulary - useful for finding the right closed/open angles live
over serial before baking them into `SERVO_CLOSED_DEGREES`/`SERVO_OPEN_DEGREES`.

The D6 signal is generated by Timer4 as a 1-2 ms pulse every 20 ms.  **Do not power
the servo from the Mega's 5V USB rail.** Connect its power leads to a separate,
regulated 4.8-6V supply and connect that supply's ground to Mega GND.  Connect the
servo signal lead to D6.  Check the servo connector labels before wiring rather
than relying only on wire colours.

## Ultrasonic ranger (HC-SR04P)

`mega_controller.c` polls the HC-SR04P about once a second (every 1000
iterations of the ~1ms main loop) and emits its reading as a serial line, e.g.:

```text
DISTANCE sensor=hc_sr04p_d7_d24 cm=42
DISTANCE sensor=hc_sr04p_d7_d24 status=out-of-range
```

Unlike the earlier Grove Ultrasonic Ranger, the HC-SR04P has separate Trig and
Echo pins rather than one shared SIG line: Trig is driven on D7, Echo is read on
D24. Expected range is 2-350cm; readings outside that (or a missing echo) report
`status=out-of-range`.
