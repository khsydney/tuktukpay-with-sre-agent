#!/bin/bash
# cloud-init for the TukTukPay Splunk Enterprise instance (Amazon Linux 2023, x86_64).
# Downloads and unpacks Splunk only; splunk/ec2/setup-splunk.sh (run over SSH by ec2-up.sh) does the
# first start, because the admin password must not travel in user data.
set -euxo pipefail
URL="https://download.splunk.com/products/splunk/releases/10.6.1.1/linux/splunk-10.6.1.1-b2ae2962645c-linux-amd64.tgz"

hostnamectl set-hostname tuktukpay-splunk
dnf install -y tar

# Splunk warns about transparent huge pages; turn them off now and on every boot
cat > /etc/systemd/system/disable-thp.service <<'EOF'
[Unit]
Description=Disable transparent huge pages for Splunk
Before=Splunkd.service
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled; echo never > /sys/kernel/mm/transparent_hugepage/defrag'
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now disable-thp.service

# Torn down with the EKS cluster on Fri 30 Oct 2026 22:00 (+07) = 15:00 UTC. The instance's shutdown
# behaviour is "terminate", so this power-off deletes it even if k8s/eks-down.sh does not run.
cat > /etc/systemd/system/tuktukpay-teardown.timer <<'EOF'
[Unit]
Description=Terminate the TukTukPay Splunk instance with the EKS cluster
[Timer]
OnCalendar=2026-10-30 15:00:00 UTC
Unit=poweroff.target
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now tuktukpay-teardown.timer

id splunk >/dev/null 2>&1 || useradd -r -m -d /opt/splunk -s /bin/bash splunk
if [ ! -x /opt/splunk/bin/splunk ]; then
  cd /root
  curl -fsSL -o splunk.tgz "$URL"
  curl -fsSL -o splunk.tgz.sha512 "$URL.sha512"
  [ "$(sha512sum splunk.tgz | cut -d' ' -f1)" = "$(grep -oE '[0-9a-f]{128}' splunk.tgz.sha512)" ]
  tar -xzf splunk.tgz -C /opt
  rm -f splunk.tgz splunk.tgz.sha512
  chown -R splunk:splunk /opt/splunk
fi
touch /var/tmp/tuktukpay-splunk-unpacked
