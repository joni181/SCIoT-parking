/*
 * Standalone hardware bring-up firmware for an Arduino Mega ADK R3.
 *
 * Rotary encoder: D23/PA1 (CLK), D25/PA3 (DT)
 * Grove LCD v4:   D20/PD1 (SDA), D21/PD0 (SCL), native Mega I2C
 * Debug LED:      D22/PA0
 *
 * The encoder is incremental, so it has no absolute mechanical angle.  The
 * display therefore shows its relative position in ticks; a future application
 * can map those ticks to minutes after it defines a calibration/reference point.
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
#define LCD_TEXT_ADDR 0x3E
#define LCD_RGB_ADDR 0x62

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

static bool lcd_write(uint8_t address, uint8_t control, uint8_t value) {
    const bool started = twi_start(address);
    const bool control_written = started && twi_write(control);
    const bool value_written = control_written && twi_write(value);
    const bool stopped = twi_stop();
    return value_written && stopped;
}

static bool lcd_ping(uint8_t address) {
    const bool acknowledged = twi_start(address);
    const bool stopped = twi_stop();
    return acknowledged && stopped;
}

static bool lcd_init(void) {
    const bool text_present = lcd_ping(LCD_TEXT_ADDR);
    const bool rgb_present = lcd_ping(LCD_RGB_ADDR);
    if (!(text_present && rgb_present)) {
        return false;
    }

    lcd_write(LCD_RGB_ADDR, 0x00, 0x00);
    lcd_write(LCD_RGB_ADDR, 0x01, 0x00);
    lcd_write(LCD_RGB_ADDR, 0x08, 0xAA);
    lcd_write(LCD_RGB_ADDR, 0x04, 0x00);
    lcd_write(LCD_RGB_ADDR, 0x03, 0x80);
    lcd_write(LCD_RGB_ADDR, 0x02, 0x40);

    lcd_write(LCD_TEXT_ADDR, 0x80, 0x01);
    _delay_ms(50);
    lcd_write(LCD_TEXT_ADDR, 0x80, 0x0C);
    lcd_write(LCD_TEXT_ADDR, 0x80, 0x28);
    return true;
}

static void lcd_line(uint8_t cursor_command, const char *line) {
    lcd_write(LCD_TEXT_ADDR, 0x80, cursor_command);
    bool ended = false;
    for (uint8_t index = 0; index < 16; ++index) {
        if (!ended && line[index] == '\0') {
            ended = true;
        }
        lcd_write(LCD_TEXT_ADDR, 0x40, (uint8_t)(ended ? ' ' : line[index]));
    }
}

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
    uart_puts(lcd_ready ? "LCD=native-i2c-ready\r\n" : "LCD=not-found\r\n");
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
