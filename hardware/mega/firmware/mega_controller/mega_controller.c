/*
 * Combined Mega hardware bring-up controller.
 *
 * Keeps the PCF8574 LCD + rotary behavior and adds:
 * - RC522 reader 1: SCK D13, MISO D12, MOSI D11, SS D10, RST D8
 * - RC522 reader 2: shared SCK/MISO/MOSI/RST, SS D9 (optional)
 * - Photoresistors: A15/ADC15 (buffer B1), A12/A13/A14 (P1/P2/P3)
 * - HC-SR04P ultrasonic ranger: Trig D7/PH4, Echo D24/PA2
 * - Modelcraft RS-2 servo: D6/PH3 PWM signal, commanded over serial with
 *   "GATE OPEN" / "GATE CLOSE" lines (closed on boot; not tied to the rotary)
 *
 * The controller probes both the supplied Uno/Nano D11-D13 wiring and the
 * Mega's native D50-D52 SPI wiring, then uses the one where reader 1 responds.
 *
 * Serial RX (the GATE OPEN/CLOSE command channel) is interrupt-driven, not
 * polled, so it can't be starved by uart_puts()'s busy-wait transmission of
 * the periodic LIGHT/DISTANCE/NFC/ROTARY lines - see uart_try_getc().
 */

#include <avr/interrupt.h>
#include <string.h>

#define MEGA_CONTROLLER_LIBRARY
#include "rotary_lcd_pcf8574.c"

#define NFC_READER_COUNT 2

#define RC522_COMMAND_REG 0x01
#define RC522_COM_IRQ_REG 0x04
#define RC522_ERROR_REG 0x06
#define RC522_FIFO_DATA_REG 0x09
#define RC522_FIFO_LEVEL_REG 0x0A
#define RC522_CONTROL_REG 0x0C
#define RC522_BIT_FRAMING_REG 0x0D
#define RC522_MODE_REG 0x11
#define RC522_TX_CONTROL_REG 0x14
#define RC522_TX_ASK_REG 0x15
#define RC522_RFCFG_REG 0x26
#define RC522_T_MODE_REG 0x2A
#define RC522_T_PRESCALER_REG 0x2B
#define RC522_T_RELOAD_REG_H 0x2C
#define RC522_T_RELOAD_REG_L 0x2D
#define RC522_VERSION_REG 0x37

#define RC522_PCD_IDLE 0x00
#define RC522_PCD_TRANSCEIVE 0x0C
#define RC522_PCD_SOFT_RESET 0x0F
#define RC522_PICC_REQA 0x26

/* Uno-compatible software SPI pins on ATmega2560 port B. */
#define NFC_SS_1 PB4  /* Arduino D10 */
#define NFC_MOSI PB5  /* Arduino D11 */
#define NFC_MISO PB6  /* Arduino D12 */
#define NFC_SCK PB7   /* Arduino D13 */
#define NFC_SS_2 PH6  /* Arduino D9 */
#define NFC_RST PH5   /* Arduino D8 */
#define ULTRASONIC_TRIG PH4 /* Arduino D7 */
#define ULTRASONIC_ECHO PA2 /* Arduino D24 */
#define SERVO_PIN PH3 /* Arduino D6 / Timer4 output compare A */

#define SERVO_MAX_DEGREES 180
#define SERVO_CLOSED_DEGREES 0
#define SERVO_OPEN_DEGREES 180
#define SERVO_MIN_PULSE_US 1000
#define SERVO_MAX_PULSE_US 2000

#define GATE_LINE_MAX 16

typedef struct {
    bool online;
    bool had_card;
    uint8_t uid[4];
} NfcReaderState;

static bool nfc_hardware_spi;

static void nfc_deselect_all(void) {
    PORTB |= _BV(NFC_SS_1);
    PORTH |= _BV(NFC_SS_2);
}

static void nfc_select(uint8_t reader) {
    nfc_deselect_all();
    if (reader == 0) {
        PORTB &= (uint8_t)~_BV(NFC_SS_1);
    } else {
        PORTH &= (uint8_t)~_BV(NFC_SS_2);
    }
    _delay_us(1);
}

