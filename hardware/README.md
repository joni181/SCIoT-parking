# Hardware bring-up layer

This folder owns **physical wiring, controller firmware, and bring-up tools**.  It is
deliberately separate from `parking/`: the application layer should later consume
stable, typed events and commands rather than opening serial ports or knowing GPIO
numbers.

## Layout

- `pinmap.yaml` is the single source of truth for physical connections.
- `mega/firmware/rotary_lcd_bringup/` contains a small, standalone Mega firmware
  for proving the rotary encoder and LCD work together.
- `pi/bringup/` contains non-production Pi utilities.  They confirm the serial
  protocol before a future `parking.sensors` adapter publishes MQTT events.

When a device is added, first update `pinmap.yaml`, add a focused bring-up program
here, and only then add its application-facing driver under `parking/sensors` or
`parking/actuators`.

## Current rotary + LCD bring-up

The Mega firmware reads the incremental rotary encoder, writes its signed position
to the Grove LCD, and emits serial lines such as `ROTARY position=3`.  The current
encoder has no usable mechanical press, so its `SW` lead is deliberately not an
application input.  The firmware toggles the LED on D22 whenever the displayed
position changes.

```bash
cd ~/SCIoT-parking/hardware/mega/firmware/rotary_lcd_bringup
make TARGET=rotary_lcd_pcf8574
make upload TARGET=rotary_lcd_pcf8574 PORT=/dev/ttyACM0
python3 ../../../pi/bringup/monitor_rotary_lcd.py
```

`make upload` deliberately replaces the current Mega firmware.  Keep the backup
created under `/home/group4/arduino-backups/` before using it.

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
