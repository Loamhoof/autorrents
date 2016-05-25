transmission-remote -l | grep Done | grep -oP "\d+(?= +100%)" | xargs -n 1 -I % transmission-remote  -t% -r