static uint8_t nfc_spi_transfer(uint8_t value) {
    if (nfc_hardware_spi) {
        SPDR = value;
        while (!(SPSR & _BV(SPIF))) {
        }
        return SPDR;
    }

    uint8_t received = 0;
    for (uint8_t mask = 0x80; mask; mask >>= 1) {
        if (value & mask) {
            PORTB |= _BV(NFC_MOSI);
        } else {
            PORTB &= (uint8_t)~_BV(NFC_MOSI);
        }
        _delay_us(1);
        PORTB |= _BV(NFC_SCK);
        _delay_us(1);
        if (PINB & _BV(NFC_MISO)) {
            received |= mask;
        }
        PORTB &= (uint8_t)~_BV(NFC_SCK);
        _delay_us(1);
    }
    return received;
}

static void rc522_write(uint8_t reader, uint8_t reg, uint8_t value) {
    nfc_select(reader);
    nfc_spi_transfer((uint8_t)((reg << 1) & 0x7E));
    nfc_spi_transfer(value);
    nfc_deselect_all();
}

static uint8_t rc522_read(uint8_t reader, uint8_t reg) {
    nfc_select(reader);
    nfc_spi_transfer((uint8_t)(0x80 | ((reg << 1) & 0x7E)));
    const uint8_t value = nfc_spi_transfer(0x00);
    nfc_deselect_all();
    return value;
}

static void rc522_set_bits(uint8_t reader, uint8_t reg, uint8_t mask) {
    rc522_write(reader, reg, (uint8_t)(rc522_read(reader, reg) | mask));
}

static void rc522_clear_bits(uint8_t reader, uint8_t reg, uint8_t mask) {
    rc522_write(reader, reg, (uint8_t)(rc522_read(reader, reg) & (uint8_t)~mask));
}

static void nfc_reset_all(void) {
    PORTH &= (uint8_t)~_BV(NFC_RST);
    _delay_ms(50);
    PORTH |= _BV(NFC_RST);
    _delay_ms(50);
}

static void nfc_soft_spi_init(void) {
    nfc_hardware_spi = false;
    DDRB |= _BV(NFC_SS_1) | _BV(NFC_MOSI) | _BV(NFC_SCK);
    DDRB &= (uint8_t)~_BV(NFC_MISO);
    PORTB &= (uint8_t)~(_BV(NFC_MOSI) | _BV(NFC_SCK) | _BV(NFC_MISO));
    DDRH |= _BV(NFC_SS_2) | _BV(NFC_RST);
    nfc_deselect_all();
    nfc_reset_all();
}

static void nfc_hardware_spi_init(void) {
    nfc_hardware_spi = true;
    /* Mega native SPI: D50/PB3 MISO, D51/PB2 MOSI, D52/PB1 SCK. */
    DDRB |= _BV(PB0) | _BV(PB1) | _BV(PB2) | _BV(NFC_SS_1);
    DDRB &= (uint8_t)~_BV(PB3);
    PORTB |= _BV(PB0) | _BV(NFC_SS_1);
    DDRH |= _BV(NFC_SS_2) | _BV(NFC_RST);
    nfc_deselect_all();
    SPCR = _BV(SPE) | _BV(MSTR) | _BV(SPR0);
    SPSR = 0;
    nfc_reset_all();
}

static bool rc522_responds(uint8_t reader) {
    const uint8_t version = rc522_read(reader, RC522_VERSION_REG);
    return version != 0x00 && version != 0xFF;
}

static bool rc522_init(uint8_t reader) {
    rc522_write(reader, RC522_COMMAND_REG, RC522_PCD_SOFT_RESET);
    _delay_ms(50);
    const uint8_t version = rc522_read(reader, RC522_VERSION_REG);
    if (version == 0x00 || version == 0xFF) {
        return false;
    }

    rc522_write(reader, RC522_T_MODE_REG, 0x8D);
    rc522_write(reader, RC522_T_PRESCALER_REG, 0x3E);
    rc522_write(reader, RC522_T_RELOAD_REG_L, 30);
    rc522_write(reader, RC522_T_RELOAD_REG_H, 0);
    rc522_write(reader, RC522_TX_ASK_REG, 0x40);
    rc522_write(reader, RC522_MODE_REG, 0x3D);
    rc522_write(reader, RC522_RFCFG_REG, 0x70);
    rc522_set_bits(reader, RC522_TX_CONTROL_REG, 0x03);

    uart_puts("NFC reader=");
    uart_putc((char)('1' + reader));
    uart_puts(" status=ready version=0x");
    const char hex[] = "0123456789ABCDEF";
    uart_putc(hex[version >> 4]);
    uart_putc(hex[version & 0x0F]);
    uart_puts("\r\n");
    return true;
}

