"""MFRC522 RFID reader library for Raspberry Pi (SPI, Python 3)."""

import RPi.GPIO as GPIO
import spidev

# Status codes
MI_OK = 0
MI_NOTAGERR = 1
MI_ERR = 2

# RC522 registers
_REG_COMMAND = 0x01
_REG_COM_IE = 0x02
_REG_COM_IRQ = 0x04
_REG_ERROR = 0x06
_REG_FIFO_DATA = 0x09
_REG_FIFO_LEVEL = 0x0A
_REG_CONTROL = 0x0C
_REG_BIT_FRAMING = 0x0D
_REG_MODE = 0x11
_REG_TX_CONTROL = 0x14
_REG_TX_ASK = 0x15
_REG_CRC_RESULT_H = 0x21
_REG_CRC_RESULT_L = 0x22
_REG_T_MODE = 0x2A
_REG_T_PRESCALER = 0x2B
_REG_T_RELOAD_H = 0x2C
_REG_T_RELOAD_L = 0x2D

# RC522 commands
_CMD_IDLE = 0x00
_CMD_AUTHENT = 0x0E
_CMD_TRANSCEIVE = 0x0C
_CMD_RESET = 0x0F
_CMD_CALC_CRC = 0x03

# PICC (card) commands
PICC_REQIDL = 0x26
PICC_AUTHENT1A = 0x60
PICC_AUTHENT1B = 0x61
PICC_READ = 0x30
_PICC_ANTICOLL = 0x93
_PICC_SELECT = 0x93
_PICC_HALT = 0x50

# Default SPI and GPIO pins (matching tutorial wiring)
_DEFAULT_RST_PIN = 25  # GPIO25, physical pin 22
_DEFAULT_SPI_BUS = 0
_DEFAULT_SPI_DEVICE = 0  # CE0 = GPIO8, physical pin 24


