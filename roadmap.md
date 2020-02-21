
* DONE triggering jobs
* DONE support for on-demand building/testing from private/developer branch (support for CI and OD/PM)
** DONE split ci/dev
** DONE add submit form for new flow
** DONE add submit form for triggering run
* DONE collect logs to logstash
** DONE add collecting logs
** DONE add presenting logs in UI
** DONE fine tune presenting logs in UI (auto scroll, etc)
* DONE prod deployment preparation
** DONE ??? combine planner and scheduler in 1 process
**
* DONE new project
* DONE filtrowanie po age na stronie issues
* DONE zrobić dynamiczne menu w breadcrumbie (kliknięcie powoduje dynamiczne załadowanie pozycji do menu)
* DONE dodać statsy o zmianach do run-box'a
* DONE dodać automatyczne wyznaczanie timeout'u
* DONE .dockerignore dla build ui
* DONE executors
** DONE add groups, discovered
** DONE support for docker executor
** DONE support for bare metal executor
* DONE add monitoring executors in watchdog with timeout 10mins
* DONE timeout for whole run
* DONE przerobić stronę główną na bardziej statyczną bez rozwijanego drzewa
* DONE czas na branchu jest pokazywany jako AM a jest PM
* DONE local_run nie zapisuje do logstash'a
* DONE do not count issues in run.get_json(), do this at the end of run
* support repos:
** trigger on commit
** DONE trigger on github push event
** storing commit used
** getting git diff to prev job
* TODO support for lxd executor
* canceling job or run
* nie pozwalać na run stage gdy parent stage nie był jeszcze puszczony
* stage definition files from repo
* TODO artifacts
** integrate Nexus
** implement artifacts tool
** DONE artifacts on FTP
* add support for config in job
* add support for system in job
* add handling NOT FOUND when ID in URL is incorrect
* kraken_shell: clearly report timeout errors
* fork branch operation with test results history continuity
* jak sie wywali poprzedni stage to nie startować następnego
* show OS instead of hardcoded Ubuntu 18.04
* add links to executors and groups on run page and everywhere else
* improve auto refreshing of run page
* add reruning single job
