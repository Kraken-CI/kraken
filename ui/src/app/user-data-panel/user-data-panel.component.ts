import { Component, OnInit, OnDestroy, Input } from '@angular/core';

import { Subscription } from 'rxjs'

import { MessageService } from 'primeng/api'

import { ExecutionService } from '../backend/api/execution.service'
import { showErrorBox } from '../utils'

@Component({
  selector: 'app-user-data-panel',
  templateUrl: './user-data-panel.component.html',
  styleUrls: ['./user-data-panel.component.sass']
})
export class UserDataPanelComponent implements OnInit, OnDestroy {
    @Input() flowId: number
    @Input() branchId: number
    @Input() projectId: number

    data = ''
    dataCI = ''
    dataDev = ''

    private subs: Subscription = new Subscription()

    constructor(
        protected executionService: ExecutionService,
        private msgSrv: MessageService,
    ) { }

    ngOnInit(): void {
        let scope
        let entityId
        if (this.flowId) {
            scope = 'flow'
            entityId = this.flowId
        } else if (this.branchId) {
            scope = 'branch'
            entityId = this.branchId
        } else if (this.projectId) {
            scope = 'project'
            entityId = this.projectId
        }

        this.subs.add(
            this.executionService.getUserData(scope, entityId).subscribe(
                (data) => {
                    this.data = data.data
                },
                (err) => {
                    showErrorBox(
                        this.msgSrv,
                        err,
                        'Getting user data erred'
                    )
                }
            )
        )

        if (this.branchId) {
            this.subs.add(
                this.executionService.getUserData('branch-ci', entityId).subscribe(
                    (data) => {
                        this.dataCI = data.data
                    },
                    (err) => {
                        showErrorBox(
                            this.msgSrv,
                            err,
                            'Getting user data erred'
                        )
                    }
                )
            )

            this.subs.add(
                this.executionService.getUserData('branch-dev', entityId).subscribe(
                    (data) => {
                        this.dataDev = data.data
                    },
                    (err) => {
                        showErrorBox(
                            this.msgSrv,
                            err,
                            'Getting user data erred'
                        )
                    }
                )
            )
        }
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }
}
