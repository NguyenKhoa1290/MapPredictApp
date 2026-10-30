#!/bin/sh
set -eu
umask 077

# Chrome keeps its own debugger on loopback. socat makes it reachable through
# the container's private network and the host's SSH-only loopback mapping.
# No Google cookie import, credential extraction, stealth or login automation.
chromium \
  --headless=new \
  --no-sandbox \
  --no-first-run \
  --no-default-browser-check \
  --disable-extensions \
  --disable-sync \
  --disable-gpu \
  --renderer-process-limit=2 \
  --user-data-dir=/var/lib/gemini-browser/profile \
  --disk-cache-size=16777216 \
  --media-cache-size=8388608 \
  --window-size=1100,800 \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9223 \
  https://gemini.google.com/app >/tmp/chromium.log 2>&1 &
browser_pid=$!
socat TCP-LISTEN:9222,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:9223 &
bridge_pid=$!

cleanup() {
  kill -TERM "$bridge_pid" "$browser_pid" 2>/dev/null || true
  wait "$browser_pid" 2>/dev/null || true
  wait "$bridge_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' TERM INT
while kill -0 "$browser_pid" 2>/dev/null && kill -0 "$bridge_pid" 2>/dev/null; do
  sleep 2 &
  wait $! || true
done
exit 1
