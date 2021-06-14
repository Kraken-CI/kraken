set-option -g mouse on
set-option -g pane-border-status bottom
set-option -g allow-rename off

rename-window '... ui server sched rq qneck ...'

# ui
splitw -h -p 50
selectp -t 0
send-keys 'rake serve_ui' Enter
select-pane -T UI

# server
splitw -v -p 50
selectp -t 1
send-keys 'rake run_server' Enter
select-pane -T SERVER

# rq
selectp -t 2
splitw -v -p 33
send-keys 'rake run_rq' Enter
select-pane -T RQ

# qneck
selectp -t 2
splitw -v -p 50
send-keys 'rake run_qneck' Enter
select-pane -T QNECK

# scheduler
selectp -t 2
send-keys 'rake run_scheduler' Enter
select-pane -T SCHEDULER

####################################
new-window -n '... planner wdg minio clickhouse ...'

# planner
splitw -h -p 50
selectp -t 0
send-keys 'rake run_planner' Enter
select-pane -T PLANNER

# watchdog
splitw -v -p 50
send-keys 'rake run_watchdog' Enter
select-pane -T WATCHDOG

# minio
selectp -t 2
splitw -v  -p 50
send-keys 'rake run_minio' Enter
select-pane -T MINIO

# clickhouse
selectp -t 2
send-keys 'rake run_ch' Enter
select-pane -T CLICKHOUSE

####################################
new-window -n '... agents ...'

# agent local
splitw -v -p 30
selectp -t 0
send-keys 'rake run_agent' Enter
select-pane -T 'AGENT LOCAL'

# agent in docker
selectp -t 1
splitw -v -p 50
selectp -t 1
send-keys 'rake run_agent_in_docker'
select-pane -T 'AGENT DOCKER'

# agent in lxd
selectp -t 2
send-keys 'rake run_agent_in_lxd'
select-pane -T 'AGENT LXD'

####################################
select-window -t 0
