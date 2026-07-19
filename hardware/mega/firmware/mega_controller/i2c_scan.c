/* Temporary native-I2C scanner for the Arduino Mega ADK (SDA D20, SCL D21). */

#define F_CPU 16000000UL
#define BAUD 9600UL
#define TWI_FREQUENCY 100000UL

#include <avr/io.h>
#include <stdbool.h>
#include <stdint.h>
#include <util/delay.h>

static void uart_init(void) {
    const uint16_t ubrr = (F_CPU / (16UL * BAUD)) - 1;
    UBRR0H = (uint8_t)(ubrr >> 8);
    UBRR0L = (uint8_t)ubrr;
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

static void uart_put_hex(uint8_t value) {
    const char hex[] = "0123456789ABCDEF";
    uart_putc(hex[value >> 4]);
    uart_putc(hex[value & 0x0F]);
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

static void twi_init(void) {
    TWSR = 0;
    TWBR = (uint8_t)((F_CPU / TWI_FREQUENCY - 16UL) / 2UL);
    TWCR = _BV(TWEN);
}

static bool twi_probe(uint8_t address) {
    TWCR = _BV(TWINT) | _BV(TWSTA) | _BV(TWEN);
    if (!twi_wait()) {
        return false;
    }
    const uint8_t start_status = TWSR & 0xF8;
    if (start_status != 0x08 && start_status != 0x10) {
        twi_stop();
        return false;
    }

    TWDR = (uint8_t)(address << 1);
    TWCR = _BV(TWINT) | _BV(TWEN);
    if (!twi_wait()) {
        twi_stop();
        return false;
    }
    const bool acknowledged = (TWSR & 0xF8) == 0x18;
    twi_stop();
    return acknowledged;
}

int main(void) {
    uart_init();
    twi_init();
    uart_puts("I2C_SCAN begin\r\n");

    for (uint8_t address = 0x03; address < 0x78; ++address) {
        if (twi_probe(address)) {
            uart_puts("I2C address=0x");
            uart_put_hex(address);
            uart_puts("\r\n");
        }
    }
    uart_puts("I2C_SCAN done\r\n");

    for (;;) {
        _delay_ms(1000);
    }
}
