# 🎮 Настройка прокси для игровых консолей

## Обзор

TG WS Proxy поддерживает подключение игровых консолей через локальную сеть:
- **PS4/PS5** — полная поддержка SOCKS5
- **Nintendo Switch** — поддержка HTTP proxy
- **Xbox** — требуется настройка роутера

---

## 🚀 Быстрый старт

### Автоматическая настройка

```bash
# PS4/PS5
python setup_gaming_proxy.py --console PS5 --port 1080

# Nintendo Switch
python setup_gaming_proxy.py --console SWITCH --port 1081

# Xbox (инструкции)
python setup_gaming_proxy.py --console XBOX --firewall
```

### Ручная настройка

1. Запустите прокси на компьютере:
   ```bash
   python proxy/tg_ws_proxy.py --host 0.0.0.0 --socks-port 1080
   ```

2. Настройте брандмауэр Windows (PowerShell от администратора):
   ```powershell
   netsh advfirewall firewall add rule name="TG WS Proxy" dir=in action=allow protocol=TCP localport=1080
   netsh advfirewall firewall add rule name="TG WS Proxy UDP" dir=in action=allow protocol=UDP localport=1080
   ```

3. Узнайте IP адрес компьютера:
   ```bash
   ipconfig
   # IPv4 Address: 192.168.1.XXX
   ```

---

## 📱 PlayStation 4/5

### Пошаговая настройка

1. **Settings** → **Network** → **Network Settings**
2. **Set Up Internet Connection**
3. Выберите тип подключения:
   - **Wi-Fi** или **Use a LAN Cable** (рекомендуется)
4. **Custom** настройки:
   - **IP Address Settings**: Automatic
   - **DHCP Host Name**: Do Not Specify
   - **DNS Settings**: Manual
     - Primary DNS: `1.1.1.1`
     - Secondary DNS: `1.0.0.1`
   - **MTU Settings**: Automatic
   - **Proxy Server**: **Use**
     - Proxy Server: `<IP_КОМПЬЮТЕРА>` (например, 192.168.1.100)
     - Proxy Port: `1080`
5. **Save** и **Test Internet Connection**

### Проверка

```bash
python setup_gaming_proxy.py --test --ip 192.168.1.XXX
```

---

## 🎮 Nintendo Switch

### Пошаговая настройка

1. **System Settings** → **Internet** → **Internet Settings**
2. Выберите вашу Wi-Fi сеть
3. **Change Settings**
4. Прокрутите до **Proxy Settings**
5. **Proxy Server**: **On**
   - Proxy Server: `<IP_КОМПЬЮТЕРА>`
   - Port: `1081`
6. **Save** → **Test Connection**

### Важно

- Switch поддерживает только HTTP proxy
- Убедитесь что прокси поддерживает HTTP режим

---

## 🎯 Xbox One / Series X|S

### ⚠️ Ограничение

Xbox **не поддерживает** прокси напрямую!

### Варианты решения

#### 1. Настройка прокси на роутере

1. Зайдите в настройки роутера (192.168.1.1)
2. Найдите раздел **Proxy** или **SOCKS**
3. Укажите:
   - Server: `<IP_КОМПЬЮТЕРА>`
   - Port: `1080`

#### 2. PC как мост (Internet Connection Sharing)

1. **Панель управления** → **Сетевые подключения**
2. ПКМ на адаптере с интернетом → **Свойства**
3. **Доступ** → **Разрешить другим использовать**
4. Выберите адаптер локальной сети

#### 3. Прозрачный прокси на роутере

Требует прошивку **DD-WRT** или **OpenWRT**:
```bash
# Пример для DD-WRT
iptables -t nat -A PREROUTING -i br0 -p tcp --dport 80 -j REDIRECT --to-port 1080
```

---

## 🔧 Настройка брандмауэра

### Windows

Запустите PowerShell **от имени администратора**:

