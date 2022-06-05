import { Component, OnInit, OnDestroy } from '@angular/core'
import { Title } from '@angular/platform-browser'

import { MessageService } from 'primeng/api'

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

    tools: any[] = []
    totalTools = 0
    loadingTools = false
    selectedTool: any

    toolVersions: any[]
    selectedVersion: any

    constructor(
        protected managementService: ManagementService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
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

                    if (!this.selectedTool) {
                        this.selectedTool = this.tools[0]
                        this.loadToolVersions(this.selectedTool)
                    }
                })
        )
    }

    loadToolVersions(tool) {
        this.subs.add(
            this.managementService
                .getToolVersions(tool.name, 0, 1000)
                .subscribe((data) => {
                    this.toolVersions = data.items
                    this.selectedVersion = this.toolVersions[0]
                    this.genRawSchema()
                })
        )
    }

    versionSelect(ev) {
        this.genRawSchema()
    }

    genRawSchema() {
        this.selectedVersion.fieldsJson = JSON.stringify(
            this.selectedVersion.fields.properties,
            null,
            4
        )
    }

    deleteToolVersion() {
        this.subs.add(
            this.managementService
                .deleteTool(this.selectedVersion.id)
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Tool version deletion succeeded',
                            detail: 'Tool version deletion operation succeeded.',
                        })
                        this.loadToolVersions(this.selectedTool)
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Tool version deletion erred',
                            detail:
                                'Tool version delete operation erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }
}
