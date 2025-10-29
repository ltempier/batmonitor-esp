import network
import time

from tools import get_rtc_datetime_str, blink_led, set_led_rgba
from logger import log, log_warn, log_err
from env import env

class Wifi:
    _instance = None  # ← SINGLETON MAGIC !

    def __new__(cls, *args, **kwargs):
        """SINGLETON : Une seule instance TOUJOURS"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Singleton : __init__ ne s'exécute QU'UNE FOIS
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.wlan = network.WLAN(network.STA_IF)
            self.ap = network.WLAN(network.AP_IF)
            self.mode = None
            self.ssid = None
    
    def get_ip(self):
        if self.wlan.active() and self.wlan.isconnected():
            return self.wlan.ifconfig()[0]
        if self.ap.active():
            return self.ap.ifconfig()[0]
        return None

    def is_wlan_connect(self):
        return self.wlan.isconnected()

    def connect(self, ssid, password, timeout = 5):
        ap_active = self.ap.active()
        if ap_active:
            self.ap.active(False)
        
        if self.wlan.isconnected():
            self.wlan.disconnect()
            time.sleep(1)
        
        self.wlan.active(True)
        self.wlan.connect(str(ssid), str(password))
        
        start = time.ticks_ms()
        while not self.is_wlan_connect() and time.ticks_diff(time.ticks_ms(), start) <= timeout * 1000:
            time.sleep(0.5)
      
        is_connected = self.is_wlan_connect()
        if is_connected:
            env.set("WIFI_SSID", ssid)
            env.set("WIFI_PASSWORD", password)
            log(f"Wifi connected - ssid: {ssid}")
            
            self.mode = "STA"
            self.ssid = ssid
            
            blink_led(5, color=(0,255,255))
        else:            
            self.wlan.active(False)
            self.ap.active(ap_active)
            
            blink_led(1, color=(255,0,0))
            time.sleep(1)
                
        return is_connected
    
    def create_access_point(self, ap_ssid="ESP32_Access_Point", ap_password="12345678"):
        if self.wlan.active():
            self.wlan.active(False)

        # Activer le mode AP
        self.ap.active(True)

        # Configurer le point d'accès
        self.ap.config(essid=str(ap_ssid), password=str(ap_password), authmode=network.AUTH_WPA_WPA2_PSK)
        self.ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
        
        env.set("AP_SSID", ap_ssid)
        env.set("AP_PASSWORD", ap_password)
        log(f"Wifi create access point - ssid: {ap_ssid} pwd: {ap_password}")

        self.mode = "AP"
        self.ssid = ap_ssid
        
        blink_led(5, color=(255,255,0))
        
    def list_ssid(self):
        wlan_active = self.wlan.active()
        if not wlan_active:
            self.wlan.active(True)
            
        networks = self.wlan.scan()
        ssid_list = set()
        for network in networks:
            ssid_bytes = network[0]
            try:
                ssid = ssid_bytes.decode('utf-8') if isinstance(ssid_bytes, (bytes, bytearray)) else str(ssid_bytes)
            except Exception:
                ssid = repr(ssid_bytes)

            ssid = ssid.strip()
            if ssid:
                ssid_list.add(ssid)

        self.wlan.active(wlan_active)
        return list(ssid_list)


wifi = Wifi()

