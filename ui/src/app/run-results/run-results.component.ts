import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'

import { MenuItem } from 'primeng/api'

import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { TestCaseResults } from '../test-case-results'
import { Job, Run } from '../backend/model/models'

@Component({
    selector: 'app-run-results',
    templateUrl: './run-results.component.html',
    styleUrls: ['./run-results.component.sass'],
})
export class RunResultsComponent implements OnInit {
    tabs: MenuItem[]
    activeTab: MenuItem
    activeTabIdx = 0
    recordsCount: string[] = ['0', '0', '0']

    runId = 0
    run: Run = { tests_passed: 0 }

    // jobs
    jobs: Job[]
    totalJobs = 0
    loadingJobs = true
    includeCovered = false

    job: Job
    selectedJobId = 0

    // results
    results: any[]
    totalResults = 0
    loadingResults = true
    resultStatuses: any[]
    filterStatuses: any[] = []
    resultChanges: any[]
    filterChanges: any[] = []
    filterMinAge = 0
    filterMaxAge = 1000
    filterMinInstability = 0
    filterMaxInstability = 10
    filterTestCaseText = ''
    filterResultJob = ''

    // issues
    issues: any[]
    totalIssues = 0
    loadingIssues = true
    issueTypes: any[]
    filterIssueTypes: any[] = []
    filterIssueLocation = ''
    filterIssueMessage = ''
    filterIssueSymbol = ''
    filterIssueMinAge = 0
    filterIssueMaxAge = 1000
    filterIssueJob = ''

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService
    ) {
        this.resultStatuses = [
            { name: 'Not Run', code: 0 },
            { name: 'Passed', code: 1 },
            { name: 'Failed', code: 2 },
            { name: 'Error', code: 3 },
            { name: 'Disabled', code: 4 },
            { name: 'Unsupported', code: 5 },
        ]

        this.resultChanges = [
            { name: 'No changes', code: 0 },
            { name: 'Fixes', code: 1 },
            { name: 'Regressions', code: 2 },
            { name: 'New', code: 3 },
        ]

        this.issueTypes = [
            { name: 'error', code: 0 },
            { name: 'warning', code: 1 },
            { name: 'convention', code: 2 },
            { name: 'refactor', code: 3 },
        ]
    }

    switchToTab(tabName) {
        let idx = 0
        if (tabName === 'results') {
            idx = 1
        } else if (tabName === 'issues') {
            idx = 2
        }
        this.activeTab = this.tabs[idx]
        this.activeTabIdx = idx
    }

    ngOnInit() {
        this.route.paramMap.subscribe(params => {
            const runId = parseInt(params.get('id'), 10)

            const tab = params.get('tab')
            if (tab === '') {
                this.router.navigate(['/runs/' + runId + '/jobs'])
                return
            }

            if (runId !== this.runId) {
                this.runId = runId

                this.tabs = [
                    {
                        label: 'Jobs',
                        routerLink: '/runs/' + this.runId + '/jobs',
                    },
                    {
                        label: 'Test Results',
                        routerLink: '/runs/' + this.runId + '/results',
                    },
                    {
                        label: 'Issues',
                        routerLink: '/runs/' + this.runId + '/issues',
                    },
                ]

                this.jobs = []
                this.results = []
                this.resetResultsFilter(null)
                this.issues = []
                this.resetIssuesFilter(null)
                if (tab === 'jobs') {
                    this.loadJobsLazy({ first: 0, rows: 30 })
                } else if (tab === 'results') {
                    this.loadResultsLazy({ first: 0, rows: 30 })
                } else if (tab === 'issues') {
                    this.loadIssuesLazy({ first: 0, rows: 30 })
                }

                this.executionService.getRun(this.runId).subscribe(run => {
                    this.run = run
                    this.recordsCount[0] = '' + run.jobs_total
                    this.recordsCount[1] =
                        '' + run.tests_passed + ' / ' + run.tests_total
                    this.recordsCount[2] = '' + run.issues_total

                    const crumbs = [
                        {
                            label: 'Projects',
                            project_id: run.project_id,
                            project_name: run.project_name,
                        },
                        {
                            label: 'Branches',
                            branch_id: run.branch_id,
                            branch_name: run.branch_name,
                        },
                        {
                            label: 'Results',
                            branch_id: run.branch_id,
                            flow_kind: run.flow_kind,
                        },
                        {
                            label: 'Flows',
                            flow_id: run.flow_id,
                        },
                        {
                            label: 'Stages',
                            run_id: run.id,
                            run_name: run.name,
                        },
                    ]
                    this.breadcrumbService.setCrumbs(crumbs)
                })
            }

            this.switchToTab(tab)
        })
    }

    formatResult(result) {
        return TestCaseResults.formatResult(result)
    }

    resultToTxt(result) {
        return TestCaseResults.resultToTxt(result)
    }

    resultToClass(result) {
        return 'result' + result
    }

    loadResultsLazy(event) {
        let statuses = this.filterStatuses.map(e => e.code)
        if (statuses.length === 0) {
            statuses = null
        }
        let changes = this.filterChanges.map(e => e.code)
        if (changes.length === 0) {
            changes = null
        }

        this.loadingResults = true
        this.executionService
            .getRunResults(
                this.runId,
                event.first,
                event.rows,
                statuses,
                changes,
                this.filterMinAge,
                this.filterMaxAge,
                this.filterMinInstability,
                this.filterMaxInstability,
                this.filterTestCaseText,
                this.filterResultJob
            )
            .subscribe(data => {
                this.results = data.items
                this.totalResults = data.total
                this.loadingResults = false
            })
    }

    refreshResults(resultsTable) {
        resultsTable.onLazyLoad.emit(resultsTable.createLazyLoadMetadata())
    }

    loadJobsLazy(event) {
        this.loadingJobs = true
        this.executionService
            .getRunJobs(
                this.runId,
                event.first,
                event.rows,
                this.includeCovered
            )
            .subscribe(data => {
                this.jobs = data.items
                this.totalJobs = data.total

                if (this.jobs.length > 0) {
                    this.job = this.jobs[0]
                    this.selectedJobId = this.job.id
                }

                this.loadingJobs = false
            })
    }

    refreshJobs(jobsTable) {
        jobsTable.onLazyLoad.emit(jobsTable.createLazyLoadMetadata())
    }

    showCmdLine() {}

    jobSelected(event) {
        this.selectedJobId = event.data.id
    }

    loadIssuesLazy(event) {
        let issueTypes = this.filterIssueTypes.map(e => e.code)
        if (issueTypes.length === 0) {
            issueTypes = null
        }

        this.loadingIssues = true
        this.executionService
            .getRunIssues(
                this.runId,
                event.first,
                event.rows,
                issueTypes,
                this.filterIssueLocation,
                this.filterIssueMessage,
                this.filterIssueSymbol,
                this.filterIssueMinAge,
                this.filterIssueMaxAge,
                this.filterIssueJob
            )
            .subscribe(data => {
                this.issues = data.items
                this.totalIssues = data.total
                this.loadingIssues = false
            })
    }

    refreshIssues(issuesTable) {
        issuesTable.onLazyLoad.emit(issuesTable.createLazyLoadMetadata())
    }

    issueTypeToClass(issueType) {
        return ''
    }

    issueTypeToTxt(issueType) {
        switch (issueType) {
            case 0:
                return 'error'
            case 1:
                return 'warning'
            case 2:
                return 'convention'
            case 3:
                return 'refactor'
        }
        return 'unknown'
    }

    getJobState(job) {
        switch (job.state) {
            case 1:
                return 'prequeued'
            case 2:
                return 'queued'
            case 3:
                return 'assigned'
            case 4:
                return 'executing-finished'
            case 5:
                return 'completed'
        }
    }

    getJobStatus(job) {
        switch (job.completion_status) {
            case 0:
                return 'all ok'
            case 1:
                return 'timeout'
            case 2:
                return 'error'
            case 3:
                return 'exception'
            case 4:
                return 'missing tool in db'
            case 5:
                return 'missing tool files'
            case 6:
                return 'step timeout'
            case 7:
                return 'timeout'
            default:
                return ''
        }
    }

    getJobStatusClass(job) {
        switch (job.completion_status) {
            case 0:
                return 'pi pi-check-circle step-status-green'
            case 1:
                return 'pi pi-exclamation-circle step-status-red'
            case 2:
                return 'pi pi-exclamation-circle step-status-red'
            case 3:
                return 'pi pi-exclamation-circle step-status-red'
            case 4:
                return 'pi pi-exclamation-circle step-status-red'
            case 5:
                return 'pi pi-exclamation-circle step-status-red'
            case 6:
                return 'pi pi-exclamation-circle step-status-red'
            case 7:
                return 'pi pi-exclamation-circle step-status-red'
            default:
                return ''
        }
    }

    getStepStatus(step) {
        switch (step.status) {
            case null:
                return 'not started'
            case 0:
                return 'not started'
            case 1:
                return 'in progress'
            case 2:
                return 'done'
            case 3:
                return 'error'
            default:
                return 'unknown'
        }
    }

    getStepStatusClass(step) {
        switch (step.status) {
            case 0:
                return 'not started'
            case 1:
                return 'pi pi-spin pi-spinner'
            case 2:
                return 'pi pi-check-circle step-status-green'
            case 3:
                return 'pi pi-exclamation-circle step-status-red'
            default:
                return ''
        }
    }

    coveredChange() {}

    getResultChangeTxt(change) {
        switch (change) {
            case 0:
                return ''
            case 1:
                return 'FIX'
            case 2:
                return 'REGR'
            case 3:
                return 'NEW'
            default:
                return 'UNKN'
        }
    }

    getResultChangeCls(change) {
        switch (change) {
            case 1:
                return 'result-fix'
            case 2:
                return 'result-regr'
            case 3:
                return 'result-new'
            default:
                return ''
        }
    }

    resetResultsFilter(resultsTable) {
        this.filterStatuses = []
        this.filterChanges = []
        this.filterMinAge = 0
        this.filterMaxAge = 1000
        this.filterMinInstability = 0
        this.filterMaxInstability = 10

        if (resultsTable) {
            this.refreshResults(resultsTable)
        }
    }

    filterResultsKeyDown(event, resultsTable) {
        if (event.key === 'Enter') {
            this.refreshResults(resultsTable)
        }
    }

    filterIssuesKeyDown(event, issuesTable) {
        if (event.key === 'Enter') {
            this.refreshIssues(issuesTable)
        }
    }

    resetIssuesFilter(issuesTable) {
        this.filterIssueTypes = []
        this.filterIssueLocation = ''
        this.filterIssueMessage = ''
        this.filterIssueSymbol = ''
        this.filterIssueMinAge = 0
        this.filterIssueMaxAge = 1000
        this.filterIssueJob = ''

        if (issuesTable) {
            this.refreshIssues(issuesTable)
        }
    }

    filterIssuesBySymbol(symbol, issuesTable) {
        this.filterIssueSymbol = symbol
        this.refreshIssues(issuesTable)
    }

    filterIssuesByAge(age, issuesTable) {
        this.filterIssueMinAge = age
        this.filterIssueMaxAge = age
        this.refreshIssues(issuesTable)
    }

    filterIssuesByType(issueType, issuesTable) {
        this.filterIssueTypes = [
            { code: issueType, name: this.issueTypeToTxt(issueType) },
        ]
        this.refreshIssues(issuesTable)
    }
}
