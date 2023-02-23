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

    private subs: Subscription = new Subscription()

    logsPanelVisible = false
    logLevel = 'info'

    constructor(
        private route: ActivatedRoute,
        public auth: AuthService,
        protected breadcrumbService: BreadcrumbsService,
        protected managementService: ManagementService,
        private titleService: Title
    ) {
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
                        this.logsPanelVisible = true
                        const level = params.get('level')
                        if (
                            ['info', 'warning', 'error'].includes(level) &&
                                this.logLevel !== level
                        ) {
                            this.logLevel = level
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

    loadDiagsData() {
        this.subs.add(
            this.managementService.getDiagnostics().subscribe((data) => {
                this.data = data
            })
        )
    }


    handleTabChange(tabName) {
        if (tabName === 'overview') {
            this.loadDiagsData()
            this.logsPanelVisible = false
        } else if (tabName === 'logs') {
            this.logsPanelVisible = true
        }
    }
}