```powershell
# Разрешить прокси
netsh advfirewall firewall add rule name="TG WS Proxy" dir=in action=allow protocol=TCP localport=1080

# Разрешить UDP
netsh advfirewall firewall add rule name="TG WS Proxy UDP" dir=in action=allow protocol=UDP localport=1080

# Игровые порты (PS4/PS5)
netsh advfirewall firewall add rule name="PSN TCP" dir=in action=allow protocol=TCP localport=3478-3480
netsh advfirewall firewall add rule name="PSN UDP" dir=in action=allow protocol=UDP localport=3478-3480
```

### Linux (UFW)

```bash
sudo ufw allow 1080/tcp
sudo ufw allow 1080/udp
sudo ufw allow 3478:3480/tcp
sudo ufw allow 3478:3480/udp
```

---

## 📊 Поиск IP адреса консоли

### Через роутер

1. Зайдите в веб-интерфейс роутера
2. Найдите **Connected Devices** или **DHCP Clients**
3. Найдите устройство с именем "PS4" или "PS5"

### Через PowerShell

```powershell
Get-NetNeighbor | Where-Object State -Eq "Reachable" | Select-Object IPAddress,LinkLayerAddress
```

### Через ping + arp

```bash
# Ping broadcast
ping 192.168.1.255

# Показать ARP таблицу
arp -a
```

---

## 🛠️ Решение проблем

### Консоль не подключается

1. **Проверьте брандмауэр:**
   ```bash
   netsh advfirewall firewall show rule name="TG WS Proxy"
   ```

2. **Проверьте что прокси слушает все интерфейсы:**
   ```bash
   netstat -ano | findstr :1080
   ```
   Должно быть `0.0.0.0:1080` а не `127.0.0.1:1080`

3. **Проверьте IP адрес компьютера:**
   ```bash
   ipconfig
   ```
   Используйте IPv4 адрес из локальной сети (192.168.x.x)

### Таймаут подключения

1. Убедитесь что консоль и компьютер в **одной сети**
2. Отключите антивирус на время теста
3. Проверьте что роутер не блокирует локальные подключения

### NAT Type Strict

Для улучшения NAT Type:

1. Включите **UPnP** на роутере
2. Или настройте **Port Forwarding**:
   - TCP: 80, 443, 3478-3480, 9295-9297
   - UDP: 3478-3480

### Медленная скорость

1. Используйте **LAN кабель** вместо Wi-Fi
2. Проверьте скорость интернета
3. Попробуйте другой DC в настройках прокси

---

## 📱 Мобильные приложения

### Для подключения Telegram с телефона в той же сети:

**Android:**
1. Установите **Proxy Droid**
2. Добавьте прокси:
   - Type: SOCKS5
   - Host: `<IP_КОМПЬЮТЕРА>`
   - Port: 1080
3. Включите

**iOS:**
1. Установите **Potatso** или **Shadowrocket**
2. Добавьте конфигурацию
3. Включите в системных настройках

---

## 📊 Мониторинг

### Веб-панель

Откройте в браузере: `http://<IP_КОМПЬЮТЕРА>:8080`

Проверьте:
- Активные подключения
- Статистику по DC
- Метрики производительности

### Тестирование

```bash
# Тест подключения
python setup_gaming_proxy.py --test --ip 192.168.1.XXX

# Проверка портов
telnet 192.168.1.XXX 1080
```

---

## 🎮 Поддерживаемые игры

Через прокси работают:
- ✅ Telegram Desktop
- ✅ WhatsApp Desktop
- ✅ Discord (частично)
- ✅ Игры с поддержкой SOCKS5

**Ограничения:**
- ❌ Игры без поддержки прокси
- ❌ P2P игры (требуют direct connection)
- ❌ Игры с античитом (могут блокировать прокси)

---

## 📚 Ссылки

- [Настройка Telegram](QUICKSTART.md#настройка-telegram)
- [Конфигурация](CONFIGURATION.md)
- [Безопасность](SECURITY_ADVANCED.md)

---

**Версия:** v2.57.0  
**Последнее обновление:** 23.03.2026
