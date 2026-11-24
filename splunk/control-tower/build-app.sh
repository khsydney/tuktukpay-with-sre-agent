#!/bin/sh
# Assemble the control-tower Splunk app from app-src/ and package it as dist/tuktukpay_control_tower-<version>.tgz
set -e
B="$(cd "$(dirname "$0")" && pwd)"; SRC="$B/app-src"; A="$B/app/tuktukpay_control_tower"
for f in "$SRC"/*.js; do node --check "$f"; done
{ echo "/* TukTukPay control tower — built from splunk/control-tower/app-src; do not edit here */"; echo "(function () {"; for f in "$SRC"/02-core.js "$SRC"/03-charts.js "$SRC"/1*.js; do cat "$f"; echo; done; echo "})();"; } > "$A/appserver/static/tower.js"
node --check "$A/appserver/static/tower.js"
cat "$SRC/01-style.css" "$SRC/90-splunk.css" > "$A/appserver/static/tower.css"
V=$(sed -n "s/^version = //p" "$A/default/app.conf" | head -1)
mkdir -p "$B/dist"; OUT="$B/dist/tuktukpay_control_tower-$V.tgz"
find "$A" -type d -exec chmod 755 {} \; ; find "$A" -type f -exec chmod 644 {} \;
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$OUT" -C "$B/app" --exclude='.DS_Store' tuktukpay_control_tower
echo "built $OUT ($(wc -c < "$OUT") bytes)"
