import network
import time
import machine
import urequests as requests
import ujson
import gc
import os

# -------------------------------------------------------------
# Versão atual do firmware (altere se subir uma nova versão)
# -------------------------------------------------------------
VERSION = "1.0.0"

# -------------------------------------------------------------
# URL do código OTA (raw GitHub ou outra fonte).
# Esse arquivo deve conter uma linha 'VERSION = "x.y.z"' atualizada.
# -------------------------------------------------------------
OTA_URL = "https://raw.githubusercontent.com/Gabriel-Victor-cy/Teste_esp32_OTA/main/main.py"

# -------------------------------------------------------------
# 1) Funções de Wi-Fi, portal e envio de dados
# -------------------------------------------------------------
def urlencode(data):
    return '&'.join('{}={}'.format(key, value) for key, value in data.items())

def connect_wifi(ssid, password=None):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('Conectando ao Wi-Fi...')
        if password:
            wlan.connect(ssid, password)
        else:
            wlan.connect(ssid)

        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(f'Aguardando conexão... {15 - timeout}/15')

    if wlan.isconnected():
        print('Conectado ao Wi-Fi!')
        print('Endereço IP:', wlan.ifconfig()[0])
        return True
    else:
        print('Falha ao conectar ao Wi-Fi. Reiniciando...')
        machine.reset()
        return False

