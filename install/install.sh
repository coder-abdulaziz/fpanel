#!/bin/bash
#
# FPANEL - Installation Script
# Debian 12 / Ubuntu 22.04+ / AlmaLinux 8
# GitHub: https://github.com/USERNAME/FPANEL
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# GitHub Configuration
GITHUB_REPO="USERNAME/FPANEL"
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/main"
GITHUB_ARCHIVE="https://github.com/${GITHUB_REPO}/archive/refs/heads/main.tar.gz"

# Configuration
FPANEL_DIR="/usr/local/fpanel"
FPANEL_USER="fpanel"
FPANEL_GROUP="fpanel"
WEB_USER="www-data"
AGENT_SOCKET="/run/hostctl.sock"
TEMP_DIR="/tmp/fpanel-install"

# Log functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Bu skript root huquqlari bilan ishga tushirilishi kerak"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        log_error "OS aniqlanmadi"
        exit 1
    fi

    log_info "Aniqlangan OS: $OS $VERSION"

    case $OS in
        debian|ubuntu)
            if [[ "$VERSION" != "12" && "$VERSION" != "22.04" && "$VERSION" != "24.04" ]]; then
                log_warning "Test qilinmagan OS versiyasi: $VERSION"
            fi
            ;;
        almalinux)
            if [[ "$VERSION" != "8" ]]; then
                log_warning "Test qilinmagan OS versiyasi: $VERSION"
            fi
            ;;
        *)
            log_error "Qo'llab-quvvatlanmaydigan OS: $OS"
            exit 1
            ;;
    esac
}

# Update system
update_system() {
    log_info "Tizim yangilanmoqda..."
    
    case $OS in
        debian|ubuntu)
            apt-get update
            apt-get upgrade -y
            ;;
        almalinux)
            dnf update -y
            ;;
    esac
    
    log_success "Tizim yangilandi"
}

# Install dependencies
install_dependencies() {
    log_info "Paketlar o'rnatilmoqda..."
    
    case $OS in
        debian|ubuntu)
            apt-get install -y \
                nginx \
                php8.2 php8.2-fpm php8.2-cli php8.2-common php8.2-curl php8.2-gd php8.2-mbstring php8.2-mysql php8.2-opcache php8.2-sqlite3 php8.2-xml php8.2-zip \
                php7.4-fpm php8.0-fpm php8.1-fpm \
                python3 python3-pip python3-venv \
                sqlite3 \
                mariadb-server \
                exim4 dovecot-core dovecot-imapd dovecot-pop3d \
                bind9 \
                proftpd-basic \
                redis-server \
                memcached \
                fail2ban \
                iptables \
                quota quotatool \
                curl wget git unzip \
                certbot python3-certbot-nginx \
                clamav \
                awstats \
                bc
            ;;
        almalinux)
            dnf install -y \
                nginx \
                php php-fpm php-cli php-common php-curl php-gd php-mbstring php-mysqlnd php-opcache php-pdo php-xml php-zip \
                python3 python3-pip \
                sqlite \
                mariadb-server \
                exim dovecot \
                bind \
                proftpd \
                redis \
                memcached \
                fail2ban \
                iptables \
                quota \
                curl wget git unzip \
                certbot python3-certbot-nginx \
                clamav \
                awstats \
                bc
            ;;
    esac
    
    log_success "Paketlar o'rnatildi"
}

# Install Python dependencies
install_python_deps() {
    log_info "Python paketlari o'rnatilmoqda..."
    
    pip3 install --upgrade pip
    pip3 install \
        bcrypt \
        psutil \
        requests
    
    log_success "Python paketlari o'rnatildi"
}

# Create user and directories
create_user() {
    log_info "Foydalanuvchi va papkalar yaratilmoqda..."
    
    # Create group
    groupadd -f $FPANEL_GROUP
    
    # Create user
    if ! id "$FPANEL_USER" &>/dev/null; then
        useradd -r -g $FPANEL_GROUP -d $FPANEL_DIR -s /bin/false $FPANEL_USER
    fi
    
    # Create directories
    mkdir -p $FPANEL_DIR
    mkdir -p /var/www
    mkdir -p /var/log/fpanel
    mkdir -p /var/log/nginx
    mkdir -p /etc/fpanel
    mkdir -p /run/fpanel
    
    # Set permissions
    chown -R $FPANEL_USER:$FPANEL_GROUP $FPANEL_DIR
    chown -R $FPANEL_USER:$FPANEL_GROUP /var/log/fpanel
    chmod 755 /var/www
    
    log_success "Foydalanuvchi va papkalar yaratildi"
}

# Download FPANEL from GitHub
download_fpanel() {
    log_info "FPANEL GitHub dan yuklanmoqda..."
    
    # Create temp directory
    rm -rf $TEMP_DIR
    mkdir -p $TEMP_DIR
    cd $TEMP_DIR
    
    # Download latest version
    log_info "Eng so'nggi versiya yuklanmoqda..."
    curl -fsSL -o fpanel.tar.gz $GITHUB_ARCHIVE
    
    # Extract
    tar -xzf fpanel.tar.gz
    
    # Find extracted directory
    EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "FPANEL-*" | head -1)
    
    if [ -z "$EXTRACTED_DIR" ]; then
        log_error "Yuklashda xatolik: katalog topilmadi"
        exit 1
    fi
    
    log_success "FPANEL yuklandi"
}

