#!/bin/bash
exec > /var/log/cumminsiq-setup.log 2>&1

# Install only what we need (skip full OS update for speed)
dnf install -y python3 python3-pip git

# Clone repo
cd /home/ec2-user
git clone https://github.com/rajeshgohad/CumminsIQ.git
chown -R ec2-user:ec2-user CumminsIQ

# Install Python deps as ec2-user
sudo -u ec2-user pip3 install --user fastapi==0.115.0 "uvicorn[standard]==0.30.0" websockets==12.0 pydantic==2.8.0

# Systemd service
cat > /etc/systemd/system/cumminsiq.service << 'SVCEOF'
[Unit]
Description=CumminsIQ FastAPI Backend
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/CumminsIQ/backend
ExecStart=/home/ec2-user/.local/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
Environment=ALLOWED_ORIGINS=*
Environment=HOME=/home/ec2-user

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable cumminsiq
systemctl start cumminsiq

echo "Setup complete at $(date)"
