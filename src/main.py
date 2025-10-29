from microdot import Microdot, Response, send_file
import time
import json
import os
import _thread
import esp32
import gc
import machine

from ina3221 import INA3221
from dataHist import DataHist
from env import env
from wifi import wifi
from tools import get_mime_type, parse_iso_date_str, get_rtc_datetime_str, format_memory
from logger import log, log_warn, log_err, get_logs

app = Microdot()
ina = INA3221(addr=0x40)
data = DataHist()

# Function to collect sensor data in a separate thread
def sensor_loop():
    target_period = 1.0 / int(env.get('ACQUISITION_FREQ', 1))
    while True:
        start_time = time.ticks_ms()  # Get current time in milliseconds
        # Read values from each channel
        v1 = ina.get_bus_voltage(0)
        a1 = ina.get_current(0)
        v2 = ina.get_bus_voltage(1)
        a2 = ina.get_current(1)
        v3 = ina.get_bus_voltage(2)
        a3 = ina.get_current(2)
        
       
        data.add(v1, a1, v2, a2, v3, a3)
        
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time) / 1000.0
        
        if target_period - elapsed_time < 0:
            log_warn("Freq too high")
            
        sleep_time = max(0, target_period - elapsed_time)
        time.sleep(sleep_time)


@app.after_error_request
def log_error_request(request, response):
    if request is None:
        log_err(f"[ERREUR] request=None | response: {response.status_code}")
        return response
    try:
        body = response.body.decode('utf-8') if isinstance(response.body, bytes) else str(response.body)
    except:
        body = "<décodage échoué>"
    log_err(f"{request.method} {request.path} → {response.status_code} | {body}")
    return response

@app.after_request
def log_request(request, response):
    log(f"{request.method} {request.path} - {response.status_code}", tag="HTTP")
    return response

@app.get('/api/status')
def api_status(request):
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }
    devices = ina.i2c.scan()
    
    # --- RAM ---
    ram_used = gc.mem_alloc()
    ram_total = ram_used + gc.mem_free()

    # --- Stockage Flash (/data) ---
    flash = os.statvfs('/')
    storage_total = flash[0] * flash[1]
    storage_used = flash[0] * flash[2]

    # --- PSRAM (si disponible) ---
    psram_str = None
    if hasattr(esp32, 'heap_caps_get_free_size') and hasattr(esp32, 'MALLOC_CAP_SPIRAM'):
        try:
            total = esp32.heap_caps_get_total_size(esp32.MALLOC_CAP_SPIRAM)
            free = esp32.heap_caps_get_free_size(esp32.MALLOC_CAP_SPIRAM)
            if total > 0:
                psram_str = format_memory(total - free, total)
        except:
            psram_str = "error"

    response = {
        'date':{
            'now': get_rtc_datetime_str(),
            'boot':env.get('BOOT_RTC_DATE'),
            'utc':env.get('IS_UTC', False),
            'sync':env.get('NTP_SYNC', False),
        },
        'wifi':{
            'ssid': wifi.ssid,
            'ip': wifi.get_ip(),
            'isConnect': wifi.is_wlan_connect(),
            'mode' : wifi.mode
        }, 
        'sensor':{
            'loopFreq': env.get('ACQUISITION_FREQ',1),
            'ina3221.address': hex(ina.addr),
            'ina3221.id': hex(ina.get_manuf_id()),
            'i2c.scan': [hex(device) for device in devices]
        },
        'memory': {
            'ram': format_memory(ram_used, ram_total),
            'storage': format_memory(storage_used, storage_total),
            'psram': psram_str
        }
    }

    return Response(json.dumps(response), headers=response_headers)

@app.get('/api/logs')
def api_logs(request):
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': 'Content-Type',
    }
    logs = get_logs()
    return Response(json.dumps(logs), headers=response_headers)

@app.get('/api/ssidList')
def api_ssid_list(request):
    response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    
    try:
        response_data = wifi.list_ssid()
        return Response(json.dumps(response_data), headers=response_headers)

    except Exception as e:
        log_err("Erreur dans api_ssid_list:", e)
        return Response(
            json.dumps({'error': f'Erreur: {str(e)}'}),
            status_code=500,
            headers=response_headers
        )


