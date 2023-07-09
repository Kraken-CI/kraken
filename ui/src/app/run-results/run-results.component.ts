import { Component, OnInit, ViewChild, OnDestroy } from '@angular/core'
import { Router, ActivatedRoute } from '@angular/router'
import { Title } from '@angular/platform-browser'

import { Subscription } from 'rxjs'

import { MenuItem } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { AuthService } from '../auth.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { Job, Run } from '../backend/model/models'
import { TcrTableComponent } from '../tcr-table/tcr-table.component'
import { pick } from '../utils'

@Component({
    selector: 'app-run-results',
    templateUrl: './run-results.component.html',
    styleUrls: ['./run-results.component.sass'],
})
export class RunResultsComponent implements OnInit, OnDestroy {
    tabs: MenuItem[]
    activeTab: MenuItem
    activeTabIdx = 0
    recordsCount: string[] = ['0', '0', '0', '0']

    projectId = 0

    runId = 0
    run: Run = { state: 'in-progress', tests_passed: 0 }

    refreshTimer: any = null
    refreshing = false

    flatLogsPanelVisible = false

    // jobs
    jobs: Job[]
    totalJobs = 0
    loadingJobs = true
    includeCovered = false

    job: Job
    selectedJobId = 0
    jobData = ''

    // results
    @ViewChild('tcrTable') tcrTable: TcrTableComponent

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

