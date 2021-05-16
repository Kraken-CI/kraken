import { Component, OnInit } from '@angular/core'
import { Title } from '@angular/platform-browser'
import { ActivatedRoute } from '@angular/router'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { ManagementService } from '../backend/api/management.service'

@Component({
    selector: 'app-diags-page',
    templateUrl: './diags-page.component.html',
    styleUrls: ['./diags-page.component.sass'],
})
export class DiagsPageComponent implements OnInit {
    tabIndex = 0
    data: any = {celery: {}}
    celeryLogs: any = []
    logServices: any = []
    logServicesSelected: string[] = []
    servicesLogs: any = []
    servicesLogsAreLoading = false

    // services logs filtering
    logLevels: any[]
    logLevel: any

    constructor(
        private route: ActivatedRoute,
        protected breadcrumbService: BreadcrumbsService,
        protected managementService: ManagementService,
        private titleService: Title
    ) {
        this.logServices = [
            {name: 'server', value: 'server'},
            {name: 'server/api', value: 'server/api'},
            {name: 'server/backend', value: 'server/backend'},
            {name: 'server/webhooks', value: 'server/webhooks'},
            {name: 'server/artifacts', value: 'server/artifacts'},
            {name: 'server/install', value: 'server/install'},
            {name: 'server/job-log', value: 'server/job-log'},
            {name: 'server/badge', value: 'server/badge'},
            {name: 'server/other', value: 'server/other'},
            {name: 'celery', value: 'celery'},
            {name: 'scheduler', value: 'scheduler'},
            {name: 'planner', value: 'planner'},
            {name: 'watchdog', value: 'watchdog'},
        ]

        this.logLevels = [
            {label: 'Info', value: 'info'},
            {label: 'Warning', value: 'warning'},
            {label: 'Error', value: 'error'},
        ]
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

        this.managementService.getDiagnostics().subscribe((data) => {
            this.data = data
        })

        this.route.queryParamMap.subscribe(
            (params) => {
                if (params.get('tab') == 'logs') {
                    this.tabIndex = 2
                } else {
                    this.tabIndex = 0
                }
                const level = params.get('level')
                if (['info', 'warning', 'error'].includes(level) && this.logLevel !== level) {
                    this.logLevel = level
                    this.loadServicesLogs()
                }
            },
            (error) => {
                console.log(error)
            }
        )
    }
    showCeleryLogs(taskName) {
        this.managementService.getCeleryLogs(taskName).subscribe((data) => {
            this.celeryLogs = data.items
        })
    }

    loadServicesLogs() {
        this.servicesLogsAreLoading = true

        let services = ['all']
        if (this.logServicesSelected.length > 0) {
            services = this.logServicesSelected
        }

        this.managementService.getServicesLogs(services, this.logLevel).subscribe((data) => {
            this.servicesLogs = data.items
            this.servicesLogsAreLoading = false
        })
    }

    handleTabChange(ev) {
        if (ev.index === 2) {
            this.loadServicesLogs()
        }
    }
}