# Copy FPANEL files
copy_files() {
    log_info "Fayllar nusxalanmoqda..."
    
    cd $TEMP_DIR
    EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "FPANEL-*" | head -1)
    
    # Create directory structure
    mkdir -p $FPANEL_DIR/{agent,backend,database,configs,systemd,templates}
    
    # Copy agent
    cp -r $EXTRACTED_DIR/agent/* $FPANEL_DIR/agent/
    
    # Copy backend
    cp -r $EXTRACTED_DIR/backend/* $FPANEL_DIR/backend/
    
    # Copy database
    cp -r $EXTRACTED_DIR/database/* $FPANEL_DIR/database/
    
    # Copy configs
    cp -r $EXTRACTED_DIR/configs/* $FPANEL_DIR/configs/
    
    # Copy systemd
    cp -r $EXTRACTED_DIR/systemd/* $FPANEL_DIR/systemd/
    
    # Copy templates
    if [ -d "$EXTRACTED_DIR/templates" ]; then
        cp -r $EXTRACTED_DIR/templates/* $FPANEL_DIR/templates/
    fi
    
    # Copy panel assets
    if [ -d "$EXTRACTED_DIR/panel" ]; then
        cp -r $EXTRACTED_DIR/panel/* $FPANEL_DIR/backend/public/
    elif [ -d "$EXTRACTED_DIR/frontend/assets" ]; then
        cp -r $EXTRACTED_DIR/frontend/assets/* $FPANEL_DIR/backend/public/
    fi
    
    # Set permissions
    chown -R $FPANEL_USER:$FPANEL_GROUP $FPANEL_DIR
    chmod +x $FPANEL_DIR/agent/hostctl.py
    
    # Cleanup
    rm -rf $TEMP_DIR
    
    log_success "Fayllar nusxalandi"
}

# Initialize database
init_database() {
    log_info "Database ishga tushirilmoqda..."
    
    # Create database directory
    mkdir -p $FPANEL_DIR/database
    
    # Initialize SQLite database
    sqlite3 $FPANEL_DIR/database/fpanel.db < $FPANEL_DIR/database/schema.sql
    
    # Set permissions
    chown -R $FPANEL_USER:$FPANEL_GROUP $FPANEL_DIR/database
    chmod 640 $FPANEL_DIR/database/fpanel.db
    
    log_success "Database ishga tushirildi"
}

# Configure Nginx
configure_nginx() {
    log_info "Nginx sozlanmoqda..."
    
    # Create FPANEL nginx config
    cat > /etc/nginx/sites-available/fpanel << EOF
server {
    listen 5555;
    server_name _;
    root ${FPANEL_DIR}/backend/public;
    index index.php;

    access_log /var/log/nginx/fpanel.access.log;
    error_log /var/log/nginx/fpanel.error.log;

    location / {
        try_files \$uri \$uri/ /index.php?\$query_string;
    }

    location ~ \\.php\$ {
        fastcgi_pass unix:/run/php/php8.2-fpm.sock;
        fastcgi_index index.php;
        fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
        include fastcgi_params;
    }

    location ~ /\\. {
        deny all;
    }

    location ~* \\.(sql|log|conf)\$ {
        deny all;
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/fpanel /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test and reload nginx
    nginx -t
    systemctl reload nginx
    
    log_success "Nginx sozlandi"
}

# Configure PHP-FPM
configure_php() {
    log_info "PHP-FPM sozlanmoqda..."
    
    # Create PHP log directory
    mkdir -p /var/log/php8.2-fpm
    chown $FPANEL_USER:$FPANEL_GROUP /var/log/php8.2-fpm
    
    # Configure PHP 8.2
    cat > /etc/php/8.2/fpm/pool.d/fpanel.conf << EOF
[fpanel]
user = $FPANEL_USER
group = $FPANEL_GROUP
listen = /run/php/php8.2-fpanel.sock
listen.owner = www-data
listen.group = www-data
pm = dynamic
pm.max_children = 10
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 3
php_admin_value[open_basedir] = ${FPANEL_DIR}/:/tmp/:/var/tmp/
php_admin_value[upload_tmp_dir] = /tmp
php_admin_value[session.save_path] = /tmp
EOF

    # Restart PHP-FPM
    systemctl restart php8.2-fpm
    
    log_success "PHP-FPM sozlandi"
}

# Configure MySQL
configure_mysql() {
    log_info "MySQL sozlanmoqda..."
    
    # Start MySQL
    systemctl start mariadb
    systemctl enable mariadb
    
    # Secure installation
    mysql -e "UPDATE mysql.user SET Password=PASSWORD('$(openssl rand -base64 32)') WHERE User='root';"
    mysql -e "DELETE FROM mysql.user WHERE User='';"
    mysql -e "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');"
    mysql -e "DROP DATABASE IF EXISTS test;"
    mysql -e "FLUSH PRIVILEGES;"
    
    log_success "MySQL sozlandi"
}

# Configure Fail2ban
configure_fail2ban() {
    log_info "Fail2ban sozlanmoqda..."
    
    # Create FPANEL jail
    cat > /etc/fail2ban/jail.d/fpanel.conf << EOF
[fpanel]
enabled = true
port = 5555
filter = fpanel
logpath = /var/log/fpanel/auth.log
maxretry = 5
bantime = 3600
EOF

    # Create filter
    cat > /etc/fail2ban/filter.d/fpanel.conf << EOF
[Definition]
failregex = ^.*Failed login attempt from <HOST>.*$
ignoreregex =
EOF

    systemctl restart fail2ban
    
    log_success "Fail2ban sozlandi"
}

# Install systemd service
install_service() {
    log_info "Systemd servisi o'rnatilmoqda..."
    
    # Copy service file
    cp $FPANEL_DIR/systemd/fpanel-agent.service /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable fpanel-agent
    
    log_success "Systemd servisi o'rnatildi"
}

# Configure firewall (optional - skipped by default)
configure_firewall() {
    log_info "Firewall sozlanmoqda..."
    log_warning "Firewall sozlamalari o'tkazib yuborildi."
    log_info "Portlarni qo'lda ochish:"
    echo "  - 5555 (FPANEL panel)"
    echo "  - 80, 443 (HTTP/HTTPS)"
    echo "  - 21 (FTP)"
    echo "  - 22 (SSH)"
    echo "  - 25, 465, 587 (SMTP)"
    echo "  - 110, 995 (POP3)"
    echo "  - 143, 993 (IMAP)"
    echo "  - 53 (DNS)"
}

# Create admin user
create_admin() {
    log_info "Admin foydalanuvchi yaratilmoqda..."
    
    echo ""
    echo "=========================================="
    echo "Admin foydalanuvchi ma'lumotlarini kiriting"
    echo "=========================================="
    echo ""
    
    read -p "Admin username [admin]: " admin_user
    admin_user=${admin_user:-admin}
    
    read -s -p "Admin password: " admin_pass
    echo ""
    
    read -p "Admin email [admin@localhost]: " admin_email
    admin_email=${admin_email:-admin@localhost}
    
    # Hash password
    hashed_pass=$(php -r "echo password_hash('$admin_pass', PASSWORD_BCRYPT);")
    
    # Insert into database
    sqlite3 $FPANEL_DIR/database/fpanel.db << EOF
INSERT OR REPLACE INTO admins (username, password, email, full_name, role, created_at)
VALUES ('$admin_user', '$hashed_pass', '$admin_email', 'Administrator', 'super_admin', datetime('now'));
EOF

    log_success "Admin foydalanuvchi yaratildi"
    echo ""
    echo "Admin login: $admin_user"
    echo "Admin email: $admin_email"
    echo ""
}

# Start services
start_services() {
    log_info "Xizmatlar ishga tushirilmoqda..."
    
    systemctl start fpanel-agent
    systemctl start nginx
    systemctl start php8.2-fpm
    systemctl start mariadb
    systemctl start fail2ban
    
    log_success "Xizmatlar ishga tushirildi"
}

# Print completion message
print_completion() {
    echo ""
    echo "=========================================="
    echo "  FPANEL muvaffaqiyatli o'rnatildi!"
    echo "=========================================="
    echo ""
    echo "O'rnatish katalogi: ${FPANEL_DIR}"
    echo "Panelga kirish: http://$(hostname -I | awk '{print $1}'):5555"
    echo "GitHub: https://github.com/${GITHUB_REPO}"
    echo ""
    echo "Foydali buyruqlar:"
    echo "  systemctl status fpanel-agent  - Agent statusini ko'rish"
    echo "  systemctl restart fpanel-agent - Agentni qayta ishga tushirish"
    echo "  tail -f /var/log/fpanel/agent.log - Loglarni ko'rish"
    echo ""
    echo "Yangilash uchun:"
    echo "  bash <(curl -fsSL ${GITHUB_RAW}/install/install.sh)"
    echo ""
    echo "Eslatma: Xavfsizlik uchun parolni o'zgartiring!"
    echo ""
}

# Main installation function
main() {
    echo "=========================================="
    echo "  FPANEL o'rnatish skripti"
    echo "  GitHub: https://github.com/${GITHUB_REPO}"
    echo "=========================================="
    echo ""
    
    check_root
    detect_os
    update_system
    install_dependencies
    install_python_deps
    create_user
    download_fpanel
    copy_files
    init_database
    configure_nginx
    configure_php
    configure_mysql
    configure_fail2ban
    install_service
    configure_firewall
    create_admin
    start_services
    print_completion
}

# Run main function
main "$@"