class MFRC522:
    def __init__(self, rst_pin=_DEFAULT_RST_PIN, spi_bus=_DEFAULT_SPI_BUS, spi_device=_DEFAULT_SPI_DEVICE):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(rst_pin, GPIO.OUT)
        GPIO.output(rst_pin, GPIO.HIGH)

        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_device)
        self._spi.max_speed_hz = 1000000

        self._reset()
        self._write(_REG_T_MODE, 0x8D)
        self._write(_REG_T_PRESCALER, 0x3E)
        self._write(_REG_T_RELOAD_H, 0x00)
        self._write(_REG_T_RELOAD_L, 0x1E)
        self._write(_REG_TX_ASK, 0x40)
        self._write(_REG_MODE, 0x3D)
        self._antenna_on()

    def __del__(self):
        try:
            self._spi.close()
            GPIO.cleanup()
        except Exception:
            pass

    def _write(self, reg, val):
        self._spi.xfer2([(reg << 1) & 0x7E, val])

    def _read(self, reg):
        return self._spi.xfer2([((reg << 1) & 0x7E) | 0x80, 0])[1]

    def _set_bits(self, reg, mask):
        self._write(reg, self._read(reg) | mask)

    def _clear_bits(self, reg, mask):
        self._write(reg, self._read(reg) & (~mask))

    def _reset(self):
        self._write(_REG_COMMAND, _CMD_RESET)

    def _antenna_on(self):
        if not (self._read(_REG_TX_CONTROL) & 0x03):
            self._set_bits(_REG_TX_CONTROL, 0x03)

    def _calc_crc(self, data):
        self._clear_bits(_REG_COM_IRQ, 0x04)
        self._set_bits(_REG_FIFO_LEVEL, 0x80)
        for byte in data:
            self._write(_REG_FIFO_DATA, byte)
        self._write(_REG_COMMAND, _CMD_CALC_CRC)

        for _ in range(5000):
            if self._read(0x05) & 0x04:  # DivIrqReg CRCIRq
                break

        return [self._read(_REG_CRC_RESULT_L), self._read(_REG_CRC_RESULT_H)]

    def _transceive(self, data):
        self._write(_REG_COM_IE, 0x77)
        self._clear_bits(_REG_COM_IRQ, 0x80)
        self._set_bits(_REG_FIFO_LEVEL, 0x80)
        self._write(_REG_COMMAND, _CMD_IDLE)

        for byte in data:
            self._write(_REG_FIFO_DATA, byte)

        self._write(_REG_COMMAND, _CMD_TRANSCEIVE)
        self._set_bits(_REG_BIT_FRAMING, 0x80)

        i = 2000
        while True:
            irq = self._read(_REG_COM_IRQ)
            i -= 1
            if not (i != 0 and not (irq & 0x01) and not (irq & 0x30)):
                break

        self._clear_bits(_REG_BIT_FRAMING, 0x80)

        if i == 0 or (self._read(_REG_ERROR) & 0x1B):
            return MI_ERR, [], 0

        if irq & 0x30:
            status = MI_OK
        else:
            status = MI_ERR

        n = self._read(_REG_FIFO_LEVEL)
        last_bits = self._read(_REG_CONTROL) & 0x07
        bit_len = (n - 1) * 8 + last_bits if last_bits else n * 8

        back_data = [self._read(_REG_FIFO_DATA) for _ in range(n)]
        return status, back_data, bit_len

    def request(self, req_mode=PICC_REQIDL):
        """Scan for cards. Returns (MI_OK, tag_type) or (MI_ERR/MI_NOTAGERR, [])."""
        self._write(_REG_BIT_FRAMING, 0x07)
        status, back_data, _ = self._transceive([req_mode])
        if status != MI_OK or len(back_data) != 2:
            return MI_NOTAGERR, []
        return MI_OK, back_data

    def anticoll(self):
        """Get UID of card in field. Returns (status, uid_bytes)."""
        self._write(_REG_BIT_FRAMING, 0x00)
        status, back_data, _ = self._transceive([_PICC_ANTICOLL, 0x20])
        if status == MI_OK and len(back_data) == 5:
            checksum = 0
            for b in back_data[:4]:
                checksum ^= b
            if checksum != back_data[4]:
                return MI_ERR, []
        return status, back_data

    def select_tag(self, uid):
        """Select a tag by UID. Returns (status, sak_byte)."""
        buf = [_PICC_SELECT, 0x70] + uid[:5]
        crc = self._calc_crc(buf)
        buf += crc
        status, back_data, _ = self._transceive(buf)
        if status == MI_OK and len(back_data) == 3:
            return MI_OK, back_data[0]
        return MI_ERR, 0

    def auth(self, auth_mode, block_addr, sector_key, uid):
        """Authenticate a sector. auth_mode: PICC_AUTHENT1A or PICC_AUTHENT1B."""
        buf = [auth_mode, block_addr] + sector_key[:6] + uid[:4]
        self._write(_REG_COMMAND, _CMD_IDLE)
        for byte in buf:
            self._write(_REG_FIFO_DATA, byte)
        self._write(_REG_COMMAND, _CMD_AUTHENT)

        i = 2000
        while not (self._read(_REG_COM_IRQ) & 0x10) and i > 0:
            i -= 1

        if self._read(0x08) & 0x08:  # Status2Reg MFCrypto1On
            return MI_OK
        return MI_ERR

    def stop_crypto(self):
        """Stop crypto after an authenticated session."""
        self._clear_bits(0x08, 0x08)  # Status2Reg MFCrypto1On

    def read_block(self, block_addr):
        """Read 16 bytes from a block. Returns (status, data_bytes)."""
        buf = [PICC_READ, block_addr]
        buf += self._calc_crc(buf)
        status, back_data, _ = self._transceive(buf)
        if status == MI_OK and len(back_data) == 16:
            return MI_OK, back_data
        return MI_ERR, []

    def uid_to_str(self, uid):
        """Format UID bytes as a colon-separated hex string."""
        return ":".join(f"{b:02X}" for b in uid[:4])
