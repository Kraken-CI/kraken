import { Component, OnInit, OnDestroy } from '@angular/core'
import { Title } from '@angular/platform-browser'

import { Subscription } from 'rxjs'

import { ManagementService } from '../backend/api/management.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-tools-page',
    templateUrl: './tools-page.component.html',
    styleUrls: ['./tools-page.component.sass'],
})
export class ToolsPageComponent implements OnInit, OnDestroy {
    private subs: Subscription = new Subscription()

    tools: any[]
    totalTools = 0
    loadingTools = false

    constructor(
        protected managementService: ManagementService,
        protected breadcrumbService: BreadcrumbsService,
        private titleService: Title
    ) {}

    ngOnInit(): void {
        this.titleService.setTitle('Kraken - Tools')
        const crumbs = [
            {
                label: 'Home',
            },
            {
                label: 'Tools',
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    loadToolsLazy(event) {
        this.loadingTools = true
        console.info(event)

        let sortField = 'name'
        if (event.sortField) {
            sortField = event.sortField
        }
        let sortDir = 'asc'
        if (event.sortOrder === -1) {
            sortDir = 'desc'
        }

        this.subs.add(
            this.managementService
                .getTools(event.first, event.rows, sortField, sortDir)
                .subscribe((data) => {
                    this.tools = data.items
                    this.totalTools = data.total
                    this.loadingTools = false

                    for (const t of this.tools) {
                        t.fieldsJson = JSON.stringify(
                            t.fields.properties,
                            null,
                            4
                        )
                    }
                })
        )
    }

    showRawSchema() {}
}
