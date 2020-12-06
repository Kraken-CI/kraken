set-option -g mouse on

selectp -t 0

# storage
splitw -v  -p 50
send-keys 'rake run_storage' Enter

# ui
splitw -h -p 50
send-keys 'rake serve_ui' Enter

selectp -t 1

# watchdog
splitw -h -p 50
send-keys 'rake run_watchdog' Enter

selectp -t 3

# ELK
splitw -h -p 50
send-keys 'rake run_ch' Enter

selectp -t 0

# scheduler
splitw -h -p 50
send-keys 'rake run_scheduler' Enter

#
splitw -h -p 50
send-keys 'rake run_planner' Enter

selectp -t 0

#
splitw -h -p 50
send-keys 'rake run_celery' Enter

selectp -t 0
send-keys 'rake run_server' Enter
