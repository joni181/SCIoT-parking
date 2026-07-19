/*
 * Standalone servo test: isolates the Modelcraft RS-2 on D6 from the rest of
 * mega_controller.c - no NFC, ultrasonic, LCD, or rotary code at all. Type an
 * angle 0-180 and Enter over serial, or "s" to sweep the full range.
 *
 * Build/upload/reflash like any other target here:
 *   make TARGET=servo_test
 *   make upload TARGET=servo_test PORT=/dev/ttyACM0
 */
#define F_CPU 16000000UL
#define BAUD 9600UL

#include <avr/io.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <util/delay.h>

#define SERVO_PIN PH3 /* Arduino D6 / Timer4 OC4A */
#define SERVO_MIN_PULSE_US 1000
#define SERVO_MAX_PULSE_US 2000
#define SERVO_MAX_DEGREES 180
#define LINE_MAX 8

static void uart_init(void) {
    const uint16_t ubrr = (F_CPU / (16UL * BAUD)) - 1;
    UBRR0H = (uint8_t)(ubrr >> 8);
    UBRR0L = (uint8_t)ubrr;
    UCSR0A = 0;
    UCSR0B = _BV(TXEN0) | _BV(RXEN0);
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

static void uart_put_u8(uint8_t value) {
    char digits[3];
    uint8_t count = 0;
    do {
        digits[count++] = (char)('0' + (value % 10));
        value /= 10;
    } while (value);
    while (count) {
        uart_putc(digits[--count]);
    }
}

static bool uart_try_getc(char *out) {
    if (!(UCSR0A & _BV(RXC0))) {
        return false;
    }
    *out = (char)UDR0;
    return true;
}

/* D6 is OC4A on the Mega. Timer4 produces one 1-2ms pulse every 20ms. */
static void servo_init(void) {
    DDRH |= _BV(SERVO_PIN);
    TCCR4A = _BV(COM4A1) | _BV(WGM41);
    TCCR4B = _BV(WGM43) | _BV(WGM42) | _BV(CS41);
    ICR4 = 39999; /* 20ms at 2MHz (F_CPU / 8) */
    OCR4A = SERVO_MIN_PULSE_US * 2;
}

static void servo_set_angle(uint8_t angle) {
    if (angle > SERVO_MAX_DEGREES) {
        angle = SERVO_MAX_DEGREES;
    }
    const uint16_t pulse_us = SERVO_MIN_PULSE_US +
        (((uint32_t)angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) / SERVO_MAX_DEGREES);
    OCR4A = pulse_us * 2;

    uart_puts("angle=");
    uart_put_u8(angle);
    uart_puts("\r\n");
}

static bool parse_u8(const char *text, uint8_t *out) {
    if (*text == '\0') {
        return false;
    }
    uint16_t value = 0;
    for (; *text; ++text) {
        if (*text < '0' || *text > '9') {
            return false;
        }
        value = (uint16_t)(value * 10 + (uint8_t)(*text - '0'));
        if (value > 255) {
            return false;
        }
    }
    *out = (uint8_t)value;
    return true;
}

static void handle_line(const char *line) {
    if (strcmp(line, "s") == 0) {
        uart_puts("sweeping\r\n");
        for (uint8_t angle = 0; angle <= 180; angle += 5) {
            servo_set_angle(angle);
            _delay_ms(200);
        }
        for (uint8_t angle = 180;; angle -= 5) {
            servo_set_angle(angle);
            _delay_ms(200);
            if (angle == 0) {
                break;
            }
        }
        return;
    }
    uint8_t angle;
    if (parse_u8(line, &angle) && angle <= SERVO_MAX_DEGREES) {
        servo_set_angle(angle);
    } else {
        uart_puts("enter 0-180 or s\r\n");
    }
}

int main(void) {
    uart_init();
    servo_init();
    servo_set_angle(0);
    uart_puts("READY servo_test pin=D6 - type 0-180 or s, then Enter\r\n");

    char line[LINE_MAX];
    uint8_t length = 0;
    for (;;) {
        char c;
        while (uart_try_getc(&c)) {
            if (c == '\r') {
                continue;
            }
            if (c == '\n') {
                line[length] = '\0';
                handle_line(line);
                length = 0;
                continue;
            }
            if (length < LINE_MAX - 1) {
                line[length++] = c;
            } else {
                length = 0;
            }
        }
    }
}