static bool rc522_transceive(
    uint8_t reader,
    const uint8_t *sent,
    uint8_t sent_length,
    uint8_t bit_framing,
    uint8_t *received,
    uint8_t *received_length
) {
    rc522_write(reader, RC522_COMMAND_REG, RC522_PCD_IDLE);
    rc522_write(reader, RC522_COM_IRQ_REG, 0x7F);
    rc522_set_bits(reader, RC522_FIFO_LEVEL_REG, 0x80);
    for (uint8_t index = 0; index < sent_length; ++index) {
        rc522_write(reader, RC522_FIFO_DATA_REG, sent[index]);
    }
    rc522_write(reader, RC522_BIT_FRAMING_REG, bit_framing);
    rc522_write(reader, RC522_COMMAND_REG, RC522_PCD_TRANSCEIVE);
    rc522_set_bits(reader, RC522_BIT_FRAMING_REG, 0x80);

    bool completed = false;
    for (uint16_t timeout = 500; timeout; --timeout) {
        const uint8_t irq = rc522_read(reader, RC522_COM_IRQ_REG);
        if (irq & 0x30) {
            completed = true;
            break;
        }
        if (irq & 0x01) {
            break;
        }
        _delay_us(50);
    }
    rc522_clear_bits(reader, RC522_BIT_FRAMING_REG, 0x80);
    if (!completed || (rc522_read(reader, RC522_ERROR_REG) & 0x1B)) {
        return false;
    }

    const uint8_t length = rc522_read(reader, RC522_FIFO_LEVEL_REG);
    if (length > *received_length) {
        return false;
    }
    for (uint8_t index = 0; index < length; ++index) {
        received[index] = rc522_read(reader, RC522_FIFO_DATA_REG);
    }
    *received_length = length;
    return true;
}

static bool rc522_read_uid(uint8_t reader, uint8_t uid[4]) {
    const uint8_t request[] = {RC522_PICC_REQA};
    uint8_t atqa[2];
    uint8_t atqa_length = sizeof(atqa);
    if (!rc522_transceive(reader, request, sizeof(request), 0x07, atqa, &atqa_length)) {
        return false;
    }

    const uint8_t anticollision[] = {0x93, 0x20};
    uint8_t response[5];
    uint8_t response_length = sizeof(response);
    if (!rc522_transceive(reader, anticollision, sizeof(anticollision), 0x00, response, &response_length)) {
        return false;
    }
    if (response_length != sizeof(response)) {
        return false;
    }
    if ((uint8_t)(response[0] ^ response[1] ^ response[2] ^ response[3]) != response[4]) {
        return false;
    }
    for (uint8_t index = 0; index < 4; ++index) {
        uid[index] = response[index];
    }
    return true;
}

static bool uid_changed(const uint8_t current[4], const uint8_t previous[4]) {
    for (uint8_t index = 0; index < 4; ++index) {
        if (current[index] != previous[index]) {
            return true;
        }
    }
    return false;
}

static void publish_uid(uint8_t reader, const uint8_t uid[4]) {
    const char hex[] = "0123456789ABCDEF";
    uart_puts("NFC reader=");
    uart_putc((char)('1' + reader));
    uart_puts(" uid=");
    for (uint8_t index = 0; index < 4; ++index) {
        uart_putc(hex[uid[index] >> 4]);
        uart_putc(hex[uid[index] & 0x0F]);
    }
    uart_puts("\r\n");
}

static void adc_init(void) {
    ADCSRA = _BV(ADEN) | _BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0);
}

static uint16_t adc_read(uint8_t channel) {
    ADMUX = _BV(REFS0) | (channel & 0x07);
    ADCSRB = (channel & 0x08) ? _BV(MUX5) : 0;
    ADCSRA |= _BV(ADSC);
    while (ADCSRA & _BV(ADSC)) {
    }
    return ADC;
}

/* One photoresistor per buffer/parking spot: A15=buffer B1, A12-A14=P1-P3. */
#define LIGHT_SENSOR_COUNT 4
static const uint8_t light_channels[LIGHT_SENSOR_COUNT] = {15, 12, 13, 14};
static const char *const light_labels[LIGHT_SENSOR_COUNT] = {
    "photoresistor_a15",
    "photoresistor_a12",
    "photoresistor_a13",
    "photoresistor_a14",
};

