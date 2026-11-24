#!/bin/bash
# Runs ON the instance as root (ec2-up.sh copies it with the files below into /tmp/stage and runs it).
# Safe to re-run. Staged files:
#   admin.pw     admin password (first start only; removed afterwards)
#   license.lic  Splunk Enterprise license
#   app.tgz      control-tower app
#   lookups/*.csv
# Writes the HEC (HTTP Event Collector) token to /tmp/stage/hec.token for ec2-up.sh to fetch.
set -euo pipefail
STAGE=/tmp/stage
SPLUNK=/opt/splunk/bin/splunk
API=https://127.0.0.1:8089
NETRC=$STAGE/.netrc
SPL_STAGE=/opt/splunk/var/run/tuktukpay-stage   # splunkd runs as splunk and cannot read /tmp/stage

[ -x $SPLUNK ] || { echo "Splunk is not unpacked yet (cloud-init still running?)" >&2; exit 1; }

# 1. First start: admin user from user-seed.conf, HTTPS (HyperText Transfer Protocol Secure) for Splunk Web, systemd unit
if [ ! -f /opt/splunk/etc/passwd ]; then
  [ -s $STAGE/admin.pw ] || { echo "no $STAGE/admin.pw for the first start" >&2; exit 1; }
  ( umask 077; { echo "[user_info]"; echo "USERNAME = admin"; printf 'PASSWORD = %s\n' "$(cat $STAGE/admin.pw)"; } > /opt/splunk/etc/system/local/user-seed.conf )
  printf '[settings]\nenableSplunkWebSSL = true\n' > /opt/splunk/etc/system/local/web.conf
  chown -R splunk:splunk /opt/splunk     # everything under SPLUNK_HOME must belong to the splunk user
  $SPLUNK enable boot-start -systemd-managed 1 -user splunk -group splunk --accept-license --answer-yes --no-prompt
  systemctl start Splunkd
fi
systemctl is-active --quiet Splunkd || systemctl start Splunkd
for i in $(seq 60); do curl -sk -o /dev/null $API/services/server/info && break; sleep 5; done

# REST calls authenticate from a netrc file so the password never appears in a process list
[ -s $STAGE/admin.pw ] && ( umask 077; printf 'machine 127.0.0.1 login admin password %s\n' "$(cat $STAGE/admin.pw)" > $NETRC )
[ -s $NETRC ] || { echo "no $NETRC; stage admin.pw again" >&2; exit 1; }
api() { curl -sk --netrc-file $NETRC "$@"; }
code() { curl -sk --netrc-file $NETRC -o /dev/null -w '%{http_code}' "$@"; }
[ "$(code $API/services/authentication/current-context)" = 200 ] || { echo "admin login failed" >&2; exit 1; }

# 2. License (restart only when it was just added)
if [ -s $STAGE/license.lic ] && ! api "$API/services/licenser/licenses?output_mode=json&count=0" | grep -q '"type":"enterprise"'; then
  echo "== adding license"
  install -d -o splunk -g splunk -m 700 $SPL_STAGE
  install -o splunk -g splunk -m 600 $STAGE/license.lic $SPL_STAGE/license.lic
  api -X POST $API/services/licenser/licenses --data-urlencode "name=$SPL_STAGE/license.lic" -o /dev/null
  systemctl restart Splunkd
  for i in $(seq 60); do [ "$(code $API/services/server/info)" = 200 ] && break; sleep 5; done
fi

# 3. Index
if [ "$(code $API/services/data/indexes/tuktukpay)" != 200 ]; then
  echo "== creating index tuktukpay"
  api -X POST $API/services/data/indexes -d name=tuktukpay -o /dev/null
fi

# 4. HEC (HTTP Event Collector): global switch on, one token writing to tuktukpay
api -X POST $API/servicesNS/nobody/splunk_httpinput/data/inputs/http/http -d disabled=0 -d enableSSL=1 -o /dev/null
if [ "$(code $API/servicesNS/nobody/splunk_httpinput/data/inputs/http/tuktukpay)" != 200 ]; then
  echo "== creating HEC token tuktukpay"
  api -X POST $API/servicesNS/nobody/splunk_httpinput/data/inputs/http -d name=tuktukpay -d index=tuktukpay -d indexes=tuktukpay -o /dev/null
fi
api "$API/servicesNS/nobody/splunk_httpinput/data/inputs/http/tuktukpay?output_mode=json" | grep -oE '"token":"[^"]+"' | cut -d'"' -f4 > $STAGE/hec.token
chown ec2-user $STAGE/hec.token

# 5a. Log Observer Connect: role o11y_logs (search + edit_tokens_own, index tuktukpay only, no indexes_list_all),
#     service account o11y_connect, token authentication on (docs/logs-setup.md 1.4)
if [ "$(code $API/services/authorization/roles/o11y_logs)" != 200 ]; then
  echo "== creating role o11y_logs"
  api -X POST $API/services/authorization/roles -d name=o11y_logs -d capabilities=search -d capabilities=edit_tokens_own \
      -d srchIndexesAllowed=tuktukpay -d srchIndexesDefault=tuktukpay -d srchJobsQuota=4 -d rtSrchJobsQuota=0 -d cumulativeSrchJobsQuota=16 \
      -d srchTimeWin=2592000 -o /dev/null
fi
if [ -s $STAGE/o11y_connect.pw ]; then
  if [ "$(code $API/services/authentication/users/o11y_connect)" != 200 ]; then
    echo "== creating user o11y_connect"
    api -X POST $API/services/authentication/users -d name=o11y_connect -d roles=o11y_logs --data-urlencode "password@$STAGE/o11y_connect.pw" -o /dev/null
  fi
  rm -f $STAGE/o11y_connect.pw
fi
api -X POST $API/services/admin/Token-auth/tokens_auth -d disabled=false -o /dev/null

# 5. Control-tower app and lookups
if [ -s $STAGE/app.tgz ]; then
  echo "== installing control-tower app"
  install -d -o splunk -g splunk -m 700 $SPL_STAGE
  install -o splunk -g splunk -m 600 $STAGE/app.tgz $SPL_STAGE/app.tgz
  api -X POST $API/services/apps/local -d filename=true -d update=true --data-urlencode "name=$SPL_STAGE/app.tgz" -o /dev/null
fi
if ls $STAGE/lookups/*.csv >/dev/null 2>&1; then
  install -d -o splunk -g splunk /opt/splunk/etc/apps/search/lookups
  install -o splunk -g splunk -m 644 $STAGE/lookups/*.csv /opt/splunk/etc/apps/search/lookups/
fi

echo "== done: $(api "$API/services/server/info?output_mode=json" | grep -oE '"version":"[^"]+"' | head -1)"
# 6. Clean up secrets on the instance (user-seed.conf is deleted by Splunk itself after first start)
rm -f $STAGE/admin.pw $NETRC $STAGE/license.lic
rm -rf $SPL_STAGE
