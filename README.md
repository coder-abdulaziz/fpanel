# FPANEL - Linux Hosting Control Panel

FPANEL - bu to'liq Linux hosting boshqaruv paneli bo'lib, professional shared hosting control panel sifatida ishlaydi.

## Xususiyatlar

- **Multi-tenant hosting**: Har bir foydalanuvchi alohida Linux user sifatida
- **Domain boshqaruvi**: Nginx vhost auto-yaratish, Let's Encrypt SSL
- **PHP Multi-version**: PHP 5.4 - 8.1 versiyalarini qo'llab-quvvatlash
- **Database**: MySQL/MariaDB boshqaruvi
- **Pochta tizimi**: Exim + Dovecot + SpamAssassin
- **DNS**: Bind9 zone boshqaruvi
- **FTP/SFTP**: ProFTPD va SFTP (2222 port)
- **Xavfsizlik**: Fail2ban, WAF qoidalari, brute force himoyasi
- **Statistika**: AWstats integratsiyasi

## Texnologiya Stack

- **Frontend**: Bootstrap 5 (port 5555)
- **Backend**: PHP 8.2 (custom MVC, frameworksiz)
- **Database**: SQLite (panel), MySQL (hosting)
- **System Agent**: Python3 root daemon
- **Aloqa**: UNIX socket JSON (/run/hostctl.sock)

## Qo'llab-quvvatlanadigan OS

- Debian 11/12
- Ubuntu 22.04/24.04
- AlmaLinux 8

## O'rnatish

### Bir qatorli buyruq orqali o'rnatish:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/USERNAME/FPANEL/main/install/install.sh)
```

### Yoki qo'lda o'rnatish:

```bash
# Repository ni klonlash
git clone https://github.com/USERNAME/FPANEL.git
cd FPANEL

# Install skriptni ishga tushirish
sudo bash install/install.sh
```

## Foydalanish

O'rnatishdan so'ng, brauzer orqali panelga kiring:

```
http://server-ip:5555
```

Standart login ma'lumotlari o'rnatish jarayonida so'raladi.

## Asosiy Buyruqlar

```bash
# Agent statusini ko'rish
systemctl status fpanel-agent

# Agentni qayta ishga tushirish
systemctl restart fpanel-agent

# Loglarni ko'rish
tail -f /var/log/fpanel/agent.log

# Nginx konfiguratsiyasini tekshirish
nginx -t

# Barcha xizmatlarni qayta ishga tushirish
systemctl restart fpanel-agent nginx php8.2-fpm mariadb
```

## Arxitektura

```
Frontend (5555)
    ↓
PHP Core MVC
    ↓
AgentClient (UNIX Socket)
    ↓
Python Root Agent
    ↓
OS Adapter (Debian 12)
    ↓
Linux System
```

## Xavfsizlik

- **bcrypt** parol xeshlash
- **CSRF** himoyasi
- **Brute force** bloklash (5 ta noto'g'ri urinishdan keyin 15 daqiqa)
- **IP whitelist** opsiyasi
- **Fail2ban** integratsiyasi
- **WAF** qoidalari (SQL injection, XSS, bad bot bloklash)
- **PHP izolatsiyasi** (open_basedir, disable_functions)

## Litsenziya

MIT License

## Muallif

FPANEL Team
