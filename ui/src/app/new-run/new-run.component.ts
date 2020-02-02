import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'

import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-new-run',
    templateUrl: './new-run.component.html',
    styleUrls: ['./new-run.component.sass'],
})
export class NewRunComponent implements OnInit {
    flowId = 0
    stageId = 0
    flow: any = { id: 0 }
    stage: any = { name: '' }
    params: any[]
    args: any

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService
    ) {}

    ngOnInit() {
        this.flowId = parseInt(this.route.snapshot.paramMap.get('flow_id'))
        this.stageId = parseInt(this.route.snapshot.paramMap.get('stage_id'))
        this.executionService.getFlow(this.flowId).subscribe(flow => {
            this.flow = flow

            for (const s of flow.stages) {
                if (s.id == this.stageId) {
                    this.stage = s
                    break
                }
            }

            // prepare breadcrumb
            const crumbs = [
                {
                    label: 'Projects',
                    project_id: flow.project_id,
                    project_name: flow.project_name,
                },
                {
                    label: 'Branches',
                    branch_id: flow.branch_id,
                    branch_name: flow.base_branch_name,
                },
                {
                    label: 'Results',
                    branch_id: flow.branch_id,
                    flow_kind: flow.kind,
                },
                {
                    label: 'Flows',
                    flow_id: flow.id,
                },
            ]
            this.breadcrumbService.setCrumbs(crumbs)

            // prepare args form
            const args = {}
            for (const p of this.stage.schema.parameters) {
                args[p.name] = p.default
            }
            this.params = this.stage.schema.parameters
            this.args = args
        })
    }

    submitRun() {
        const run = {
            stage_id: this.stageId,
            args: this.args,
        }
        this.executionService.createRun(this.flowId, run).subscribe(run => {
            this.router.navigate(['/flows/' + this.flowId])
        })
    }
}
