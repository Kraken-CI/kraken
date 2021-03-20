import { Component, OnInit } from '@angular/core'
import { ActivatedRoute, NavigationEnd, Router } from '@angular/router'
import { distinctUntilChanged, filter, map, switchMap } from 'rxjs/operators'
import { BehaviorSubject } from 'rxjs'

import { MenuItem } from 'primeng/api'

import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-breadcrumbs',
    templateUrl: './breadcrumbs.component.html',
    styleUrls: ['./breadcrumbs.component.sass'],
})
export class BreadcrumbsComponent implements OnInit {
    breadcrumbsIn: any
    breadcrumbs = new BehaviorSubject([
        {
            label: 'Home',
            url: '/',
            id: 0,
        },
    ])
    crumbMenuItems: MenuItem[]
    projects: any[] = []
    branches = {}
    flows = {}
    runs = {}

    currProjectId = 0
    currBranchId = 0
    currFlowKind = 'CI'
    currFlowId = 0
    currRunId = 0

    constructor(
        private activatedRoute: ActivatedRoute,
        private router: Router,
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService
    ) {}

    ngOnInit() {
        this.breadcrumbsIn = this.breadcrumbService.getCrumbs()

        this.breadcrumbsIn.subscribe((data) => {
            if (data.length === 0) {
                return
            }
            let getBranches = false
            let getFlows = false
            let getRuns = false

            const data2 = []
            for (const it of data) {
                const it2 = {
                    label: it.label,
                    url: '',
                    id: '',
                    menuItems: [],
                }
                switch (it.label) {
                    case 'Projects':
                        it2.url = '/projects/' + it.project_id
                        it2.id = it.project_name
                        this.currProjectId = it.project_id
                        break
                    case 'Branches':
                        it2.url = '/branches/' + it.branch_id
                        it2.id = it.branch_name
                        this.currBranchId = it.branch_id
                        getBranches = true
                        break
                    case 'Results':
                        it2.url =
                            '/branches/' + it.branch_id + '/' + it.flow_kind
                        it2.id = it.flow_kind.toUpperCase()
                        it2.menuItems = [
                            {
                                label: 'CI',
                                routerLink: '/branches/' + it.branch_id + '/ci',
                            },
                            {
                                label: 'DEV',
                                routerLink:
                                    '/branches/' + it.branch_id + '/dev',
                            },
                        ]
                        this.currFlowKind = it.flow_kind
                        break
                    case 'Flows':
                        it2.url = '/flows/' + it.flow_id
                        it2.id = it.flow_id
                        this.currFlowId = it.flow_id
                        getFlows = true
                        break
                    case 'Stages':
                        it2.url = '/runs/' + it.run_id
                        it2.id = it.run_name
                        getRuns = true
                        break
                    case 'Result':
                        it2.url = '/test_case_result/' + it.tcr_id
                        it2.id = it.tc_name
                        break
                }
                data2.push(it2)
            }

            if (
                getBranches &&
                this.currProjectId &&
                (this.branches[this.currProjectId] === undefined ||
                    this.branches[this.currProjectId].length === 0)
            ) {
                const projId = this.currProjectId
                this.managementService.getProject(projId).subscribe((proj) => {
                    this.branches[projId] = proj.branches
                })
            }

            if (getFlows) {
                const flowsKey =
                    '' + this.currBranchId + '-' + this.currFlowKind
                if (
                    this.flows[flowsKey] === undefined ||
                    this.flows[flowsKey].length === 0
                ) {
                    this.executionService
                        .getFlows(
                            this.currBranchId,
                            this.currFlowKind,
                            null,
                            10,
                            this.currFlowId
                        )
                        .subscribe((flows) => {
                            this.flows[flowsKey] = flows.items
                        })
                }
            }

            if (
                getRuns &&
                this.currFlowId &&
                (this.runs[this.currFlowId] === undefined ||
                    this.runs[this.currFlowId].length === 0)
            ) {
                const flowId = this.currFlowId
                this.executionService.getFlow(flowId).subscribe((flow) => {
                    this.runs[flowId] = flow.runs
                })
            }

            this.breadcrumbs.next(data2)
        })

        this.managementService.getProjects().subscribe((data) => {
            this.projects = data.items
        })
    }

    showCrumbMenu(event, crumbMenu, breadcrumb) {
        switch (breadcrumb.label) {
            case 'Projects':
                this.crumbMenuItems = this.projects.map((p) => {
                    return { label: p.name, routerLink: '/projects/' + p.id }
                })
                break
            case 'Branches':
                this.crumbMenuItems = this.branches[this.currProjectId].map(
                    (b) => {
                        return {
                            label: b.name,
                            routerLink: '/branches/' + b.id,
                        }
                    }
                )
                break
            case 'Flows':
                const flowsKey =
                    '' + this.currBranchId + '-' + this.currFlowKind
                this.crumbMenuItems = this.flows[flowsKey].map((f) => {
                    return {
                        label: f.id + ' - ' + f.label,
                        routerLink: '/flows/' + f.id,
                    }
                })
                break
            case 'Stages':
                this.crumbMenuItems = this.runs[this.currFlowId].map((r) => {
                    return { label: r.stage_name, routerLink: '/runs/' + r.id }
                })
                break
            case 'Home':
                this.router.navigate(['/'])
                return
            default:
                if (breadcrumb.menuItems) {
                    this.crumbMenuItems = breadcrumb.menuItems
                } else {
                    this.crumbMenuItems = []
                }
        }

        if (this.crumbMenuItems.length > 0) {
            crumbMenu.toggle(event)
        }
    }
}