    // artifacts
    artifacts: any[]
    totalArtifacts = 0
    loadingArtifacts = true

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        public auth: AuthService,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
        private titleService: Title
    ) {
        this.issueTypes = [
            { name: 'error', code: 0 },
            { name: 'warning', code: 1 },
            { name: 'convention', code: 2 },
            { name: 'refactor', code: 3 },
        ]
    }

    switchToTab(tabName) {
        for (let idx = 0; idx < this.tabs.length; idx++) {
            if (this.tabs[idx].routerLink.endsWith('/' + tabName)) {
                this.activeTab = this.tabs[idx]
                this.activeTabIdx = idx
                return
            }
        }
    }

    ngOnInit() {
        this.subs.add(
            this.route.paramMap.subscribe((params) => {
                const runId = parseInt(params.get('id'), 10)
                this.run.id = runId

                const tab = params.get('tab')
                if (!tab) {
                    this.router.navigate(['/runs/' + runId + '/jobs'], {
                        replaceUrl: true,
                    })
                    return
                }

                // only when it is the first load or a run is changed
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
                        {
                            label: 'Artifacts',
                            routerLink: '/runs/' + this.runId + '/artifacts',
                        },
                        {
                            label: 'Reports',
                            routerLink: '/runs/' + this.runId + '/reports',
                        },
                        {
                            label: 'Run Details',
                            routerLink: '/runs/' + this.runId + '/details',
                        },
                    ]

                    this.jobs = []
                    this.issues = []
                    this.resetIssuesFilter(null)
                    if (tab === 'jobs') {
                        this.loadJobsLazy({ first: 0, rows: 30 })
                    } else if (tab === 'results') {
                        // it loads on its one I think
                    } else if (tab === 'issues') {
                        this.loadIssuesLazy({ first: 0, rows: 30 })
                    } else if (tab === 'artifacts') {
                        this.loadArtifactsLazy({ first: 0, rows: 30 })
                    }

                    this.subs.add(
                        this.executionService
                            .getRun(this.runId)
                            .subscribe((run) => {
                                this.projectId = run.project_id

                                this.titleService.setTitle(
                                    'Kraken - Run ' +
                                        (run.label || run.stage_name) +
                                        ' ' +
                                        this.runId
                                )
                                this.run = run
                                this.recordsCount[0] = '' + run.jobs_total
                                this.recordsCount[1] =
                                    '' +
                                    run.tests_passed +
                                    ' / ' +
                                    run.tests_total
                                this.recordsCount[2] = '' + run.issues_total
                                this.recordsCount[3] = '' + run.artifacts_total

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
                                        flow_label: run.flow_label,
                                    },
                                    {
                                        label: 'Stages',
                                        run_id: run.id,
                                        run_name: run.stage_name,
                                    },
                                ]
                                this.breadcrumbService.setCrumbs(crumbs)

                                // refresh page data every 5 seconds
                                if (this.refreshTimer === null) {
                                    this.refreshTimer = setTimeout(() => {
                                        this.refreshTimer = null
                                        this.refreshPage()
                                    }, 5000)
                                }
                            })
                    )
                }

                this.switchToTab(tab)
            })
        )
    }

    cancelRefreshTimer() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer)
            this.refreshTimer = null
        }
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
        this.cancelRefreshTimer()
    }

    refreshPage() {
        if (this.refreshing) {
            return
        }
        this.refreshing = true

        switch (this.activeTabIdx) {
            case 0: // jobs
                this.loadJobsLazy({ first: 0, rows: 30 })
                break
            case 1: // results
                this.tcrTable.refreshResults()
                break
            case 2: // issues
                this.loadIssuesLazy({ first: 0, rows: 30 })
                break
            case 3: // artifacts
                this.loadArtifactsLazy({ first: 0, rows: 30 })
                break
            default:
                break
        }

        this.subs.add(
            this.executionService.getRun(this.runId).subscribe((run) => {
                this.refreshing = false
                this.refreshTimer = null

                this.run = run
                this.recordsCount[0] = '' + run.jobs_total
                this.recordsCount[1] =
                    '' + run.tests_passed + ' / ' + run.tests_total
                this.recordsCount[2] = '' + run.issues_total
                this.recordsCount[3] = '' + run.artifacts_total

                // refresh page data every 5 seconds
                if (run.state !== 'processed') {
                    this.refreshTimer = setTimeout(() => {
                        this.refreshTimer = null
                        this.refreshPage()
                    }, 5000)
                }
            })
        )
    }

    prepareJobDataStr() {
        const data = pick(this.job, 'id', 'created', 'name', 'steps')
        this.jobData = JSON.stringify(data, null, 4);
    }

    loadJobsLazy(event) {
        this.loadingJobs = true
        this.subs.add(
            this.executionService
                .getRunJobs(
                    this.runId,
                    event.first,
                    event.rows,
                    this.includeCovered
                )
                .subscribe((data) => {
                    this.jobs = data.items
                    this.totalJobs = data.total

                    // if there are any jobs fetched from the server
                    if (this.jobs.length > 0) {
                        // if job was already selected and assign selected job
                        if (this.selectedJobId) {
                            let foundJob = false
                            for (const job of this.jobs) {
                                if (job.id === this.selectedJobId) {
                                    this.job = job
                                    foundJob = true
                                }
                            }
                            // if selected job was not found in fetched jobs then select the first job
                            if (!foundJob) {
                                this.job = this.jobs[0]
                                this.selectedJobId = this.job.id
                            }
                        } else {
                            // job was not selected yet so select the first job
                            this.job = this.jobs[0]
                            this.selectedJobId = this.job.id
                        }
                        this.prepareJobDataStr()
                    }

                    this.loadingJobs = false
                })
        )
    }

    refreshJobs(jobsTable) {
        jobsTable.onLazyLoad.emit(jobsTable.createLazyLoadMetadata())
    }

    rerunAll() {
        this.subs.add(
            this.executionService.runRunJobs(this.run.id).subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Rerun submitted',
                        detail: 'Rerun operation submitted.',
                    })

                    if (this.refreshTimer === null) {
                        this.refreshTimer = setTimeout(() => {
                            this.refreshTimer = null
                            this.refreshPage()
                        }, 5000)
                    }
                },
                (err) => {
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Rerun erred',
                        detail: 'Rerun operation erred: ' + err.statusText,
                        life: 10000,
                    })
                }
            )
        )
    }

    showCmdLine() {}

    jobSelected(event) {
        this.selectedJobId = event.data.id
    }

    loadIssuesLazy(event) {
        let issueTypes = this.filterIssueTypes.map((e) => e.code)
        if (issueTypes.length === 0) {
            issueTypes = null
        }

        this.loadingIssues = true
        this.subs.add(
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
                .subscribe((data) => {
                    this.issues = data.items
                    this.totalIssues = data.total
                    this.loadingIssues = false
                })
        )
    }

    loadArtifactsLazy(event) {
        this.subs.add(
            this.executionService
                .getRunArtifacts(this.runId, event.first, event.rows)
                .subscribe((data) => {
                    this.artifacts = data.items
                    this.totalArtifacts = data.total
                    this.loadingArtifacts = false
                })
        )
    }

    refreshIssues(issuesTable) {
        issuesTable.onLazyLoad.emit(issuesTable.createLazyLoadMetadata())
    }

    showLastIssuesChanges(issuesTable) {
        this.filterIssueMinAge = 0
        this.filterIssueMaxAge = 0
        this.refreshIssues(issuesTable)
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
            case 8:
                return 'cancel'
            case 9:
                return 'missing group'
            case 10:
                return 'no agents'
            case 11:
                return 'agent not alive'
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
            case 8:
                return 'pi pi-exclamation-circle step-status-red'
            case 9:
                return 'pi pi-exclamation-circle step-status-red'
            case 10:
                return 'pi pi-exclamation-circle step-status-red'
            case 11:
                return 'pi pi-exclamation-circle step-status-red'
            default:
                return ''
        }
    }

    coveredChange(jobsTable) {
        this.refreshJobs(jobsTable)
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

    cancelJob() {
        if (!this.job) {
            return
        }
        this.subs.add(
            this.executionService.deleteJob(this.job.id).subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Job cancelled',
                        detail: 'Cancelling job succeeded.',
                    })
                },
                (err) => {
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Cancel erred',
                        detail: 'Cancelling job erred: ' + err.statusText,
                        life: 10000,
                    })
                }
            )
        )
    }

    rerunJob() {
        this.subs.add(
            this.executionService.jobRerun(this.job.id).subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Job rerun submitted',
                        detail: 'Job rerun operation submitted.',
                    })

                    if (this.refreshTimer === null) {
                        this.refreshTimer = setTimeout(() => {
                            this.refreshTimer = null
                            this.refreshPage()
                        }, 5000)
                    }
                },
                (err) => {
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Job rerun erred',
                        detail: 'Job rerun operation erred: ' + err.statusText,
                        life: 10000,
                    })
                }
            )
        )
    }

    handleJobTabChange(ev) {
        if (ev.index === 1) {
            this.flatLogsPanelVisible = true
        } else {
            this.flatLogsPanelVisible = false
        }
    }
}
