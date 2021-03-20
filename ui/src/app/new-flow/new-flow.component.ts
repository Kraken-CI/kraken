import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'

import { TreeNode } from 'primeng/api'
import { MenuItem } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { AuthService } from '../auth.service'
import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-new-flow',
    templateUrl: './new-flow.component.html',
    styleUrls: ['./new-flow.component.sass'],
})
export class NewFlowComponent implements OnInit {
    kind: string
    branchId = 0
    branch: any = { name: '' }
    params: any[]
    args: any

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        public auth: AuthService,
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService
    ) {}

    ngOnInit() {
        this.kind = this.route.snapshot.paramMap.get('kind')

        this.branchId = parseInt(this.route.snapshot.paramMap.get('id'), 10)
        this.managementService.getBranch(this.branchId).subscribe((branch) => {
            this.branch = branch

            // prepare breadcrumb
            const crumbs = [
                {
                    label: 'Projects',
                    project_id: branch.project_id,
                    project_name: branch.project_name,
                },
                {
                    label: 'Branches',
                    branch_id: branch.id,
                    branch_name: branch.name,
                },
            ]
            this.breadcrumbService.setCrumbs(crumbs)

            // prepare args form
            const args = { Common: { BRANCH: branch.branch_name } }
            const params = []

            if (this.kind === 'dev') {
                params.push({
                    name: 'Common',
                    params: [
                        {
                            name: 'BRANCH',
                            type: 'string',
                        },
                    ],
                })
            }

            for (const s of branch.stages) {
                if (
                    s.schema.parent !== 'root' ||
                    s.schema.triggers.parent === false
                ) {
                    continue
                }
                params.push({
                    name: s.name,
                    params: s.schema.parameters,
                })
                args[s.name] = {}
                for (const p of s.schema.parameters) {
                    args[s.name][p.name] = p._default
                }
            }
            this.params = params
            this.args = args
        })
    }

    submitFlow() {
        const flow = {
            args: this.args,
        }
        this.executionService
            .createFlow(this.branchId, this.kind, flow)
            .subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Flow started',
                        detail: 'Starting flow succeeded.',
                    })
                    this.router.navigate(['/flows/' + data.id])
                },
                (err) => {
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Flow start erred',
                        detail: 'Starting flow erred: ' + msg,
                        life: 10000,
                    })
                }
            )
    }
}
