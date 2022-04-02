import { Component, OnInit, OnDestroy } from '@angular/core'
import { Title } from '@angular/platform-browser'
import { ActivatedRoute } from '@angular/router'

import { Subscription } from 'rxjs'

import { AuthService } from '../auth.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { ManagementService } from '../backend/api/management.service'

@Component({
    selector: 'app-diags-page',
    templateUrl: './diags-page.component.html',
    styleUrls: ['./diags-page.component.sass'],
})
export class DiagsPageComponent implements OnInit, OnDestroy {
    data: any = { rq: {} }
    logServices: any = []
    logServicesSelected: string[] = []
    servicesLogs: any = []
    servicesLogsAreLoading = false

    // services logs filtering
    logLevels: any[]
    logLevel: any

    rqJobs: any[]
    rqJob: any = 'all'
    rqCurrentJobs: any[]
    rqFinishedJobs: any[]
    rqFailedJobs: any[]

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        public auth: AuthService,
        protected breadcrumbService: BreadcrumbsService,
        protected managementService: ManagementService,
        private titleService: Title
    ) {
        this.logServices = [
            { name: 'server', value: 'server' },
            { name: 'server/api', value: 'server/api' },
            { name: 'server/backend', value: 'server/backend' },
            { name: 'server/webhooks', value: 'server/webhooks' },
            { name: 'server/artifacts', value: 'server/artifacts' },
            { name: 'server/install', value: 'server/install' },
            { name: 'server/job-log', value: 'server/job-log' },
            { name: 'server/badge', value: 'server/badge' },
            { name: 'server/other', value: 'server/other' },
            { name: 'rq', value: 'rq' },
            { name: 'scheduler', value: 'scheduler' },
            { name: 'planner', value: 'planner' },
            { name: 'watchdog', value: 'watchdog' },
        ]

        this.logLevels = [
            { label: 'Info', value: 'info' },
            { label: 'Warning', value: 'warning' },
            { label: 'Error', value: 'error' },
        ]

        this.rqJobs = [{ label: '-- all --', value: 'all' }]
    }

    ngOnInit() {
        this.titleService.setTitle('Kraken - Diagnostics')

        this.breadcrumbService.setCrumbs([
            {
                label: 'Home',
            },
            {
                label: 'Diagnostics',
            },
        ])

        this.subs.add(
            this.route.queryParamMap.subscribe(
                (params) => {
                    const tab = this.route.snapshot.paramMap.get('tab')
                    if (tab === 'logs') {
                        this.loadLastRQJobsNames()

                        const level = params.get('level')
                        if (
                            ['info', 'warning', 'error'].includes(level) &&
                            this.logLevel !== level
                        ) {
                            this.logLevel = level
                            this.loadServicesLogs()
                        }
                    }
                },
                (error) => {
                    console.log(error)
                }
            )
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    loadLastRQJobsNames() {
        this.subs.add(
            this.managementService.getLastRqJobsNames().subscribe((data) => {
                this.rqJobs = [{ label: '-- all --', value: 'all' }]
                for (const t of data.items) {
                    this.rqJobs.push({ label: t.name, value: t.name })
                }
            })
        )
    }

    loadDiagsData() {
        this.subs.add(
            this.managementService.getDiagnostics().subscribe((data) => {
                this.data = data
            })
        )
    }

    loadServicesLogs() {
        if (!this.auth.hasPermission('manage')) {
            return
        }
        this.servicesLogsAreLoading = true

        let services = ['all']
        if (this.logServicesSelected.length > 0) {
            if (this.rqJob && this.rqJob !== 'all') {
                services = []
                for (let s of this.logServicesSelected) {
                    if (s === 'rq') {
                        s = 'rq/' + this.rqJob
                    }
                    services.push(s)
                }
            } else {
                services = this.logServicesSelected
            }
        }

        this.subs.add(
            this.managementService
                .getServicesLogs(services, this.logLevel)
                .subscribe((data) => {
                    this.servicesLogs = data.items
                    this.servicesLogsAreLoading = false
                })
        )
    }

    handleTabChange(tabName) {
        if (tabName === 'overview') {
            this.loadDiagsData()
        } else if (tabName === 'logs') {
            this.loadServicesLogs()
        }
    }

    isRQSelected() {
        if (this.logServicesSelected.includes('rq')) {
            return true
        }
        return false
    }
}
