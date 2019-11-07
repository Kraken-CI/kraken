
* DONE triggering jobs
* support repos:
** trigger on commit
** storing commit used
** getting diff to prev job
* executors
** support for docker executor
** support for lxc executor
** support for vagrant executor
** support for bare metal executor
* collect logs to logstash
* support for on-demand building/testing from private/developer branch (support for CI and OD/PM)
** DONE split ci/dev
** DONE add submit form for new flow
** TODO add submit form for triggering run
* canceling job or run
* nie pozwalać na run stage gdy parent stage nie był jeszcze puszczony
* stage definition files from repo
* artifacts
** integrate Nexus
** implement artifacts tool
