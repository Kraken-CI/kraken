import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {MenuItem} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { TestCaseResults } from '../test-case-results';
import { Job } from '../backend/model/models';


@Component({
  selector: 'app-run-results',
  templateUrl: './run-results.component.html',
  styleUrls: ['./run-results.component.sass']
})
export class RunResultsComponent implements OnInit {

    tabs: MenuItem[]
    activeTab: MenuItem

    runId = 0;
    results: any[];
    totalRecords = 0;
    loading = false;

    jobs: Job[]
    totalJobs = 0
    loadingJobs = false

    job: Job
    logFragments: any[]
    skippedAngLoadedLogs = 0

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    switchToTab(tabLabel) {
        for (let t of this.tabs) {
            if (t.label.toLowerCase() === tabLabel.toLowerCase() && this.activeTab.label !== t.label) {
                this.activeTab = t
                break
            }
        }
    }

    ngOnInit() {
        this.runId = parseInt(this.route.snapshot.paramMap.get("id"));
        let tab = this.route.snapshot.paramMap.get("tab");

        this.tabs = [
            {label: 'Results', routerLink: '/runs/' + this.runId + '/results'},
            {label: 'Jobs', routerLink: '/runs/' + this.runId + '/jobs'},
        ]
        this.activeTab = this.tabs[0]
        if (tab === 'jobs') {
            this.activeTab = this.tabs[1]
        }

        this.route.paramMap.subscribe(params => {
            let newTab = params.get("tab");
            if (newTab) {
                this.switchToTab(newTab)
            }
        })

        this.breadcrumbService.setCrumbs([{
            label: 'Stages',
            url: '/runs/' + this.runId,
            id: this.runId
        }]);

        this.results = [];
        this.executionService.getRun(this.runId).subscribe(run => {
            if (run.state !== 'completed') {
                this.tabs = [
                    {label: 'Jobs', routerLink: '/runs/' + this.runId + '/jobs'},
                    {label: 'Results', routerLink: '/runs/' + this.runId + '/results'},
                ]
            }
            this.switchToTab(this.activeTab.label)

            let crumbs = [{
                label: 'Projects',
                url: '/projects/' + run.project_id,
                id: run.project_name
            }, {
                label: 'Branches',
                url: '/branches/' + run.branch_id,
                id: run.branch_name
            }, {
                label: 'Results',
                url: '/branches/' + run.branch_id + '/' + run.flow_kind,
                id: run.flow_kind,
                items: [{
                    label: 'CI',
                    routerLink: '/branches/' + run.branch_id + '/ci'
                }, {
                    label: 'dev',
                    routerLink: '/branches/' + run.branch_id + '/dev'
                }]
            }, {
                label: 'Flows',
                url: '/flows/' + run.flow_id,
                id: run.flow_id
            }, {
                label: 'Stages',
                url: '/runs/' + run.id,
                id: run.name
            }];
            this.breadcrumbService.setCrumbs(crumbs);
        });
    }

    formatResult(result) {
        return TestCaseResults.formatResult(result);
    }

    resultToTxt(result) {
        return TestCaseResults.resultToTxt(result);
    }

    resultToClass(result) {
        return 'result' + result;
    }

    loadResultsLazy(event) {
        this.executionService.getRunResults(this.runId, event.first, event.rows).subscribe(data => {
            this.results = data.items;
            this.totalRecords = data.total;
        });
    }

    showCmdLine() {
    }

    loadJobsLazy(event) {
        this.executionService.getRunJobs(this.runId, event.first, event.rows).subscribe(data => {
            this.jobs = data.items
            this.totalJobs = data.total

            this.job = this.jobs[0]
            this.loadJobLogs(this.job.id)
        })
    }