def authenticate_captive_portal(login_url, username, password):
    try:
        payload = {
            "auth_user": username,
            "auth_pass": password,
            "redirurl": "https://semfio.poli.usp.br:8003/index.php?zone=cpzone",
            "zone": "cpzone",
            "accept": "Entrar"
        }
        payload_encoded = urlencode(payload)
        
        headers = {
            "Host": "semfio.poli.usp.br:8003",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://semfio.poli.usp.br:8003",
            "Connection": "keep-alive",
        }

        response = requests.post(login_url, data=payload_encoded, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print("Autenticação bem-sucedida!")
        else:
            print(f"Falha na autenticação. Código: {response.status_code}")
        
        response.close()
        gc.collect()
    except Exception as e:
        print(f"Erro ao autenticar no portal captive: {e}")

def post_data(row_data, deployment_code):
    try:
        request_data = ujson.dumps({"parameters": row_data})
        r = requests.post(
            "https://script.google.com/macros/s/" + deployment_code + "/exec",
            headers={"content-type": "application/json"},
            data=request_data
        )
        r.close()
    except Exception as e:
        print(f"Error posting data: {e}")


# -------------------------------------------------------------
# 2) Classe SHT21 (ou SI7021) – leitura de Temp/Umidade em 0x40
# -------------------------------------------------------------
class SHT21:
    CMD_MEASURE_TEMP = 0xF3
    CMD_MEASURE_RH   = 0xF5

    def __init__(self, i2c, address=0x40):
        self.i2c = i2c
        self.address = address

    def _read_sensor(self, command):
        self.i2c.writeto(self.address, bytes([command]))
        time.sleep_ms(100)
        data = self.i2c.readfrom(self.address, 3)
        return data

    def read_temperature(self):
        data = self._read_sensor(self.CMD_MEASURE_TEMP)
        raw_value = (data[0] << 8) + data[1]
        raw_value &= 0xFFFC
        temp = -46.85 + (175.72 * raw_value / 65536.0)
        return temp

    def read_humidity(self):
        data = self._read_sensor(self.CMD_MEASURE_RH)
        raw_value = (data[0] << 8) + data[1]
        raw_value &= 0xFFFC
        hum = -6 + (125.0 * raw_value / 65536.0)
        return hum

# -------------------------------------------------------------
# 3) Configuração de I2C e objetos dos sensores
# -------------------------------------------------------------
i2c = machine.I2C(1, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
sht21_sensor = SHT21(i2c=i2c, address=0x40)

# -------------------------------------------------------------
# 3.1) Sensor CCS811 (CO2) em 0x5A
# -------------------------------------------------------------
try:
    from ccs811 import CCS811  # Biblioteca para CCS811 em MicroPython
    # import adafruit_ccs811  # Se estiver usando a versão CircuitPython
    ccs811_sensor = CCS811(i2c=i2c, addr=0x5A)
    ccs811_enabled = True
    print("Sensor CCS811 inicializado com sucesso.")
except Exception as e:
    print("Erro ao inicializar CCS811:", e)
    ccs811_enabled = False

# -------------------------------------------------------------
# 3.2) Sensor BME280 (Pressão) em 0x76
# -------------------------------------------------------------
try:
    import bme280  # Biblioteca bme280.py precisa estar no sistema de arquivos
    # Caso esteja usando "from bme280 import BME280", ajuste a criação do objeto.
    bme = bme280.BME280(i2c=i2c, address=0x76)
    bme280_enabled = True
    print("Sensor BME280 inicializado com sucesso.")
except Exception as e:
    print("Erro ao inicializar BME280:", e)
    bme280_enabled = False

# -------------------------------------------------------------
# 4) Google Apps Script (deployment_code)
# -------------------------------------------------------------
deployment_code = 'AKfycbxarLqDmbOGlEjl5f7PJDKxMs5O8V0xHF0Ct32wJSDNgW46VRHW4B1ePruoeM38L5DNlQ'

# -------------------------------------------------------------
# 5) Funções OTA
# -------------------------------------------------------------
def file_exists(filepath):
    try:
        os.stat(filepath)
        return True
    except OSError:
        return False

def check_version(new_code):
    for line in new_code.split("\n"):
        if line.startswith("VERSION = "):
            new_version = line.split("=")[1].strip().strip('"')
            if new_version != VERSION:
                print(f"Nova versão encontrada: {new_version}")
                return True
            else:
                print("O código já está atualizado. Nenhuma ação necessária.")
                return False
    print("Não foi encontrada linha de versão no código OTA.")
    return False

def download_new_code(url):
    try:
        print("Baixando novo código OTA de:", url)
        response = requests.get(url)
        if response.status_code == 200:
            new_code = response.text
            if check_version(new_code):
                with open("/new_main.py", "w") as f:
                    f.write(new_code)
                print("Novo código baixado com sucesso em /new_main.py!")
            else:
                print("Nenhuma atualização OTA necessária.")
            response.close()
        else:
            print(f"Falha ao baixar código OTA. Status code: {response.status_code}")
            response.close()
    except Exception as e:
        print(f"Erro ao tentar baixar o código OTA: {e}")

def apply_new_code():
    try:
        if file_exists("/new_main.py"):
            if file_exists("/main.py"):
                os.remove("/main.py")
            os.rename("/new_main.py", "/main.py")
            print("Novo código aplicado com sucesso! Reiniciando...")
            machine.reset()
        else:
            print("Nenhum novo código para aplicar.")
    except Exception as e:
        print(f"Erro ao aplicar o novo código: {e}")

def check_for_ota_update():
    print("Verificando se há atualizações OTA...")
    download_new_code(OTA_URL)
    apply_new_code()

# -------------------------------------------------------------
# 6) Funções setup() e loop()
# -------------------------------------------------------------
def setup():
    ssid = 'PoliSemFio'
    password = None

    if connect_wifi(ssid, password):
        # Autenticar no portal cativo
        login_url = "https://semfio.poli.usp.br:8003/index.php"
        username = "12330922"
        portal_password = "sua_senha_aqui"
        authenticate_captive_portal(login_url, username, portal_password)

        print("Setup concluído! Rede conectada e portal autenticado.")
        
        # Chamar OTA - se existir nova versão, a placa será atualizada e reiniciada aqui
        check_for_ota_update()

def loop():
    """
    Lê Temp/Umidade do SHT21, CO2 do CCS811 (se disponível),
    Pressão (e possivelmente Temp/Umid) do BME280, e envia para o Apps Script a cada 5s.
    """
    while True:
        row_data = {}

        # 1) Ler SHT21
        try:
            temperatura = sht21_sensor.read_temperature()  # °C
            umidade     = sht21_sensor.read_humidity()     # %
            print("Temperatura (°C) [SHT21]:", temperatura)
            print("Umidade (%) [SHT21]:", umidade)

            #row_data["Temperatura"] = round(temperatura, 2)
            #row_data["Umidade"]     = round(umidade, 2)
        except Exception as e:
            print("Erro SHT21:", e)

        # 2) Ler CCS811 (CO2)
        if ccs811_enabled:
            try:
                if ccs811_sensor.data_ready():
                    co2_ppm = ccs811_sensor.eCO2
                    # tvoc_ppb = ccs811_sensor.tVOC  # se precisar
                    print("CO2 (ppm) [CCS811]:", co2_ppm)
                    #row_data["CO2_ppm"] = co2_ppm
                else:
                    print("CCS811 ainda não está pronto para leitura.")
            except Exception as e:
                print("Erro CCS811:", e)
        # 3) Ler BME280 (Temp, Pressão, Umidade)
        if bme280_enabled:
            try:
                temp_str  = bme.temperature   # Ex: "25.32C"
                press_str = bme.pressure     # Ex: "1013.10hPa"
                #hum_str   = bme.humidity     # Ex: "45.23%"

                # Converter para número:
                temp_val  = float(temp_str[:-1])
                press_val = float(press_str.replace('hPa',''))
                #hum_val   = float(hum_str.replace('%',''))

                print("BME280 -> T=%.2f °C  P=%.2f hPa" % (temp_val, press_val))
                #print("BME280 -> P=%.2f hPa   %%" % (press_val))

                # Enviar para o dicionário (ou como preferir)
                #row_data["Temperatura_BME"] = temp_val
                #row_data["Pressao_hPa"]     = press_val
                #row_data["Umidade_BME"]     = hum_val

            except Exception as e:
                print("Erro BME280:", e)
        
        row_data["Temperatura"] = round(temperatura, 2)
        row_data["Umidade"]     = round(umidade, 2)
        row_data["CO2_ppm"] 	= co2_ppm
        row_data["Temperatura_BME"] = temp_val
        row_data["Pressao_hPa"]     = press_val
        
        # Enviar ao Google Sheets
        if row_data:
            post_data(row_data, deployment_code)

        time.sleep(5)

# -------------------------------------------------------------
# 7) Execução principal
# -------------------------------------------------------------
setup()
while True:
    loop()



