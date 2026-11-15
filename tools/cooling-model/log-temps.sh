#!/usr/bin/env bash
# Log the Pi's SoC temperature, throttle flags, ARM clock and CPU use for a
# cooling test. Runs on the Pi; CSV rows go to stdout, the summary to stderr.
#
# From the Mac, leaving nothing on the Pi:
#   ssh -4 -o BatchMode=yes -i ~/.ssh/mixpi_ed25519 -o HostKeyAlias=mixxxpi.local \
#     pi@192.168.68.56 'bash -s -- 1800 10' < tools/cooling-model/log-temps.sh \
#     > deploy/cooling-YYYYMMDD/before-sealed.csv
#
# Arguments: [DURATION_S=1800] [INTERVAL_S=10]
# Columns: elapsed_s,time,temp_c,throttled,arm_mhz,load1,cpu_busy_pct
# The model page (tools/cooling-model/index.html) overlays these files.
set -euo pipefail

duration=${1:-1800}
interval=${2:-10}

echo "elapsed_s,time,temp_c,throttled,arm_mhz,load1,cpu_busy_pct"

start=$(date +%s)
prev_total='' prev_idle='' flags=0 rows=''
while :; do
  elapsed=$(( $(date +%s) - start ))
  (( elapsed > duration )) && break
  temp=$(vcgencmd measure_temp | sed -E 's/temp=([0-9.]+).*/\1/')
  throttled=$(vcgencmd get_throttled | cut -d= -f2)
  mhz=$(( $(vcgencmd measure_clock arm | cut -d= -f2) / 1000000 ))
  load1=$(cut -d' ' -f1 /proc/loadavg)
  # All-core CPU busy share since the previous sample
  read -r _ u n s i w q sq st _ < /proc/stat
  total=$(( u + n + s + i + w + q + sq + st )) idle=$(( i + w )) busy=''
  if [[ -n $prev_total ]] && (( total > prev_total )); then
    busy=$(( 100 * ((total - prev_total) - (idle - prev_idle)) / (total - prev_total) ))
  fi
  prev_total=$total prev_idle=$idle
  flags=$(( flags | throttled ))
  row="$elapsed,$(date +%T),$temp,$throttled,$mhz,$load1,$busy"
  echo "$row"
  rows+="$row"$'\n'
  sleep "$interval"
done

printf '%s' "$rows" | awk -F, -v dur="$duration" -v iv="$interval" -v flags="$(printf '0x%x' "$flags")" '
  { n++; t = $3 + 0; if (t > peak) peak = t
    if ($1 >= dur - 600) { last += t; nl++ }
    if (t >= 75) hot += iv
    if ($7 != "") { busy += $7; nb++ } }
  END {
    if (!n) { print "no samples" > "/dev/stderr"; exit 1 }
    printf "samples %d over %.1f min\n", n, (n - 1) * iv / 60 > "/dev/stderr"
    printf "peak %.1f C, mean of the last 10 min %.1f C, at or above 75 C for %.1f min\n", peak, last / (nl ? nl : 1), hot / 60 > "/dev/stderr"
    printf "throttle flags (OR of every sample) %s, mean CPU busy %.0f %% (about %.1f cores)\n", flags, busy / (nb ? nb : 1), busy / (nb ? nb : 1) * 4 / 100 > "/dev/stderr"
  }'
