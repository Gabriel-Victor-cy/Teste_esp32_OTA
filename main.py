import network
import time
import machine
import urequests as requests  # Biblioteca para enviar requisições HTTP
import ujson
import gc  # Para liberar memória
import random

# Função alternativa para urlencode no MicroPython
def urlencode(data):
    return '&'.join('{}={}'.format(key, value) for key, value in data.items())

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
        # Dados que serão enviados no login (agora como um formulário codificado)
        payload = {
            "auth_user": username,
            "auth_pass": password,
            "redirurl": "https://semfio.poli.usp.br:8003/index.php?zone=cpzone",
            "zone": "cpzone",
            "accept": "Entrar"
        }
        # Codifica os dados como `application/x-www-form-urlencoded`
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

# Função para enviar número aleatório para a planilha
def post_data(row_data, deployment_code):
    try:
        request_data = ujson.dumps({"parameters": row_data})
        r = requests.post("https://script.google.com/macros/s/" + deployment_code + "/exec", headers = {"content-type": "application/json"}, data = request_data)
        #print(f"Response: {r.text}")
        r.close()
    except Exception as e:
        print(f"Error posting data: {e}")

deployment_code9 = 'AKfycbzOKvUxZ5sRAiqatzd-yuMH8qT4AKELip8I0O0SfraAXN8rSylQdl2QJdGw2haK9IYK'

row_data9 = {}

def update_row_data9():
    row_data9["var0"] = "Poli_Sem_fio"

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
        
        # Enviar 10 números aleatórios para a planilha após conexão e autenticação
        for count in range(10):
            update_row_data9()
            post_data(row_data9, deployment_code9)

# Loop principal
def loop():
    while True:
        # Aqui você pode adicionar o código que deseja repetir continuamente
       # print("ESP32 funcionando...")  # Apenas para teste
        time.sleep(5)  # Aguarda 5 segundos

# Executa o setup e o loop
setup()

while True:
    loop()
