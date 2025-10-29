import ntptime
import time

from tools import get_rtc_datetime_str, blink_led, set_led_rgba
from logger import log, log_warn, log_err
from env import env
from wifi import wifi

SSID = env.get("WIFI_SSID")
PASSWORD = env.get("WIFI_PASSWORD")

try:
    is_connect = wifi.connect(SSID, PASSWORD)
except Exception as e:
    is_connect = False
    log_err(f"Erreur connexion Wi-Fi : {e}")

if not is_connect:
    # Creation AP (mode AP)
    
    ap_ssid = env.get("AP_SSID", "ESP32_Access_Point")
    ap_password = env.get("AP_PASSWORD", "12345678")
    
    try:
        wifi.create_access_point(ap_ssid, ap_password)
    except Exception as e:
        blink_led(10, color=(255,0,0))
        log_err(f"Erreur creation access point Wi-Fi : {e}")

is_ntp_sync = False
for attempt in range(3):
    try:
        ntptime.settime()
        is_ntp_sync = True
        break
    except Exception as e:
        log_err(f"Erreur ntptime.settime() : {e}")
        time.sleep(2 ** attempt)

env.set("NTP_SYNC", is_ntp_sync)
env.set("IS_UTC", is_ntp_sync)
env.set("BOOT_RTC_DATE", get_rtc_datetime_str())
