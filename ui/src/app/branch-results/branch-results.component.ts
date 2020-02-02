import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'
import { Observable } from 'rxjs'
import { switchMap } from 'rxjs/operators'

import { MessageService } from 'primeng/api'

import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { Run } from '../backend/model/run'
import { datetimeToLocal } from '../utils'

@Component({
    selector: 'app-branch-results',
    templateUrl: './branch-results.component.html',
    styleUrls: ['./branch-results.component.sass'],
})
export class BranchResultsComponent implements OnInit {
    branchId = 0
    branch: any
    kind: string

    flows0: any[]
    flows: any[]

    totalFlows = 100

    stagesAvailable: any[]
    selectedStages: any[]
    selectedStage: any
    filterStageName = 'All'

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService
    ) {}

    ngOnInit() {
        this.branch = null
        this.branchId = parseInt(this.route.snapshot.paramMap.get('id'))
        this.kind = this.route.snapshot.paramMap.get('kind')
        this.selectedStage = null
        this.stagesAvailable = [{ name: 'All' }]
        this.flows0 = [
            {
                name: '278',
                state: 'completed',
                created: '2019-09-13 15:30 UTC',
                runs: [
                    {
                        name: 'Tarball',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Package',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'System Tests',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                        jobs_total: 103,
                        jobs_error: 78,
                        jobs_rerun: 7,
                        jobs_pending: 2,
                        tests_passed: 987,
                        tests_total: 1033,
                        issues_total: 12,
                    },
                    {
                        name: 'Deploy',
                        state: 'not-run',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Deploy Prod',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Deploy Prod 2',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Deploy Prod 3',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Deploy Prod 4',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                ],
            },
            {
                name: '277',
                created: '2019-09-13 15:30 UTC',
                state: 'completed',
                runs: [
                    {
                        name: 'Tarball',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Package',
                        state: 'completed',
                        color: '#ffe6e6',
                        jobs_total: 18,
                        jobs_error: 3,
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Deploy',
                        color: '#ffffff',
                        state: 'not-run',
                        started: 'not run',
                        duration: '---',
                    },
                ],
            },
            {
                name: '276',
                created: '2019-09-13 15:30 UTC',
                state: 'completed',
                runs: [
                    {
                        name: 'Tarball',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Package',
                        color: '#e6ffe6',
                        state: 'completed',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'System Tests',
                        state: 'completed',
                        color: '#fff9e6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                        tests_passed: 987,
                        tests_total: 1033,
                    },
                    {
                        name: 'Deploy',
                        state: 'not-run',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                ],
            },
            {
                name: '275',
                created: '2019-09-13 15:30 UTC',
                state: 'in-progress',
                runs: [
                    {
                        name: 'Tarball',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'Package',
                        state: 'completed',
                        color: '#e6ffe6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                    {
                        name: 'System Tests',
                        state: 'completed',
                        color: '#fff9e6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                        tests_passed: 987,
                        tests_total: 1033,
                    },
                    {
                        name: 'Static Analysis',
                        state: 'not-run',
                        color: '#fff9e6',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                        issues_total: 78,
                    },
                    {
                        name: 'Deploy',
                        state: 'not-run',
                        started: '2019-09-13 15:30 UTC',
                        duration: '3h 40m',
                    },
                ],
            },
        ]

        this.executionService.getBranch(this.branchId).subscribe(branch => {
            this.branch = branch
            this.updateBreadcrumb()
        })

        this.route.paramMap.subscribe(params => {
            this.branchId = parseInt(params.get('id'))
            this.kind = params.get('kind')
            this.updateBreadcrumb()
            this.refresh(0, 10)
        })
    }

    updateBreadcrumb() {
        if (this.branch == null) {
            return
        }
        const crumbs = [
            {
                label: 'Projects',
                project_id: this.branch.project_id,
                project_name: this.branch.project_name,
            },
            {
                label: 'Branches',
                branch_id: this.branch.id,
                branch_name: this.branch.name,
            },
            {
                label: 'Results',
                branch_id: this.branch.id,
                flow_kind: this.kind,
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)
    }

    _processFlowData(flow, stages) {
        for (const run of flow.runs) {
            stages.add(run.name)
        }
    }

    refresh(start, limit) {
        this.route.paramMap
            .pipe(
                switchMap((params: ParamMap) =>
                    this.executionService.getFlows(
                        parseInt(params.get('id')),
                        this.kind,
                        start,
                        limit
                    )
                )
            )
            .subscribe(data => {
                let flows = []
                const stages = new Set<string>()
                this.totalFlows = data.total
                flows = flows.concat(data.items)
                flows = flows.concat(this.flows0)
                for (const flow of flows) {
                    this._processFlowData(flow, stages)
                }
                this.flows = flows
                const newStages = [{ name: 'All' }]
                for (const st of Array.from(stages).sort()) {
                    newStages.push({ name: st })
                }
                this.stagesAvailable = newStages
            })
    }

    paginateFlows(event) {
        this.refresh(event.first, event.rows)
    }

    filterStages(event) {
        this.filterStageName = event.value.name
    }

    onStageRun(newRun) {}
}
