import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, ParamMap, Router, NavigationEnd } from '@angular/router'

import { MessageService, MenuItem } from 'primeng/api'

import { ManagementService } from '../backend/api/management.service';
import { BreadcrumbsService } from '../breadcrumbs.service';

@Component({
  selector: 'app-executors-page',
  templateUrl: './executors-page.component.html',
  styleUrls: ['./executors-page.component.sass']
})
export class ExecutorsPageComponent implements OnInit {

    // executors table
    executors: any[]
    totalExecutors = 0
    loadingExecutors = true
    executor: any
    executorsTable: any

    executorMenuItems: MenuItem[]

    // action panel
    filterText = ''

    // executor tabs
    activeTabIdx = 0
    tabs: MenuItem[]
    activeItem: MenuItem
    openedExecutors: any
    executorTab: any

    executorGroups: any[] = []

    constructor(private route: ActivatedRoute,
                private router: Router,
                private msgSrv: MessageService,
                protected managementService: ManagementService,
                protected breadcrumbService: BreadcrumbsService
    ) {}

    switchToTab(index) {
        if (this.activeTabIdx === index) {
            return
        }
        this.activeTabIdx = index
        this.activeItem = this.tabs[index]
        if (index > 0) {
            this.executorTab = this.openedExecutors[index - 1]
        }
    }

    addExecutorTab(executor) {
        this.openedExecutors.push({
            executor,
            name: executor.name
        })
        console.info('executor.groups', executor.groups)
        this.tabs.push({
            label: executor.name,
            routerLink: '/executors/' + executor.id,
        })
    }

    ngOnInit() {
        this.tabs = [{ label: 'Executors', routerLink: '/executors/all' }]

        this.executors = []
        this.executorMenuItems = [
            {
                label: 'Delete',
                icon: 'pi pi-times',
            },
        ]

        this.openedExecutors = []

        this.route.paramMap.subscribe((params: ParamMap) => {
            const executorIdStr = params.get('id')
            if (executorIdStr === 'all') {
                this.switchToTab(0)
            } else {
                const executorId = parseInt(executorIdStr, 10)

                let found = false
                // if tab for this executor is already opened then switch to it
                for (let idx = 0; idx < this.openedExecutors.length; idx++) {
                    const g = this.openedExecutors[idx].executor
                    if (g.id === executorId) {
                        this.switchToTab(idx + 1)
                        found = true
                    }
                }

                // if tab is not opened then search for list of executors if the one is present there,
                // if so then open it in new tab and switch to it
                if (!found) {
                    for (const g of this.executors) {
                        if (g.id === executorId) {
                            this.addExecutorTab(g)
                            this.switchToTab(this.tabs.length - 1)
                            found = true
                            break
                        }
                    }
                }

                // if executor is not loaded in list fetch it individually
                if (!found) {
                    this.managementService.getExecutor(executorId).subscribe(
                        data => {
                            this.addExecutorTab(data)
                            this.switchToTab(this.tabs.length - 1)
                        },
                        err => {
                            let msg = err.statusText
                            if (err.error && err.error.message) {
                                msg = err.error.message
                            }
                            this.msgSrv.add({
                                severity: 'error',
                                summary: 'Cannot get executor',
                                detail: 'Getting executor with ID ' + executorId + ' erred: ' + msg,
                                life: 10000,
                            })
                            this.router.navigate(['/executors/all'])
                        }
                    )
                }
            }
        })

        this.managementService.getGroups(0, 1000).subscribe(data => {
            this.executorGroups = data.items.map(g => {
                return {id: g.id, name: g.name}
            })
            console.info(this.executorGroups)
        })
    }

    loadExecutorsLazy(event) {
        console.info(event)
        this.loadingExecutors = true
        this.managementService.getExecutors(false, event.first, event.rows).subscribe(data => {
            this.executors = data.items
            this.totalExecutors = data.total
            this.loadingExecutors = false
        })
    }

    refreshExecutors(executorsTable) {
        executorsTable.onLazyLoad.emit(executorsTable.createLazyLoadMetadata())
    }

    keyDownFilterText(executorsTable, event) {
        if (this.filterText.length >= 3 || event.key === 'Enter') {
            executorsTable.filter(this.filterText, 'text', 'equals')
        }
    }

    closeTab(event, idx) {
        this.openedExecutors.splice(idx - 1, 1)
        this.tabs.splice(idx, 1)
        if (this.activeTabIdx === idx) {
            this.switchToTab(idx - 1)
            if (idx - 1 > 0) {
                this.router.navigate(['/executors/' + this.executorTab.executor.id])
            } else {
                this.router.navigate(['/executors/all'])
            }
        } else if (this.activeTabIdx > idx) {
            this.activeTabIdx = this.activeTabIdx - 1
        }
        if (event) {
            event.preventDefault()
        }
    }

    showExecutorMenu(event, executorMenu, executor) {
        executorMenu.toggle(event)

        // connect method to delete executor
        this.executorMenuItems[0].command = () => {
            this.managementService.deleteExecutor(executor.id).subscribe(data => {
                // remove from list of machines
                for (let idx = 0; idx < this.executors.length; idx++) {
                    const e = this.executors[idx]
                    if (e.id === executor.id) {
                        this.executors.splice(idx, 1) // TODO: does not work
                        break
                    }
                }
                // remove from opened tabs if present
                for (let idx = 0; idx < this.openedExecutors.length; idx++) {
                    const e = this.openedExecutors[idx].executor
                    if (e.id === executor.id) {
                        this.closeTab(null, idx + 1)
                        break
                    }
                }
            })
        }
    }

    saveExecutor(executorsTable) {
        // if nothing changed
        // if (executorTab.name === executorTab.executor.name) {
        //     return
        // }
        let groups = this.executorTab.executor.groups.map(g => {
            return {id: g.id}
        })
        const ex = { groups: groups }
        this.managementService.updateExecutor(this.executorTab.executor.id, ex).subscribe(
            data => {
                console.info('updated', data)
                //executorTab.executor.name = data.name
                this.msgSrv.add({
                    severity: 'success',
                    summary: 'Executor updated',
                    detail: 'Executor update succeeded.',
                })
            },
            err => {
                let msg = err.statusText
                if (err.error && err.error.message) {
                    msg = err.error.message
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Executor update failed',
                    detail: 'Updating executor erred: ' + msg,
                    life: 10000,
                })
            }
        )
    }

    executorNameKeyDown(event, executorTab) {
        if (event.key === 'Enter') {
            this.saveExecutor(executorTab)
        }
    }
}
