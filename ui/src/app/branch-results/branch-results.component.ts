import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'
import { Title } from '@angular/platform-browser'
import { Observable } from 'rxjs'
import { switchMap } from 'rxjs/operators'

import { MessageService } from 'primeng/api'

import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { Run } from '../backend/model/run'
import { datetimeToLocal, humanBytes } from '../utils'

@Component({
    selector: 'app-branch-results',
    templateUrl: './branch-results.component.html',
    styleUrls: ['./branch-results.component.sass'],
})
export class BranchResultsComponent implements OnInit {
    branchId = 0
    branch: any
    kind: string

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
        private msgSrv: MessageService,
        private titleService: Title
    ) {}

    ngOnInit() {
        this.branch = null
        this.branchId = parseInt(this.route.snapshot.paramMap.get('id'), 10)
        this.kind = this.route.snapshot.paramMap.get('kind')
        this.selectedStage = null
        this.stagesAvailable = [{ name: 'All' }]

        this.executionService.getBranch(this.branchId).subscribe(branch => {
            this.titleService.setTitle('Kraken - Branch Results - ' + branch.name + ' ' + this.kind)
            this.branch = branch
            this.updateBreadcrumb()
        })

        this.route.paramMap.subscribe(params => {
            this.branchId = parseInt(params.get('id'), 10)
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
                        parseInt(params.get('id'), 10),
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

    humanFileSize(bytes) {
        return humanBytes(bytes, false)
    }
}
