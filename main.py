import network
import time
import machine
import urequests as requests  # Biblioteca para enviar requisições HTTP
import ujson
import gc  # Para liberar memória
import os

# Versão atual do código
VERSION = "1.0.1"

# URL para baixar o novo código OTA
OTA_URL = "https://raw.githubusercontent.com/Gabriel-Victor-cy/Teste_esp32_OTA/main/main.py"

# Função para conectar ao Wi-Fi
def connect_wifi(ssid, password=None):
    wlan = network.WLAN(network.STA_IF)  # Configura o Wi-Fi no modo "station"
    wlan.active(True)  # Ativa o adaptador Wi-Fi
    
    if not wlan.isconnected():
        print('Conectando ao Wi-Fi...')
        if password:
            wlan.connect(ssid, password)  # Conecta ao Wi-Fi com o SSID e senha fornecidos
        else:
            wlan.connect(ssid)  # Se não houver senha, conecta a um Wi-Fi aberto

        timeout = 15  # Timeout de 15 segundos para conectar
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
        machine.reset()  # Reinicia a ESP32 caso não consiga conectar
        return False

# Função para autenticar no captive portal (se necessário)
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
        print(f"Autenticando no captive portal: {login_url}")
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
        gc.collect()  # Libera memória após a operação
    except Exception as e:
        print(f"Erro ao autenticar no portal captive: {e}")

# Função para enviar dados para a planilha
def post_data(row_data, deployment_code):
    try:
        request_data = ujson.dumps({"parameters": row_data})
        r = requests.post("https://script.google.com/macros/s/" + deployment_code + "/exec", headers = {"content-type": "application/json"}, data = request_data)
        r.close()
    except Exception as e:
        print(f"Error posting data: {e}")

# Função para verificar se o código OTA contém uma versão nova
def check_version(new_code):
    # Procura a linha que contém a versão no novo código
    for line in new_code.split("\n"):
        if line.startswith("VERSION = "):
            new_version = line.split("=")[1].strip().strip('"')
            if new_version != VERSION:
                print(f"Nova versão encontrada: {new_version}")
                return True
            else:
                print("O código já está atualizado. Nenhuma ação necessária.")
                return False
    print("Nenhuma versão encontrada no código OTA.")
    return False

# Função OTA para baixar o novo código
def download_new_code(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            new_code = response.text
            if check_version(new_code):  # Verifica se há uma nova versão
                with open("/new_main.py", "w") as f:
                    f.write(new_code)
                print("Novo código baixado com sucesso!")
            else:
                print("Nenhuma atualização OTA necessária.")
            response.close()
        else:
            print(f"Falha ao baixar o código. Status code: {response.status_code}")
            response.close()
    except Exception as e:
        print(f"Erro ao tentar baixar o código: {e}")

# Função para verificar se um arquivo existe (alternativa ao os.path.exists no MicroPython)
def file_exists(filepath):
    try:
        os.stat(filepath)
        return True
    except OSError:
        return False

# Função para aplicar o novo código e reiniciar
def apply_new_code():
    try:
        if file_exists("/new_main.py"):  # Verifica se o novo arquivo existe
            if file_exists("/main.py"):  # Se o arquivo principal já existir
                os.remove("/main.py")  # Remove o código atual
            os.rename("/new_main.py", "/main.py")  # Aplica o novo código
            print("Novo código aplicado com sucesso! Reiniciando...")
            machine.reset()  # Reinicia a ESP32 para executar o novo código
        else:
            print("Nenhum novo código para aplicar.")
    except Exception as e:
        print(f"Erro ao aplicar o novo código: {e}")

# Função para verificar e aplicar OTA
def check_for_ota_update():
    print("Verificando se há atualizações OTA...")
    download_new_code(OTA_URL)  # Baixa o novo código
    apply_new_code()  # Aplica o novo código e reinicia a ESP32, se houver

# Função alternativa para urlencode no MicroPython
def urlencode(data):
    return '&'.join('{}={}'.format(key, value) for key, value in data.items())

deployment_code9 = 'AKfycbzOKvUxZ5sRAiqatzd-yuMH8qT4AKELip8I0O0SfraAXN8rSylQdl2QJdGw2haK9IYK'

row_data9 = {}

def update_row_data9():
    row_data9["var0"] = "Poli_Sem_fio_Git_hub_V2"

# Configurações iniciais
def setup():
    ssid = 'PoliSemFio'  # Nome da rede Wi-Fi
    password = None  # Deixe None se a rede não tiver senha
    
    if connect_wifi(ssid, password):
        # Autenticar no captive portal
        login_url = "https://semfio.poli.usp.br:8003/index.php"
        username = "12330922"  # Seu número USP
        portal_password = "pE8GpJKVjvrA"  # Sua senha do portal

        authenticate_captive_portal(login_url, username, portal_password)
        # Verifica se há uma atualização OTA disponível
        check_for_ota_update()        
        # Enviar dados para a planilha após conexão e autenticação
        for count in range(10):
            update_row_data9()
            post_data(row_data9, deployment_code9)



# Loop principal
def loop():
    while True:
        time.sleep(5)  # Aguarda 5 segundos

# Executa o setup e o loop
setup()

while True:
    loop()