    _prepareLogs(logs) {
        let step = null
        let fragment = null
        if (this.logFragments.length > 0) {
            if (this.logFragments[this.logFragments.length - 1].loading) {
                this.logFragments.splice(this.logFragments.length - 1, 1)
            }
            fragment = this.logFragments[this.logFragments.length - 1]
        }
        for (let l of logs) {
            if (fragment === null) {
                let title = ''
                if (l.step !== undefined) {
                    step = l.step
                    title = l.tool
                }
                fragment = {
                    title: title,
                    expanded: true,
                    logs: [],
                }
                this.logFragments.push(fragment)
            } else {
                if (l.step !== step) {
                    let title = ''
                    step = l.step
                    if (l.step !== undefined) {
                        title = l.tool
                    }
                    fragment = {
                        title: title,
                        expanded: true,
                        logs: [],
                    }
                    this.logFragments.push(fragment)
                }
            }
            if (fragment.title === '' && l.tool !== '') {
                fragment.title = l.tool
            }
            l['style'] = {}
            if (l.message.includes('ERRO') || l.level === 'ERROR') {
                l['style'] = {color: 'red'}
            }
            fragment.logs.push(l)
        }
    }

    _addLoadingMoreEntryToLogs() {
        this.logFragments.push({
            title: '',
            expanded: true,
            loading: true,
            logs: [{
                message: '... loading more ...',
                style: {}
            }]
        })
    }

    _processNewLogs(data, skippedLogsCount) {
        console.info(data)
        if (skippedLogsCount > 0) {
            this.logFragments.push({
                title: '',
                expanded: true,
                logs: [{
                    message: '... skipped ' + skippedLogsCount + ' lines ...',
                    style: {}
                }]
            })
        }
        this._prepareLogs(data.items.reverse())

        if (data.job.state != 5) {  // completed
            this._addLoadingMoreEntryToLogs()
        }
    }

    _processNextLogs(jobId, data) {
        console.info('loaded next ' + data.items.length + ' of ' + data.total)
        this.skippedAngLoadedLogs += data.items.length

        if (data.items.length === 0) {
            if (data.job.state === 5) {
                console.info('completed loading')
                // TODO: remove loading more entry
            } else {
                // nothing loaded but still running then wait 3 seconds and then load more
                console.info('nothing loaded but still running then wait 3 seconds and then load more')
                setTimeout(() => {
                    this.executionService.getJobLogs(jobId, this.skippedAngLoadedLogs, 200, 'asc').subscribe(data2 => {
                        this._processNextLogs(jobId, data2)
                    })
                }, 3000);
                return
            }
        }

        // TODO: glue fragments
        this._prepareLogs(data.items)

        if (this.skippedAngLoadedLogs < data.total) {
            // load the rest immediatelly
            let num = data.total - this.skippedAngLoadedLogs
            if (num > 1000) {
                num = 1000
            }
            console.info('load the rest ' + num + ' immediatelly')
            this.executionService.getJobLogs(jobId, this.skippedAngLoadedLogs, num, 'asc').subscribe(data2 => {
                this._processNextLogs(jobId, data2)
            })
        } else if (data.job.state != 5) {
            this._addLoadingMoreEntryToLogs()
            // wait for next logs 3 seconds
            console.info('wait for next logs 3 seconds')
            setTimeout(() => {
                this.executionService.getJobLogs(jobId, this.skippedAngLoadedLogs, 200, 'asc').subscribe(data2 => {
                    this._processNextLogs(jobId, data2)
                })
            }, 3000);
            return
        } else {
            console.info('completed loading at next shot')
        }
    }

    loadJobLogs(jobId) {
        console.info('loading logs for ', jobId)
        this.logFragments = []
        this.executionService.getJobLogs(jobId, 0, 200, 'desc').subscribe(data => {
            console.info('loaded first ' + data.items.length + ' of ' + data.total)
            this.skippedAngLoadedLogs = data.total

            this._processNewLogs(data, data.total - 200)

            if (data.job.state != 5) {  // completed
                // wait for next logs 3 seconds
                console.info('waiting for next logs 3 seconds')
                setTimeout(() => {
                    this.executionService.getJobLogs(jobId, this.skippedAngLoadedLogs, 200, 'asc').subscribe(data2 => {
                        this._processNextLogs(jobId, data2)
                    })
                }, 3000);
            } else {
                console.info('completed loading at first shot')
            }
        })
    }

    jobSelected(event) {
        this.loadJobLogs(event.data.id)
    }
}
