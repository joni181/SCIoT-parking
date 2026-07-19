/*
 * Mega ADK rotary encoder + replacement I2C LCD bring-up firmware.
 *
 * Rotary encoder: D23/PA1 (CLK), D25/PA3 (DT)
 * LCD:            D20/PD1 (SDA), D21/PD0 (SCL), address 0x27
 * LCD controller: PCF8574 I2C backpack + HD44780-compatible character LCD
 * Debug LED:      D22/PA0
 */

#define F_CPU 16000000UL
#define BAUD 9600UL
#define TWI_FREQUENCY 100000UL

#include <avr/io.h>
#include <stdbool.h>
#include <stdint.h>
#include <util/delay.h>

#define LED_BIT PA0
#define ROTARY_CLK PA1
#define ROTARY_DT PA3

#define LCD_I2C_ADDR 0x27
#define LCD_RS 0x01
#define LCD_ENABLE 0x04
#define LCD_BACKLIGHT 0x08

static void uart_init(void) {
    const uint16_t ubrr = (F_CPU / (16UL * BAUD)) - 1;
    UBRR0H = (uint8_t)(ubrr >> 8);
    UBRR0L = (uint8_t)ubrr;
    UCSR0A = 0;
    UCSR0B = _BV(TXEN0);
    UCSR0C = _BV(UCSZ01) | _BV(UCSZ00);
}

static void uart_putc(char c) {
    while (!(UCSR0A & _BV(UDRE0))) {
    }
    UDR0 = (uint8_t)c;
}

static void uart_puts(const char *text) {
    while (*text) {
        uart_putc(*text++);
    }
}

static void uart_put_i16(int16_t value) {
    uint16_t magnitude;
    char digits[5];
    uint8_t count = 0;

    if (value < 0) {
        uart_putc('-');
        magnitude = (uint16_t)(-value);
    } else {
        magnitude = (uint16_t)value;
    }
    do {
        digits[count++] = (char)('0' + (magnitude % 10));
        magnitude /= 10;
    } while (magnitude && count < sizeof(digits));
    while (count) {
        uart_putc(digits[--count]);
    }
}

static bool twi_wait(void) {
    uint16_t timeout = 60000;
    while (!(TWCR & _BV(TWINT))) {
        if (--timeout == 0) {
            return false;
        }
    }
    return true;
}

static void twi_init(void) {
    TWSR = 0;
    TWBR = (uint8_t)((F_CPU / TWI_FREQUENCY - 16UL) / 2UL);
    TWCR = _BV(TWEN);
}

static bool twi_stop(void) {
    TWCR = _BV(TWINT) | _BV(TWEN) | _BV(TWSTO);
    uint16_t timeout = 60000;
    while (TWCR & _BV(TWSTO)) {
        if (--timeout == 0) {
            return false;
        }
    }
    return true;
}

static bool twi_start(uint8_t address) {
    TWCR = _BV(TWINT) | _BV(TWSTA) | _BV(TWEN);
    if (!twi_wait()) {
        return false;
    }
    const uint8_t start_status = TWSR & 0xF8;
    if (start_status != 0x08 && start_status != 0x10) {
        return false;
    }

    TWDR = (uint8_t)(address << 1);
    TWCR = _BV(TWINT) | _BV(TWEN);
    if (!twi_wait()) {
        return false;
    }
    return (TWSR & 0xF8) == 0x18;
}

static bool twi_write(uint8_t value) {
    TWDR = value;
    TWCR = _BV(TWINT) | _BV(TWEN);
    if (!twi_wait()) {
        return false;
    }
    return (TWSR & 0xF8) == 0x28;
}

static bool pcf8574_write(uint8_t value) {
    const bool started = twi_start(LCD_I2C_ADDR);
    const bool written = started && twi_write(value);
    const bool stopped = twi_stop();
    return written && stopped;
}

static bool lcd_ping(void) {
    const bool acknowledged = twi_start(LCD_I2C_ADDR);
    const bool stopped = twi_stop();
    return acknowledged && stopped;
}

static bool lcd_write4(uint8_t nibble, bool rs) {
    uint8_t data = (uint8_t)(nibble & 0xF0) | LCD_BACKLIGHT;
    if (rs) {
        data |= LCD_RS;
    }
    return pcf8574_write(data) && pcf8574_write(data | LCD_ENABLE) && pcf8574_write(data);
}