static void publish_light(const char *label, uint16_t raw) {
    char digits[4];
    uint8_t count = 0;
    do {
        digits[count++] = (char)('0' + (raw % 10));
        raw /= 10;
    } while (raw && count < sizeof(digits));

    uart_puts("LIGHT sensor=");
    uart_puts(label);
    uart_puts(" raw=");
    while (count) {
        uart_putc(digits[--count]);
    }
    uart_puts("\r\n");
}

static void ultrasonic_init(void) {
    DDRH |= _BV(ULTRASONIC_TRIG);
    PORTH &= (uint8_t)~_BV(ULTRASONIC_TRIG);
    DDRA &= (uint8_t)~_BV(ULTRASONIC_ECHO);
    /* Timer1 at F_CPU/8 = 2MHz: one tick is 0.5us. */
    TCCR1A = 0;
    TCCR1B = _BV(CS11);
}

/* HC-SR04P has separate Trig/Echo lines: emit a 10us trigger pulse on Trig, then time the Echo pulse width. */
static int16_t ultrasonic_measure_cm(void) {
    PORTH &= (uint8_t)~_BV(ULTRASONIC_TRIG);
    _delay_us(2);
    PORTH |= _BV(ULTRASONIC_TRIG);
    _delay_us(12);
    PORTH &= (uint8_t)~_BV(ULTRASONIC_TRIG);

    TCNT1 = 0;
    while (!(PINA & _BV(ULTRASONIC_ECHO))) {
        if (TCNT1 >= 60000) { /* 30ms: no echo / out of range */
            return -1;
        }
    }

    TCNT1 = 0;
    while (PINA & _BV(ULTRASONIC_ECHO)) {
        if (TCNT1 >= 60000) {
            return -1;
        }
    }
    return (int16_t)(TCNT1 / 116U);
}

static void publish_distance(int16_t distance_cm) {
    uart_puts("DISTANCE sensor=hc_sr04p_d7_d24 ");
    if (distance_cm < 0) {
        uart_puts("status=out-of-range");
    } else {
        uart_puts("cm=");
        uart_put_i16(distance_cm);
    }
    uart_puts("\r\n");
}

/*
 * D6 is OC4A on the Mega.  Timer4 produces one 1-2ms pulse every 20ms,
 * which is the conventional control signal for an analogue hobby servo.
 */
static void servo_init(void) {
    DDRH |= _BV(SERVO_PIN);
    TCCR4A = _BV(COM4A1) | _BV(WGM41);
    TCCR4B = _BV(WGM43) | _BV(WGM42) | _BV(CS41);
    ICR4 = 39999; /* 20ms at 2MHz (F_CPU / 8). */
    OCR4A = SERVO_MIN_PULSE_US * 2;
}

/*
 * The gate servo is commanded, not tied to the rotary encoder: the Pi sends
 * "GATE OPEN" / "GATE CLOSE" lines over serial (see gate_poll_uart below),
 * and this is the only thing that moves it.
 */
static void gate_set(bool open) {
    const uint8_t angle = open ? SERVO_OPEN_DEGREES : SERVO_CLOSED_DEGREES;
    const uint16_t pulse_us = SERVO_MIN_PULSE_US +
        (((uint32_t)angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) /
         SERVO_MAX_DEGREES);
    OCR4A = pulse_us * 2;

    uart_puts("GATE state=");
    uart_puts(open ? "open" : "closed");
    uart_puts(" angle=");
    uart_put_i16(angle);
    uart_puts(" pulse_us=");
    uart_put_i16(pulse_us);
    uart_puts("\r\n");
}

/* Incoming bytes are captured by ISR, not polled: uart_puts() busy-waits per
 * byte while transmitting (LIGHT/DISTANCE/NFC/ROTARY lines), and during those
 * multi-millisecond windows nothing would otherwise be reading UDR0 - the
 * single-byte hardware RX register has no FIFO, so a GATE OPEN/CLOSE byte
 * arriving mid-transmission would silently overwrite/be lost (UART overrun).
 * The interrupt preempts that busy-wait immediately regardless of what the
 * main loop is doing. */
#define UART_RX_BUFFER_SIZE 32
static volatile char uart_rx_buffer[UART_RX_BUFFER_SIZE];
static volatile uint8_t uart_rx_head = 0;
static volatile uint8_t uart_rx_tail = 0;

