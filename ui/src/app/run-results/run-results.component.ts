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

    runId = 0
    results: any[]
    totalResults = 0
    loadingResults = false

    jobs: Job[]
    totalJobs = 0
    loadingJobs = false
    includeCovered = false

    job: Job
    selectedJobId = 0

    issues: any[]
    totalIssues = 0
    loadingIssues = false

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    switchToTab(tabName) {
        let idx = 0
        if (tabName === 'results') {
            idx = 1
        } else if (tabName === 'issues') {
            idx = 2
        }
        this.activeTab = this.tabs[idx]
    }

    ngOnInit() {
        this.runId = parseInt(this.route.snapshot.paramMap.get("id"));

        this.tabs = [
            {label: 'Jobs', routerLink: '/runs/' + this.runId + '/jobs'},
            {label: 'Test Results', routerLink: '/runs/' + this.runId + '/results'},
            {label: 'Issues', routerLink: '/runs/' + this.runId + '/issues'},
        ]

        let tab = this.route.snapshot.paramMap.get("tab");
        this.switchToTab(tab)

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
            let tab = this.route.snapshot.paramMap.get("tab");
            if (tab === '') {
                if (run.state === 'completed') {
                    this.router.navigate([this.tabs[1].routerLink]);
                } else {
                    this.router.navigate([this.tabs[0].routerLink]);
                }
            }

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
            this.totalResults = data.total;
        });
    }

    loadJobsLazy(event) {
        this.executionService.getRunJobs(this.runId, event.first, event.rows, this.includeCovered).subscribe(data => {
            this.jobs = data.items
            this.totalJobs = data.total

            this.job = this.jobs[0]
            this.selectedJobId = this.job.id
        })
    }

    refreshJobs(jobsTable) {
        jobsTable.onLazyLoad.emit(jobsTable.createLazyLoadMetadata())
    }

    showCmdLine() {
    }

    jobSelected(event) {
        this.selectedJobId = event.data.id
    }

    loadIssuesLazy(event) {
        this.executionService.getRunIssues(this.runId, event.first, event.rows).subscribe(data => {
            this.issues = data.items
            this.totalIssues = data.total
        });
    }

    issueTypeToClass(issue_type) {
        return ''
    }

    issueTypeToTxt(issue_type) {
        switch (issue_type) {
        case 0: return 'error'
        case 1: return 'warning'
        case 2: return 'convention'
        case 3: return 'refactor'
        }
        return 'unknown'
    }

    getJobState(job) {
        switch (job.state) {
        case 1: return 'prequeued'
        case 2: return 'queued'
        case 3: return 'assigned'
        case 4: return 'executing-finished'
        case 5: return 'completed'
        }
    }

    getJobStatus(job) {
        switch (job.completion_status) {
        case 0: return 'all ok'
        case 1: return 'timeout'
        case 2: return 'error'
        case 3: return 'exception'
        case 4: return 'missing tool in db'
        case 5: return 'missing tool files'
        case 6: return 'step timeout'
        default: return ''
        }
    }

    getJobStatusClass(job) {
        switch (job.completion_status) {
        case 0: return 'pi pi-check-circle step-status-green'
        case 1: return 'pi pi-exclamation-circle step-status-red'
        case 2: return 'pi pi-exclamation-circle step-status-red'
        case 3: return 'pi pi-exclamation-circle step-status-red'
        case 4: return 'pi pi-exclamation-circle step-status-red'
        case 5: return 'pi pi-exclamation-circle step-status-red'
        case 6: return 'pi pi-exclamation-circle step-status-red'
        default: return ''
        }
    }

    getStepStatus(step) {
        switch (step.status) {
        case null: return 'not started'
        case 0: return 'not started'
        case 1: return 'in progress'
        case 2: return 'done'
        case 3: return 'error'
        default: return 'unknown'
        }
    }

    getStepStatusClass(step) {
        switch (step.status) {
        case 0: return 'not started'
        case 1: return 'pi pi-spin pi-spinner'
        case 2: return 'pi pi-check-circle step-status-green'
        case 3: return 'pi pi-exclamation-circle step-status-red'
        default: return ''
        }
    }

    coveredChange() {
    }
}
