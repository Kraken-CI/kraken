import { Component, OnInit, OnDestroy } from '@angular/core'
import { Router, ActivatedRoute } from '@angular/router'

import { Subscription } from 'rxjs'

import { AuthService } from '../auth.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-new-run',
    templateUrl: './new-run.component.html',
    styleUrls: ['./new-run.component.sass'],
})
export class NewRunComponent implements OnInit, OnDestroy {
    projectId = 0
    flowId = 0
    stageId = 0
    flow: any = { id: 0 }
    stage: any = { name: '' }
    params: any[]
    args: any

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        public auth: AuthService,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService
    ) {}

    ngOnInit() {
        this.flowId = parseInt(this.route.snapshot.paramMap.get('flow_id'), 10)
        this.stageId = parseInt(
            this.route.snapshot.paramMap.get('stage_id'),
            10
        )
        this.subs.add(
            this.executionService.getFlow(this.flowId).subscribe((flow) => {
                this.projectId = flow.project_id
                this.flow = flow

                for (const s of flow.stages) {
                    if (s.id === this.stageId) {
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
                        flow_label: flow.label,
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
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    submitRun() {
        const run = {
            stage_id: this.stageId,
            args: this.args,
        }
        this.subs.add(
            this.executionService
                .createRun(this.flowId, run)
                .subscribe((run2) => {
                    this.router.navigate(['/flows/' + this.flowId])
                })
        )
    }
}
