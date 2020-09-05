import { Component, OnInit } from '@angular/core'
import {
    ActivatedRoute,
    ParamMap,
    Router,
    NavigationEnd,
} from '@angular/router'
import { Title } from '@angular/platform-browser'

import { MessageService, MenuItem } from 'primeng/api'

import { ManagementService } from '../backend/api/management.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-groups-page',
    templateUrl: './groups-page.component.html',
    styleUrls: ['./groups-page.component.sass'],
})
export class GroupsPageComponent implements OnInit {
    // groups table
    groups: any[]
    totalGroups: number
    groupMenuItems: MenuItem[]

    // action panel
    filterText = ''

    // new group
    newGroupDlgVisible = false
    groupName: string

    // group tabs
    activeTabIdx = 0
    tabs: MenuItem[]
    activeItem: MenuItem
    openedGroups: any
    groupTab: any

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        private msgSrv: MessageService,
        protected managementService: ManagementService,
        protected breadcrumbService: BreadcrumbsService,
        private titleService: Title
    ) {}

    switchToTab(index) {
        if (this.activeTabIdx === index) {
            return
        }
        this.activeTabIdx = index
        this.activeItem = this.tabs[index]
        if (index > 0) {
            this.groupTab = this.openedGroups[index - 1]
        }
    }

    addGroupTab(group) {
        this.openedGroups.push({
            group,
            name: group.name,
        })
        this.tabs.push({
            label: group.name,
            routerLink: '/agents-groups/' + group.id,
        })
    }

    ngOnInit() {
        this.titleService.setTitle('Kraken - Groups')
        const crumbs = [
            {
                label: 'Home',
            },
            {
                label: 'Agent Groups',
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)

        this.tabs = [{ label: 'Groups', routerLink: '/agents-groups/all' }]

        this.groups = []
        this.groupMenuItems = [
            {
                label: 'Delete',
                icon: 'pi pi-times',
            },
        ]

        this.openedGroups = []

        this.route.paramMap.subscribe((params: ParamMap) => {
            const groupIdStr = params.get('id')
            if (groupIdStr === 'all') {
                this.switchToTab(0)
            } else {
                const groupId = parseInt(groupIdStr, 10)

                let found = false
                // if tab for this group is already opened then switch to it
                for (let idx = 0; idx < this.openedGroups.length; idx++) {
                    const g = this.openedGroups[idx].group
                    if (g.id === groupId) {
                        this.switchToTab(idx + 1)
                        found = true
                    }
                }

                // if tab is not opened then search for list of groups if the one is present there,
                // if so then open it in new tab and switch to it
                if (!found) {
                    for (const g of this.groups) {
                        if (g.id === groupId) {
                            this.addGroupTab(g)
                            this.switchToTab(this.tabs.length - 1)
                            found = true
                            break
                        }
                    }
                }

                // if group is not loaded in list fetch it individually
                if (!found) {
                    this.managementService.getGroup(groupId).subscribe(
                        data => {
                            this.addGroupTab(data)
                            this.switchToTab(this.tabs.length - 1)
                        },
                        err => {
                            let msg = err.statusText
                            if (err.error && err.error.message) {
                                msg = err.error.message
                            }
                            this.msgSrv.add({
                                severity: 'error',
                                summary: 'Cannot get group',
                                detail:
                                    'Getting group with ID ' +
                                    groupId +
                                    ' erred: ' +
                                    msg,
                                life: 10000,
                            })
                            this.router.navigate(['/agents-groups/all'])
                        }
                    )
                }
            }
        })
    }

    loadGroupsLazy(event) {
        console.info(event)
        this.managementService
            .getGroups(event.first, event.rows)
            .subscribe(data => {
                this.groups = data.items
                this.totalGroups = data.total
            })
    }

    showNewGroupDlg() {
        this.newGroupDlgVisible = true
    }

    addNewGroup() {
        if (this.groupName.trim() === '') {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Adding new group erred',
                detail: 'Group name cannot be empty.',
                life: 10000,
            })
            return
        }

        this.newGroupDlgVisible = false

        const g = { name: this.groupName }

        this.managementService.createGroup(g).subscribe(
            data => {
                this.msgSrv.add({
                    severity: 'success',
                    summary: 'New group added',
                    detail: 'Adding new group succeeded.',
                })
                this.newGroupDlgVisible = false
                this.addGroupTab(data)
                this.router.navigate(['/agents-groups/' + data.id])
            },
            err => {
                console.info(err)
                let msg = err.statusText
                if (err.error && err.error.message) {
                    msg = err.error.message
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Adding new group erred',
                    detail: 'Adding new group operation erred: ' + msg,
                    life: 10000,
                })
                this.newGroupDlgVisible = false
            }
        )
    }

    cancelNewGroup() {
        this.newGroupDlgVisible = false
    }

    keyDownNewGroup(event) {
        if (event.key === 'Enter') {
            this.addNewGroup()
        }
    }

    refreshGroupsList(groupsTable) {
        groupsTable.onLazyLoad.emit(groupsTable.createLazyLoadMetadata())
    }

    keyDownFilterText(groupsTable, event) {
        if (this.filterText.length >= 3 || event.key === 'Enter') {
            groupsTable.filter(this.filterText, 'text', 'equals')
        }
    }

    closeTab(event, idx) {
        this.openedGroups.splice(idx - 1, 1)
        this.tabs.splice(idx, 1)
        if (this.activeTabIdx === idx) {
            this.switchToTab(idx - 1)
            if (idx - 1 > 0) {
                this.router.navigate([
                    '/agents-groups/' + this.groupTab.group.id,
                ])
            } else {
                this.router.navigate(['/agents-groups/all'])
            }
        } else if (this.activeTabIdx > idx) {
            this.activeTabIdx = this.activeTabIdx - 1
        }
        if (event) {
            event.preventDefault()
        }
    }

    showGroupMenu(event, groupMenu, group) {
        groupMenu.toggle(event)

        // connect method to delete group
        this.groupMenuItems[0].command = () => {
            this.managementService.deleteGroup(group.id).subscribe(data => {
                // remove from list of groups
                for (let idx = 0; idx < this.groups.length; idx++) {
                    const g = this.groups[idx]
                    if (g.id === group.id) {
                        this.groups.splice(idx, 1) // TODO: does not work
                        break
                    }
                }
                // remove from opened tabs if present
                for (let idx = 0; idx < this.openedGroups.length; idx++) {
                    const g = this.openedGroups[idx].group
                    if (g.id === group.id) {
                        this.closeTab(null, idx + 1)
                        break
                    }
                }
            })
        }
    }

    saveGroup(groupTab) {
        console.info(groupTab)
        if (groupTab.name === groupTab.group.name) {
            return
        }
        const g = { name: groupTab.name }
        this.managementService.updateGroup(groupTab.group.id, g).subscribe(
            data => {
                console.info('updated', data)
                groupTab.group.name = data.name
                this.msgSrv.add({
                    severity: 'success',
                    summary: 'Group updated',
                    detail: 'Group update succeeded.',
                })
            },
            err => {
                let msg = err.statusText
                if (err.error && err.error.message) {
                    msg = err.error.message
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Group update failed',
                    detail: 'Updating group erred: ' + msg,
                    life: 10000,
                })
            }
        )
    }

    groupNameKeyDown(event, groupTab) {
        if (event.key === 'Enter') {
            this.saveGroup(groupTab)
        }
    }
}
