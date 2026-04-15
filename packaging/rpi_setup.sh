#!/usr/bin/env bash
# packaging/rpi_setup.sh — bootstrap Raspberry Pi OS (64-bit Bookworm) for SleepSense AI
# Run: sudo bash packaging/rpi_setup.sh
set -euo pipefail

INSTALL_USER="${SUDO_USER:-pi}"
REPO_DIR="${SLEEPSENSE_HOME:-/home/${INSTALL_USER}/sleepsense-ai}"

echo "=== SleepSense AI RPi Setup (user=${INSTALL_USER}, repo=${REPO_DIR}) ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-pip python3-venv git mosquitto mosquitto-clients redis-server nginx curl

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Clone your fork into ${REPO_DIR} (adjust URL):"
  echo "  sudo -u \"${INSTALL_USER}\" git clone https://github.com/your-org/sleepsense-ai.git \"$REPO_DIR\""
  echo "Then re-run this script or continue manually."
  exit 1
fi

sudo -u "$INSTALL_USER" python3 -m venv "${REPO_DIR}/.venv"
sudo -u "$INSTALL_USER" "${REPO_DIR}/.venv/bin/pip" install -U pip
sudo -u "$INSTALL_USER" "${REPO_DIR}/.venv/bin/pip" install -r "${REPO_DIR}/api/requirements_api.txt"
sudo -u "$INSTALL_USER" "${REPO_DIR}/.venv/bin/pip" install -r "${REPO_DIR}/hardware/requirements_rpi.txt"

if [[ ! -f "${REPO_DIR}/.env" ]]; then
  sudo -u "$INSTALL_USER" cp "${REPO_DIR}/.env.example" "${REPO_DIR}/.env"
  echo "EDGE_DEVICE=raspberry_pi_5" | sudo -u "$INSTALL_USER" tee -a "${REPO_DIR}/.env" >/dev/null
fi

install -m 644 "${REPO_DIR}/packaging/sleepsense-api.service" /etc/systemd/system/sleepsense-api.service
install -m 644 "${REPO_DIR}/packaging/sleepsense-worker.service" /etc/systemd/system/sleepsense-worker.service
install -m 644 "${REPO_DIR}/hardware/sleepsense-recorder.service" /etc/systemd/system/sleepsense-recorder.service

sed -i "s|/home/pi/sleepsense-ai|${REPO_DIR}|g" /etc/systemd/system/sleepsense-api.service
sed -i "s|/home/pi/sleepsense-ai|${REPO_DIR}|g" /etc/systemd/system/sleepsense-worker.service
sed -i "s|/home/pi/sleepsense-ai|${REPO_DIR}|g" /etc/systemd/system/sleepsense-recorder.service
sed -i "s|User=pi|User=${INSTALL_USER}|g" /etc/systemd/system/sleepsense-api.service
sed -i "s|User=pi|User=${INSTALL_USER}|g" /etc/systemd/system/sleepsense-worker.service
sed -i "s|User=pi|User=${INSTALL_USER}|g" /etc/systemd/system/sleepsense-recorder.service

systemctl daemon-reload
systemctl enable mosquitto redis-server
systemctl enable sleepsense-api sleepsense-worker sleepsense-recorder || true
systemctl restart mosquitto redis-server
systemctl restart sleepsense-api sleepsense-worker || true

sudo -u "$INSTALL_USER" mkdir -p "${REPO_DIR}/datasets" "${REPO_DIR}/artifacts"
chown -R "${INSTALL_USER}:${INSTALL_USER}" "$REPO_DIR"

echo "=== Setup complete ==="
echo "API docs: http://$(hostname -I | awk '{print $1}'):8000/docs"
