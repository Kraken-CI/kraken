import { Component, OnInit, OnDestroy } from '@angular/core'
import { ActivatedRoute, ParamMap, Router } from '@angular/router'
import { Title } from '@angular/platform-browser'

import { Subscription } from 'rxjs'

import { MessageService, MenuItem } from 'primeng/api'

import { AuthService } from '../auth.service'
import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { showErrorBox } from '../utils'

@Component({
    selector: 'app-agents-page',
    templateUrl: './agents-page.component.html',
    styleUrls: ['./agents-page.component.sass'],
})
export class AgentsPageComponent implements OnInit, OnDestroy {
    // agents table
    agents: any[]
    totalAgents = 0
    loadingAgents = true
    agent: any
    agentsTable: any

    agentMenuItems: MenuItem[]

    // action panel
    filterText = ''

    // agent tabs
    activeTabIdx = 0
    tabs: MenuItem[]
    activeItem: MenuItem
    openedAgents: any
    agentTab: any

    agentGroups: any[] = []

    // agent jobs table
    agentJobs: any[] = []
    totalAgentJobs = 0
    loadingAgentJobs = false

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        public auth: AuthService,
        private msgSrv: MessageService,
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
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
            this.agentTab = this.openedAgents[index - 1]
        }
    }

    addAgentTab(agent) {
        this.openedAgents.push({
            agent,
            name: agent.name,
        })
        this.tabs.push({
            label: agent.name,
            routerLink: '/agents/' + agent.id,
        })
    }

    ngOnInit() {
        this.titleService.setTitle('Kraken - Agents')
        const crumbs = [
            {
                label: 'Home',
            },
            {
                label: 'Agents',
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)

        this.tabs = [{ label: 'Agents', routerLink: '/agents/all' }]

        this.agents = []
        this.agentMenuItems = [
            {
                label: 'Delete',
                icon: 'pi pi-times',
                disabled: !this.auth.hasPermission(null, 'admin'),
                title: this.auth.permTip(null, 'admin'),
            },
        ]

        this.openedAgents = []

        this.subs.add(
            this.route.paramMap.subscribe((params: ParamMap) => {
                const agentIdStr = params.get('id')
                if (agentIdStr === 'all') {
                    this.switchToTab(0)
                } else {
                    const agentId = parseInt(agentIdStr, 10)

                    let found = false
                    // if tab for this agent is already opened then switch to it
                    for (let idx = 0; idx < this.openedAgents.length; idx++) {
                        const g = this.openedAgents[idx].agent
                        if (g.id === agentId) {
                            this.switchToTab(idx + 1)
                            found = true
                        }
                    }

                    // if tab is not opened then search for list of agents if the one is present there,
                    // if so then open it in new tab and switch to it
                    if (!found) {
                        for (const g of this.agents) {
                            if (g.id === agentId) {
                                this.addAgentTab(g)
                                this.switchToTab(this.tabs.length - 1)
                                found = true
                                break
                            }
                        }
                    }

                    // if agent is not loaded in list fetch it individually
                    if (!found) {
                        this.subs.add(
                            this.managementService.getAgent(agentId).subscribe(
                                (data) => {
                                    this.addAgentTab(data)
                                    this.switchToTab(this.tabs.length - 1)
                                },
                                (err) => {
                                    showErrorBox(this.msgSrv, err, `Getting agent with ID ${agentId} erred`)
                                    this.router.navigate(['/agents/all'])
                                }
                            )
                        )
                    }
                }
            })
        )

        this.subs.add(
            this.managementService.getGroups(0, 1000).subscribe(
                (data) => {
                    this.agentGroups = data.items.map((g) => {
                        return { id: g.id, name: g.name }
                    })
                },
                (err) => {
                    showErrorBox(this.msgSrv, err, 'Getting agents groups erred')
                }
            )
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    loadAgentsLazy(event) {
        this.loadingAgents = true
        this.subs.add(
            this.managementService
                .getAgents(false, event.first, event.rows)
                .subscribe(
                    (data) => {
                        this.agents = data.items
                        this.totalAgents = data.total
                        this.loadingAgents = false
                    },
                    (err) => {
                        showErrorBox(this.msgSrv, err, 'Getting agents erred')
                        this.loadingAgents = false
                    }
                )
        )
    }

    refreshAgents(agentsTable) {
        agentsTable.onLazyLoad.emit(agentsTable.createLazyLoadMetadata())
    }

    keyDownFilterText(agentsTable, event) {
        if (this.filterText.length >= 3 || event.key === 'Enter') {
            agentsTable.filter(this.filterText, 'text', 'equals')
        }
    }

    closeTab(event, idx) {
        this.openedAgents.splice(idx - 1, 1)
        this.tabs.splice(idx, 1)
        if (this.activeTabIdx === idx) {
            this.switchToTab(idx - 1)
            if (idx - 1 > 0) {
                this.router.navigate(['/agents/' + this.agentTab.agent.id])
            } else {
                this.router.navigate(['/agents/all'])
            }
        } else if (this.activeTabIdx > idx) {
            this.activeTabIdx = this.activeTabIdx - 1
        }
        if (event) {
            event.preventDefault()
        }
    }

    showAgentMenu(event, agentMenu, agent) {
        agentMenu.toggle(event)

        // connect method to delete agent
        this.agentMenuItems[0].command = () => {
            this.subs.add(
                this.managementService
                    .deleteAgent(agent.id)
                    .subscribe((data) => {
                        // remove from list of machines
                        for (let idx = 0; idx < this.agents.length; idx++) {
                            const e = this.agents[idx]
                            if (e.id === agent.id) {
                                this.agents.splice(idx, 1) // TODO: does not work
                                break
                            }
                        }
                        // remove from opened tabs if present
                        for (
                            let idx = 0;
                            idx < this.openedAgents.length;
                            idx++
                        ) {
                            const e = this.openedAgents[idx].agent
                            if (e.id === agent.id) {
                                this.closeTab(null, idx + 1)
                                break
                            }
                        }
                    })
            )
        }
    }

    saveAgent(agentsTable) {
        // if nothing changed
        // if (agentTab.name === agentTab.agent.name) {
        //     return
        // }
        const groups = this.agentTab.agent.groups.map((g) => {
            return { id: g.id }
        })
        const ag = { groups }
        this.updateAgent(this.agentTab.agent.id, ag)
    }

    updateAgent(agentId, agentData) {
        this.subs.add(
            this.managementService.updateAgent(agentId, agentData).subscribe(
                (data) => {
                    // agentTab.agent.name = data.name
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Agent updated',
                        detail: 'Agent update succeeded.',
                    })
                },
                (err) => {
                    showErrorBox(this.msgSrv, err, 'Agent update erred')
                }
            )
        )
    }

    agentNameKeyDown(event, agentTab) {
        if (event.key === 'Enter') {
            this.saveAgent(agentTab)
        }
    }

    filterHostInfo(hostInfo) {
        const ignoredAttrs = new Set([
            'system',
            'system_type',
            'distro_name',
            'distro_version',
            'isolation',
            'isolation_type',
        ])
        const res = []
        for (const [key, value] of Object.entries(hostInfo)) {
            if (ignoredAttrs.has(key)) {
                continue
            }
            res.push({ key, value })
        }
        return res
    }

    changeAgentDisable(ev, ag) {
        this.updateAgent(ag.id, { disabled: !ag.disabled })
    }

    loadAgentJobsLazy(event) {
        this.loadingAgentJobs = true
        this.subs.add(
            this.executionService
                .getAgentJobs(this.agentTab.agent.id, event.first, event.rows)
                .subscribe((data) => {
                    this.agentJobs = data.items
                    this.totalAgentJobs = data.total
                    this.loadingAgentJobs = false
                })
        )
    }
}
