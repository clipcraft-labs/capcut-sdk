#!/bin/sh
set -eu
video=${1:?usage: ./verify-render.sh OUTPUT.mp4}
probe=$(ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,nb_frames \
  -of default=noprint_wrappers=1 "$video")
printf '%s\n' "$probe"
printf '%s\n' "$probe" | grep -q '^width=1080$'
printf '%s\n' "$probe" | grep -q '^height=1920$'
printf '%s\n' "$probe" | grep -q '^r_frame_rate=30/1$'
printf '%s\n' "$probe" | grep -q '^nb_frames=450$'
echo "PASS: 1080x1920, 30 fps, 450 frames"

if [ "$#" -ge 2 ]; then
  baseline=$2
  stats=${TMPDIR:-/tmp}/clipcraft-effect-ssim.$$.log
  trap 'rm -f "$stats"' EXIT
  ffmpeg -hide_banner -loglevel error -i "$video" -i "$baseline" \
    -lavfi "[0:v][1:v]ssim=stats_file=$stats" -f null -
  summary=$(awk -F' ' '
    { all=1; for(i=1;i<=NF;i++) if($i ~ /^All:/){split($i,a,":"); all=a[2]} }
    all < 0.999999 {count++; if(first=="") first=NR-1; last=NR-1; sum+=all}
    END {printf "%d %d %d %.8f",count,first,last,sum/count}
  ' "$stats")
  echo "effect diff: $summary (changed first last mean_ssim)"
  set -- $summary
  [ "$1" -eq 50 ] && [ "$2" -eq 211 ] && [ "$3" -eq 260 ]
  echo "PASS: exact-ID effect changed only the measured 50-frame window"
fi
