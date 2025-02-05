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
VERSION = "1.0.2"

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
# 3) Configuração de I2C e objeto do sensor
# -------------------------------------------------------------
i2c = machine.I2C(1, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
sht21_sensor = SHT21(i2c=i2c, address=0x40)

# -------------------------------------------------------------
# 4) Google Apps Script (deployment_code)
# -------------------------------------------------------------
deployment_code = 'AKfycbzOKvUxZ5sRAiqatzd-yuMH8qT4AKELip8I0O0SfraAXN8rSylQdl2QJdGw2haK9IYK'

# -------------------------------------------------------------
# 5) Funções OTA
# -------------------------------------------------------------
def file_exists(filepath):
    """Verifica se um arquivo existe no sistema de arquivos MicroPython."""
    try:
        os.stat(filepath)
        return True
    except OSError:
        return False

def check_version(new_code):
    """
    Verifica se o new_code (string) contém uma linha como:
    VERSION = "x.x.x"
    e compara com a VERSION atual do firmware.
    Retorna True se for diferente (ou seja, se há nova versão).
    """
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
    """Faz GET no URL. Se status 200, checa a versão. Se for nova, salva em /new_main.py."""
    try:
        print("Baixando novo código OTA de:", url)
        response = requests.get(url)
        if response.status_code == 200:
            new_code = response.text
            # Verifica se há versão diferente
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
    """
    Se /new_main.py existir, remove /main.py (se houver)
    e renomeia /new_main.py para /main.py, reiniciando em seguida.
    """
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
    """Fluxo completo: Baixa o código e aplica, se necessário."""
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
    Lê temp/umidade do SHT21 e envia para o Apps Script a cada 5 segundos.
    Caso queira checar OTA periodicamente, poderíamos chamar check_for_ota_update()
    dentro deste loop, mas estaria sujeito a resets no meio do funcionamento.
    """
    while True:
        try:
            # Ler sensor
            temperatura = sht21_sensor.read_temperature()  # °C
            umidade     = sht21_sensor.read_humidity()     # %

            print("Temperatura (°C):", temperatura)
            print("Umidade (%):", umidade)

            # Montar dados e enviar
            row_data = {}
            row_data["Temperatura"] = round(temperatura, 2)
            row_data["Umidade"]     = round(umidade, 2)

            post_data(row_data, deployment_code)

        except Exception as e:
            print("Erro na leitura/envio do sensor:", e)

        time.sleep(5)


# -------------------------------------------------------------
# 7) Execução principal
# -------------------------------------------------------------
setup()
while True:
    loop()