ISR(USART0_RX_vect) {
    const uint8_t next_head = (uint8_t)((uart_rx_head + 1) % UART_RX_BUFFER_SIZE);
    if (next_head != uart_rx_tail) {
        uart_rx_buffer[uart_rx_head] = (char)UDR0;
        uart_rx_head = next_head;
    } else {
        (void)UDR0; /* buffer full: drop the byte, but still clear RXC0 */
    }
}

static bool uart_try_getc(char *out) {
    if (uart_rx_head == uart_rx_tail) {
        return false;
    }
    *out = uart_rx_buffer[uart_rx_tail];
    uart_rx_tail = (uint8_t)((uart_rx_tail + 1) % UART_RX_BUFFER_SIZE);
    return true;
}

/* Calibration escape hatch: set the servo to any angle directly, without
 * going through the open/closed vocabulary, so a physical closed/open
 * position can be tuned live over serial instead of by re-flashing per guess.
 */
#define SERVO_ANGLE_PREFIX "SERVO ANGLE="
#define SERVO_ANGLE_PREFIX_LEN 12

static bool parse_uint8(const char *text, uint8_t *out) {
    if (*text == '\0') {
        return false;
    }
    uint16_t value = 0;
    for (; *text; ++text) {
        if (*text < '0' || *text > '9') {
            return false;
        }
        value = (uint16_t)(value * 10 + (uint8_t)(*text - '0'));
        if (value > SERVO_MAX_DEGREES) {
            return false;
        }
    }
    *out = (uint8_t)value;
    return true;
}

/* Mirrors DurationDial's mapping (parking/sensors/drivers.py) so the LCD
 * shows the same duration the rest of the system actually uses - keep these
 * in sync if either side's defaults change. */
#define DIAL_DEFAULT_MINUTES 30
#define DIAL_MINUTES_PER_TICK 5
#define DIAL_MIN_MINUTES 5
#define DIAL_MAX_MINUTES 180

static int16_t dial_minutes_from_ticks(int16_t ticks) {
    int16_t minutes = (int16_t)(DIAL_DEFAULT_MINUTES + ticks * DIAL_MINUTES_PER_TICK);
    if (minutes < DIAL_MIN_MINUTES) {
        minutes = DIAL_MIN_MINUTES;
    }
    if (minutes > DIAL_MAX_MINUTES) {
        minutes = DIAL_MAX_MINUTES;
    }
    return minutes;
}

static void lcd_render_minutes(int16_t position) {
    uint16_t minutes = (uint16_t)dial_minutes_from_ticks(position);
    char digits[4];
    uint8_t count = 0;
    do {
        digits[count++] = (char)('0' + (minutes % 10));
        minutes /= 10;
    } while (minutes && count < sizeof(digits));

    char line[8];
    uint8_t index = 0;
    while (count) {
        line[index++] = digits[--count];
    }
    line[index++] = ' ';
    line[index++] = 'm';
    line[index++] = 'i';
    line[index++] = 'n';
    line[index] = '\0';

    lcd_line(0x80, "Duration");
    lcd_line(0xC0, line);
}

/* Same LED-toggle-and-emit-ROTARY-line behavior as the shared
 * publish_position(), but renders the mapped duration instead of calling its
 * lcd_render(ticks) - one LCD render per tick, not two. */
static void controller_publish_position(int16_t position, bool lcd_ready) {
    PORTA ^= _BV(LED_BIT);
    if (lcd_ready) {
        lcd_render_minutes(position);
    }
    uart_puts("ROTARY ticks=");
    uart_put_i16(position);
    uart_puts("\r\n");
}

static void servo_set_raw_angle(uint8_t angle) {
    const uint16_t pulse_us = SERVO_MIN_PULSE_US +
        (((uint32_t)angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) /
         SERVO_MAX_DEGREES);
    OCR4A = pulse_us * 2;

    uart_puts("SERVO angle=");
    uart_put_i16(angle);
    uart_puts(" pulse_us=");
    uart_put_i16(pulse_us);
    uart_puts("\r\n");
}

static void gate_handle_line(const char *line) {
    if (strcmp(line, "GATE OPEN") == 0) {
        gate_set(true);
    } else if (strcmp(line, "GATE CLOSE") == 0) {
        gate_set(false);
    } else if (strncmp(line, SERVO_ANGLE_PREFIX, SERVO_ANGLE_PREFIX_LEN) == 0) {
        uint8_t angle;
        if (parse_uint8(line + SERVO_ANGLE_PREFIX_LEN, &angle)) {
            servo_set_raw_angle(angle);
        }
    }
}

