/*
 * Combined Mega hardware bring-up controller.
 *
 * Keeps the PCF8574 LCD + rotary behavior and adds:
 * - RC522 reader 1: SCK D13, MISO D12, MOSI D11, SS D10, RST D8
 * - RC522 reader 2: shared SCK/MISO/MOSI/RST, SS D9 (optional)
 * - Photoresistor: A15 / ADC15
 * - HC-SR04P ultrasonic ranger: Trig D7/PH4, Echo D24/PA2
 * - Modelcraft RS-2 servo: D6/PH3 PWM signal
 *
 * The controller probes both the supplied Uno/Nano D11-D13 wiring and the
 * Mega's native D50-D52 SPI wiring, then uses the one where reader 1 responds.
 */

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

#define SERVO_MIN_DEGREES 0
#define SERVO_MAX_DEGREES 180
#define SERVO_CENTER_DEGREES 90
#define SERVO_DEGREES_PER_ROTARY_TICK 5
#define SERVO_MIN_PULSE_US 1000
#define SERVO_MAX_PULSE_US 2000

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

static void publish_light(uint16_t raw) {
    char digits[4];
    uint8_t count = 0;
    do {
        digits[count++] = (char)('0' + (raw % 10));
        raw /= 10;
    } while (raw && count < sizeof(digits));

    uart_puts("LIGHT sensor=photoresistor_a15 raw=");
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

static uint8_t servo_angle_from_position(int16_t position) {
    int16_t angle = SERVO_CENTER_DEGREES +
        (position * SERVO_DEGREES_PER_ROTARY_TICK);
    if (angle < SERVO_MIN_DEGREES) {
        return SERVO_MIN_DEGREES;
    }
    if (angle > SERVO_MAX_DEGREES) {
        return SERVO_MAX_DEGREES;
    }
    return (uint8_t)angle;
}

static void servo_set_for_position(int16_t position) {
    const uint8_t angle = servo_angle_from_position(position);
    const uint16_t pulse_us = SERVO_MIN_PULSE_US +
        (((uint32_t)angle * (SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US)) /
         SERVO_MAX_DEGREES);
    OCR4A = pulse_us * 2;

    uart_puts("SERVO pin=D6 angle=");
    uart_put_i16(angle);
    uart_puts(" pulse_us=");
    uart_put_i16(pulse_us);
    uart_puts("\r\n");
}

static void controller_publish_position(int16_t position, bool lcd_ready) {
    publish_position(position, lcd_ready);
    servo_set_for_position(position);
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
    uart_puts(" rotary=D23,D25 light=A15 ultrasonic=D7trig,D24echo servo=D6\r\n");
    controller_publish_position(position, lcd_ready);

    for (;;) {
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
            publish_light(adc_read(15));
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

        if (++ultrasonic_timer >= 250) {
            ultrasonic_timer = 0;
            publish_distance(ultrasonic_measure_cm());
        }
        _delay_ms(1);
    }
}
