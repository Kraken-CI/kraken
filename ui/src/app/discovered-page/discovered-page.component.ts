import { Component, OnInit } from '@angular/core'

import { ManagementService } from '../backend/api/management.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-discovered-page',
    templateUrl: './discovered-page.component.html',
    styleUrls: ['./discovered-page.component.sass'],
})
export class DiscoveredPageComponent implements OnInit {
    executors: any[]
    totalExecutors = 0
    loadingExecutors = true
    selectedExecutors: any[]

    constructor(
        protected managementService: ManagementService,
        protected breadcrumbService: BreadcrumbsService
    ) {}

    ngOnInit() {
        const crumbs = [
            {
                label: 'Home',
            },
            {
                label: 'Discovered Executors',
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)
    }

    loadExecutorsLazy(event) {
        this.loadingExecutors = true
        this.managementService.getExecutors(true).subscribe(data => {
            this.executors = data.items
            this.totalExecutors = data.total
            this.loadingExecutors = false
        })
    }

    refreshExecutors(executorsTable) {
        executorsTable.onLazyLoad.emit(executorsTable.createLazyLoadMetadata())
    }

    resetExecutorsFilter(executorsTable) {
        if (executorsTable) {
            this.refreshExecutors(executorsTable)
        }
    }

    executorSelected(ev) {
        console.info(ev)
    }

    authorize(executorsTable) {
        const execs = this.selectedExecutors.map(e => {
            return { id: e.id, authorized: true }
        })
        this.managementService.updateExecutors(execs).subscribe(data => {
            this.refreshExecutors(executorsTable)
        })
    }
}
