import time
from machine import I2C, Pin
from logger import log, log_warn, log_err

# Adresses du capteur INA3221
INA3221_ADDRS = {
    0: 0x40,  # A0 pin -> GND
    1: 0x41,  # A0 pin -> VCC
    2: 0x42,  # A0 pin -> SDA
    3: 0x43,  # A0 pin -> SCL
}

# Registres du INA3221
INA3221_REG_CONF = 0x00
INA3221_REG_SHUNTV_SUM = 0x11
INA3221_REG_MANUF_ID = 0xFE
INA3221_REG_DIE_ID = 0xFF
INA3221_REG_RESET = 0x8000

# Classe INA3221
class INA3221:
    def __init__(self, scl_pin=9, sda_pin=8,addr=INA3221_ADDRS[0]):
        
        self.scl_pin = scl_pin
        self.sda_pin = sda_pin
        self.i2c = I2C(0, scl=Pin(self.scl_pin), sda=Pin(self.sda_pin), freq=100000)
        self.addr = addr
        self.shunt_res = [100, 100, 100]  # Valeur par défaut des résistances de shunt en mOhm

    # Lire un registre de 16 bits
    def _read_register(self, reg):
        self.i2c.writeto(self.addr, bytes([reg]))
        data = self.i2c.readfrom(self.addr, 2)
        return int.from_bytes(data, "big")

    # Écrire dans un registre de 16 bits
    def _write_register(self, reg, value):
        self.i2c.writeto(self.addr, bytes([reg, (value >> 8) & 0xFF, value & 0xFF]))

    def reset_i2c(self):
        """
        Réinitialise le bus I2C en cas d'erreur.
        - Débloque le bus en envoyant des impulsions sur SCL.
        - Recrée l'objet I2C.
        """
        log("Réinitialisation du bus I2C...")
        
        # Étape 1 : Débloquer le bus I2C
        scl = Pin(self.scl_pin, Pin.OUT)
        sda = Pin(self.sda_pin, Pin.OUT)
        
        # Envoyer 9 impulsions sur SCL pour débloquer un esclave coincé
        scl.value(1)
        for _ in range(9):
            scl.value(0)
            time.sleep_us(100)  # Pause de 100 µs
            scl.value(1)
            time.sleep_us(100)
        
        # S'assurer que SDA et SCL sont à l'état haut
        sda.value(1)
        scl.value(1)
        time.sleep_us(100)
        
        # Étape 2 : Recréer l'objet I2C
        try:
            self.i2c = I2C(0, scl=Pin(self.scl_pin), sda=Pin(self.sda_pin), freq=100000)
            log("Bus I2C réinitialisé")
        except Exception as e:
            log_err("Erreur lors de la réinitialisation I2C:", e)
            return False
        return True

    # Lire l'ID du fabricant (doit être 0x5449)
    def get_manuf_id(self):
        return self._read_register(INA3221_REG_MANUF_ID)

    # Lire l'ID du die (doit être 0x3220)
    def get_die_id(self):
        return self._read_register(INA3221_REG_DIE_ID)

    # Réinitialiser le capteur
    def reset(self):
        log("Reset du capteur INA3221")
        self._write_register(INA3221_REG_CONF, INA3221_REG_RESET)

    # Lire la tension de shunt pour un canal spécifique (en µV)
    def get_shunt_voltage(self, channel):
        reg = 0x01 + (channel * 2)
        return self._read_register(reg)

    # Lire la tension de bus pour un canal spécifique (en V)
    def get_bus_voltage(self, channel):
        reg = 0x02 + (channel * 2)
        return self._read_register(reg) * 0.001  # Conversion en Volts

    # Lire le courant pour un canal spécifique (en mA)
    def get_current(self, channel):
        voltage = self.get_shunt_voltage(channel)
        return voltage / self.shunt_res[channel] * 0.001 # Utiliser la loi d'Ohm (I = V/R)
