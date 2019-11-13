
* DONE triggering jobs
* DONE support for on-demand building/testing from private/developer branch (support for CI and OD/PM)
** DONE split ci/dev
** DONE add submit form for new flow
** DONE add submit form for triggering run
* support repos:
** trigger on commit
** storing commit used
** getting diff to prev job
* executors
** support for docker executor
** support for lxc executor
** support for vagrant executor
** support for bare metal executor
* TODO collect logs to logstash
** DONE add collecting logs
** DONE add presenting logs in UI
** TODO fine tune presenting logs in UI (auto scroll, etc)
* canceling job or run
* nie pozwalać na run stage gdy parent stage nie był jeszcze puszczony
* stage definition files from repo
* artifacts
** integrate Nexus
** implement artifacts tool
* add support for config in job
* add support for system in job
* add handling NOT FOUND when ID in URL is incorrect
