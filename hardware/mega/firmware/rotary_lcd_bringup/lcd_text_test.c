/* Minimal, standalone Grove LCD RGB Backlight v4.0 text test.
 *
 * Current prototype wiring on the Mega ADK:
 *   LCD SDA -> A0/PF0, LCD SCL -> A1/PF1, VCC -> 5V, GND -> GND.
 *
 * This deliberately uses a slow software-I2C clock to isolate the LCD from
 * rotary-encoder handling.  It prints two fixed lines and never redraws them.
 */

#define F_CPU 16000000UL
#define BAUD 9600UL

#include <avr/io.h>
#include <stdbool.h>
#include <stdint.h>
#include <util/delay.h>

#define LED_BIT PA0
#define LCD_SDA PF0
#define LCD_SCL PF1
#define LCD_TEXT_ADDR 0x3E
#define LCD_RGB_ADDR 0x62

static void uart_init(void) {
    const uint16_t ubrr = (F_CPU / (16UL * BAUD)) - 1;
    UBRR0H = (uint8_t)(ubrr >> 8);
    UBRR0L = (uint8_t)ubrr;
    UCSR0B = _BV(TXEN0);
    UCSR0C = _BV(UCSZ01) | _BV(UCSZ00);
}

static void uart_puts(const char *text) {
    while (*text) {
        while (!(UCSR0A & _BV(UDRE0))) {
        }
        UDR0 = (uint8_t)*text++;
    }
}

static inline void sda_low(void) {
    PORTF &= (uint8_t)~_BV(LCD_SDA);
    DDRF |= _BV(LCD_SDA);
}

static inline void sda_release(void) {
    PORTF &= (uint8_t)~_BV(LCD_SDA);
    DDRF &= (uint8_t)~_BV(LCD_SDA);
}

static inline void scl_low(void) {
    PORTF &= (uint8_t)~_BV(LCD_SCL);
    DDRF |= _BV(LCD_SCL);
}

static inline void scl_release(void) {
    PORTF &= (uint8_t)~_BV(LCD_SCL);
    DDRF &= (uint8_t)~_BV(LCD_SCL);
}

static inline bool sda_read(void) {
    return (PINF & _BV(LCD_SDA)) != 0;
}

static inline void i2c_delay(void) {
    _delay_us(30);
}

static void i2c_start(void) {
    sda_release();
    scl_release();
    i2c_delay();
    sda_low();
    i2c_delay();
    scl_low();
}

static void i2c_stop(void) {
    sda_low();
    i2c_delay();
    scl_release();
    i2c_delay();
    sda_release();
    i2c_delay();
}

static bool i2c_write(uint8_t value) {
    for (uint8_t mask = 0x80; mask; mask >>= 1) {
        if (value & mask) {
            sda_release();
        } else {
            sda_low();
        }
        i2c_delay();
        scl_release();
        i2c_delay();
        scl_low();
    }

    sda_release();
    i2c_delay();
    scl_release();
    i2c_delay();
    const bool acknowledged = !sda_read();
    scl_low();
    return acknowledged;
}

static bool lcd_write(uint8_t address, uint8_t control, uint8_t value) {
    i2c_start();
    const bool address_ack = i2c_write((uint8_t)(address << 1));
    const bool control_ack = i2c_write(control);
    const bool value_ack = i2c_write(value);
    i2c_stop();
    return address_ack && control_ack && value_ack;
}

static bool lcd_ping(uint8_t address) {
    i2c_start();
    const bool acknowledged = i2c_write((uint8_t)(address << 1));
    i2c_stop();
    return acknowledged;
}

static void lcd_line(uint8_t cursor_command, const char *line) {
    lcd_write(LCD_TEXT_ADDR, 0x80, cursor_command);
    for (uint8_t index = 0; index < 16; ++index) {
        const char value = line[index] ? line[index] : ' ';
        lcd_write(LCD_TEXT_ADDR, 0x40, (uint8_t)value);
    }
}

int main(void) {
    uart_init();
    DDRA |= _BV(LED_BIT);
    sda_release();
    scl_release();

    const bool text_ready = lcd_ping(LCD_TEXT_ADDR);
    const bool rgb_ready = lcd_ping(LCD_RGB_ADDR);
    if (text_ready && rgb_ready) {
        /* Same command sequence as the known-good GrovePi driver. */
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
        lcd_line(0x80, "SCIoT LCD v4");
        lcd_line(0xC0, "TEXT TEST: OK");
        uart_puts("LCD_TEST text=ack rgb=ack\r\n");
    } else {
        uart_puts("LCD_TEST device-not-found\r\n");
    }

    for (;;) {
        PORTA ^= _BV(LED_BIT);
        _delay_ms(500);
    }
}