/* Non-blocking: drains whatever the Pi has sent so far, one line at a time. */
static void gate_poll_uart(void) {
    static char line[GATE_LINE_MAX];
    static uint8_t length = 0;

    char c;
    while (uart_try_getc(&c)) {
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            line[length] = '\0';
            gate_handle_line(line);
            length = 0;
            continue;
        }
        if (length < GATE_LINE_MAX - 1) {
            line[length++] = c;
        } else {
            length = 0; /* overflow: drop the line and resync */
        }
    }
}

int main(void) {
    static const int8_t transition[16] = {
        0, -1, 1, 0,
        1, 0, 0, -1,
        -1, 0, 0, 1,
        0, 1, -1, 0,
    };
    NfcReaderState readers[NFC_READER_COUNT] = {0};

    uart_init();
    /* Also receive, for "GATE OPEN"/"GATE CLOSE" commands - RXCIE0 makes
     * reception interrupt-driven so it can't be starved by uart_puts()'s
     * busy-wait transmission of the periodic sensor lines. */
    UCSR0B |= _BV(RXEN0) | _BV(RXCIE0);
    sei();
    DDRA |= _BV(LED_BIT);
    DDRA &= (uint8_t)~(_BV(ROTARY_CLK) | _BV(ROTARY_DT));
    PORTA |= _BV(ROTARY_CLK) | _BV(ROTARY_DT);
    twi_init();
    const bool lcd_ready = lcd_init();
    adc_init();
    ultrasonic_init();
    servo_init();
    nfc_soft_spi_init();
    if (!rc522_responds(0)) {
        nfc_hardware_spi_init();
    }
    uart_puts("NFC bus=");
    uart_puts(nfc_hardware_spi ? "mega-native D50,D51,D52\r\n" : "software D11,D12,D13\r\n");
    for (uint8_t reader = 0; reader < NFC_READER_COUNT; ++reader) {
        readers[reader].online = rc522_init(reader);
        if (!readers[reader].online) {
            uart_puts("NFC reader=");
            uart_putc((char)('1' + reader));
            uart_puts(" status=not-detected\r\n");
        }
    }

    int16_t position = 0;
    int8_t accumulator = 0;
    uint8_t previous = rotary_sample();
    uint16_t light_timer = 0;
    uint16_t nfc_timer = 0;
    uint16_t ultrasonic_timer = 0;

    uart_puts("READY controller=mega lcd=");
    uart_puts(lcd_ready ? "pcf8574-ready" : "not-found");
    uart_puts(" rotary=D23,D25 light=A12,A13,A14,A15 ultrasonic=D7trig,D24echo servo=D6(GATE cmd)\r\n");
    controller_publish_position(position, lcd_ready);
    gate_set(false); /* closed on boot */

    for (;;) {
        gate_poll_uart();

        const uint8_t current = rotary_sample();
        if (current != previous) {
            accumulator += transition[(previous << 2) | current];
            previous = current;
            if (accumulator >= 4) {
                ++position;
                accumulator = 0;
                controller_publish_position(position, lcd_ready);
            } else if (accumulator <= -4) {
                --position;
                accumulator = 0;
                controller_publish_position(position, lcd_ready);
            }
        }

        if (++light_timer >= 500) {
            light_timer = 0;
            for (uint8_t sensor = 0; sensor < LIGHT_SENSOR_COUNT; ++sensor) {
                publish_light(light_labels[sensor], adc_read(light_channels[sensor]));
            }
        }

        if (++nfc_timer >= 100) {
            nfc_timer = 0;
            for (uint8_t reader = 0; reader < NFC_READER_COUNT; ++reader) {
                if (!readers[reader].online) {
                    continue;
                }
                uint8_t uid[4];
                if (rc522_read_uid(reader, uid)) {
                    if (!readers[reader].had_card || uid_changed(uid, readers[reader].uid)) {
                        publish_uid(reader, uid);
                        for (uint8_t index = 0; index < 4; ++index) {
                            readers[reader].uid[index] = uid[index];
                        }
                    }
                    readers[reader].had_card = true;
                } else {
                    readers[reader].had_card = false;
                }
            }
        }

        /* The main loop's baseline period is ~1ms (the trailing _delay_ms(1)
         * below), so 1000 iterations is roughly one reading per second. */
        if (++ultrasonic_timer >= 1000) {
            ultrasonic_timer = 0;
            publish_distance(ultrasonic_measure_cm());
        }
        _delay_ms(1);
    }
}
