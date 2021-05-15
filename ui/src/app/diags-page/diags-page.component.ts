import { Component, OnInit } from '@angular/core'
import { Title } from '@angular/platform-browser'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { ManagementService } from '../backend/api/management.service'

@Component({
    selector: 'app-diags-page',
    templateUrl: './diags-page.component.html',
    styleUrls: ['./diags-page.component.sass'],
})
export class DiagsPageComponent implements OnInit {
    data: any = {celery: {}}
    celeryLogs: any = []
    logServices: any = []
    logServicesSelected: string[] = []
    servicesLogs: any = []

    constructor(
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
    }
    showCeleryLogs(taskName) {
        this.managementService.getCeleryLogs(taskName).subscribe((data) => {
            this.celeryLogs = data.items
        })
    }

    loadServicesLogs() {
        this.managementService.getServicesLogs(this.logServicesSelected).subscribe((data) => {
            this.servicesLogs = data.items
        })
    }
}