@app.post('/api/connect')
def api_connect_wifi(request):
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    content_type = request.headers.get('Content-Type', '')
    
    try:
        body = request.body.decode('utf-8')

        # Parser manuellement les données form-urlencoded
        data = {}
        if 'application/x-www-form-urlencoded' in content_type:
            pairs = body.split('&')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    data[key] = value  # Pas de url decode complet, mais suffisant ici
        else:
            # Optionnel : fallback si JSON (mais on ne veut pas)
            return Response(
                json.dumps({'error': 'Content-Type non supporté'}),
                status_code=415,
                headers=response_headers
            )

        # Récupérer les champs
        ssid = data.get('ssid')
        pwd = data.get('password')
        
        if not ssid or not pwd:
            return Response(
                json.dumps({'error': 'SSID et mot de passe sont requis'}),
                status_code=400,
                headers=response_headers
            )

        # Connexion Wi-Fi
        old_ssid = env.get("WIFI_SSID")
        old_password = env.get("WIFI_PASSWORD")
        was_connect = wifi.is_wlan_connect()
        
        is_connect = wifi.connect(ssid, pwd)
 
        if not is_connect and was_connect:
            # Reconnect old config
           return wifi.connect(old_ssid, old_password)
        return machine.reset()

    except Exception as e:
        log_err(f"Erreur dans api_connect_wifi: {e}")
        return Response(
            json.dumps({'error': f'Erreur interne: {str(e)}'}),
            status_code=500,
            headers=response_headers
        )


@app.get('/api/data')
def api_data(request):
    response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    
    try:    
        response_data = []
        from_date_str = request.args.get('from', None)
        
        if from_date_str is not None:
            from_date = parse_iso_date_str(from_date_str)
            response_data = data.all_after(from_date)
        else:
            response_data = data.all()
                
        return Response(json.dumps(response_data), headers=response_headers)

    except Exception as e: 
        log_err("Erreur dans api_data:", e)
        return Response(
            json.dumps({'error': f'Erreur: {str(e)}'}),
            status_code=500,
            headers=response_headers
        )


@app.get('/api/files')
def api_files(request):
    response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
    
    try:
        files = os.listdir(data.dir_path)
        response_data = []
        base_url = request.headers.get('host', 'localhost')  # Get host from request
        for filename in files:
            response_data.append({
                'filename': filename,
                'url': f"http://{base_url}/files/{filename}",
                'size': os.stat(f'./data/{filename}')[6]  # Size in bytes
            })
        return Response(json.dumps(response_data), headers=response_headers)
    except Exception as e:
        log_err("Erreur dans api_files:", e)
        return Response(
            {'error': f'Erreur: {str(e)}'},
            status_code=500,
            headers=response_headers
        )
        

@app.route('/files/<filename>')
def file_download(request, filename):
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
    }
    try:
        filepath = f'./data/{filename}'
        try:
            os.stat(filepath)  # Check file existence
        except OSError:
            return Response(
                {'error': f'Fichier {filename} non trouvé'},
                status_code=404,
                headers=response_headers
            )
        # Get the file response
        file_response = send_file(filepath)
        # Merge headers manually
        combined_headers = file_response.headers.copy()  # Copy headers from send_file
        combined_headers.update(response_headers)  # Add CORS headers
        return Response(
            body=file_response.body,
            headers=combined_headers,
            status_code=file_response.status_code
        )
    except Exception as e:
        log_err("Erreur dans file_download:", e)
        return Response(
            {'error': f'Erreur: {str(e)}'},
            status_code=500,
            headers=response_headers
        )

@app.get('/')
@app.get('/<filepath>')
@app.get('/static/css/<filepath>')
@app.get('/static/js/<filepath>')
def serve_static(request, filepath=None):
    
    print(f"serve_static {filepath}")
    print(f"request {request.url}")
    
    if filepath == "" or filepath is None:
        filepath = "/index.html"
    else:
        filepath = request.url
    
    safe_filepath = filepath.replace('..', '').replace('\\', '/')
    full_path = f'./www/{safe_filepath}'
    try:
        os.stat(full_path)
        return send_file(full_path)
    except OSError as e:
        log_err(f"Erreur dans serve_static - file not found: {full_path} - {e}")
        return Response(
            {'error': f'Fichier {filepath} non trouvé'},
            status_code=404,
            headers={'Access-Control-Allow-Origin': '*'}
        )


if __name__ == '__main__':
    for attempt in range(3):
        try:
            ina.reset()
            _thread.start_new_thread(sensor_loop, ())
            env.set('SENSOR_LOOP', True)
            break
        except Exception as e:
            
            log('Scan I2C devices...')
            devices = ina.i2c.scan()
            if devices:
                log('Devices found:', devices)
            else:
                log('No I2C devices found.')

            has_reset = ina.reset_i2c()
            log_err(f"Erreur start sensor_loop - has_reset: {has_reset} - err: {e}")
            time.sleep(2 ** attempt)
            
    # Run the Microdot server
    app.run(debug=False, host='0.0.0.0', port=80)