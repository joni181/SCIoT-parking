MCU := atmega2560
F_CPU := 16000000UL
TARGET := rotary_lcd_bringup
PORT ?= /dev/ttyACM0
BAUD ?= 115200
BUILD := build

CC := avr-gcc
OBJCOPY := avr-objcopy
AVRDUDE := avrdude
CFLAGS := -mmcu=$(MCU) -DF_CPU=$(F_CPU) -Os -std=gnu11 -Wall -Wextra -Werror

.PHONY: all upload clean

all: $(BUILD)/$(TARGET).hex

$(BUILD):
	mkdir -p $@

$(BUILD)/$(TARGET).elf: $(TARGET).c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $< $@

upload: $(BUILD)/$(TARGET).hex
	$(AVRDUDE) -p m2560 -c wiring -P $(PORT) -b $(BAUD) -U flash:w:$<:i

clean:
	rm -rf $(BUILD)