static bool lcd_send(uint8_t value, bool rs) {
    const bool upper = lcd_write4(value & 0xF0, rs);
    const bool lower = upper && lcd_write4((uint8_t)(value << 4), rs);
    _delay_us(50);
    return lower;
}

static bool lcd_command(uint8_t command) {
    const bool sent = lcd_send(command, false);
    if (command == 0x01 || command == 0x02) {
        _delay_ms(2);
    }
    return sent;
}

static bool lcd_data(uint8_t value) {
    return lcd_send(value, true);
}

static bool lcd_init(void) {
    if (!lcd_ping()) {
        return false;
    }

    _delay_ms(50);
    bool ok = lcd_write4(0x30, false);
    _delay_ms(5);
    ok = ok && lcd_write4(0x30, false);
    _delay_us(150);
    ok = ok && lcd_write4(0x30, false);
    ok = ok && lcd_write4(0x20, false);
    ok = ok && lcd_command(0x28);  /* 4-bit, 2-line, 5x8 font */
    ok = ok && lcd_command(0x0C);  /* display on, cursor off */
    ok = ok && lcd_command(0x06);  /* increment cursor */
    ok = ok && lcd_command(0x01);  /* clear */
    return ok;
}

static void lcd_line(uint8_t cursor_command, const char *line) {
    lcd_command(cursor_command);
    for (uint8_t index = 0; index < 16; ++index) {
        const char value = line[index] ? line[index] : ' ';
        lcd_data((uint8_t)value);
    }
}

#ifndef MEGA_CONTROLLER_LIBRARY
static void lcd_render(int16_t position) {
    char line2[] = "Ticks: +0000";
    uint16_t magnitude = (position < 0) ? (uint16_t)(-position) : (uint16_t)position;

    line2[7] = (position < 0) ? '-' : '+';
    line2[11] = (char)('0' + (magnitude % 10));
    magnitude /= 10;
    line2[10] = (char)('0' + (magnitude % 10));
    magnitude /= 10;
    line2[9] = (char)('0' + (magnitude % 10));
    magnitude /= 10;
    line2[8] = (char)('0' + (magnitude % 10));

    lcd_line(0x80, "Rotary angle");
    lcd_line(0xC0, line2);
}
#endif

static uint8_t rotary_sample(void) {
    uint8_t state = 0;
    if (PINA & _BV(ROTARY_CLK)) {
        state |= 0x01;
    }
    if (PINA & _BV(ROTARY_DT)) {
        state |= 0x02;
    }
    return state;
}

#ifndef MEGA_CONTROLLER_LIBRARY
static void publish_position(int16_t position, bool lcd_ready) {
    PORTA ^= _BV(LED_BIT);
    if (lcd_ready) {
        lcd_render(position);
    }
    uart_puts("ROTARY ticks=");
    uart_put_i16(position);
    uart_puts("\r\n");
}

int main(void) {
    static const int8_t transition[16] = {
        0, -1, 1, 0,
        1, 0, 0, -1,
        -1, 0, 0, 1,
        0, 1, -1, 0,
    };

    uart_init();
    DDRA |= _BV(LED_BIT);
    DDRA &= (uint8_t)~(_BV(ROTARY_CLK) | _BV(ROTARY_DT));
    PORTA |= _BV(ROTARY_CLK) | _BV(ROTARY_DT);
    twi_init();

    const bool lcd_ready = lcd_init();
    int16_t position = 0;
    int8_t accumulator = 0;
    uint8_t previous = rotary_sample();

    uart_puts("READY controller=mega_adk rotary=D23,D25 ");
    uart_puts(lcd_ready ? "LCD=pcf8574-ready\r\n" : "LCD=not-found\r\n");
    publish_position(position, lcd_ready);

    for (;;) {
        const uint8_t current = rotary_sample();
        if (current != previous) {
            accumulator += transition[(previous << 2) | current];
            previous = current;
            if (accumulator >= 4) {
                ++position;
                accumulator = 0;
                publish_position(position, lcd_ready);
            } else if (accumulator <= -4) {
                --position;
                accumulator = 0;
                publish_position(position, lcd_ready);
            }
        }
        _delay_ms(1);
    }
}
#endif
