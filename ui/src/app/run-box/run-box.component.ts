import {
    Component,
    Input,
    Output,
    EventEmitter,
    OnInit,
    OnDestroy,
} from '@angular/core'
import { Router } from '@angular/router'

import { Subscription } from 'rxjs'

import { MenuItem } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { AuthService } from '../auth.service'
import { ExecutionService } from '../backend/api/execution.service'
import { Run, Stage } from '../backend/model/models'

@Component({
    selector: 'app-run-box',
    templateUrl: './run-box.component.html',
    styleUrls: ['./run-box.component.sass'],
})
export class RunBoxComponent implements OnInit, OnDestroy {
    @Input() projectId: number
    @Input() run: Run
    @Input() stage: Stage
    @Input() flowId: number
    @Input() selectionEnabled = false
    @Input() selected = false
    @Output() stageRun = new EventEmitter<any>()
    @Output() boxSelect = new EventEmitter<any>()

    runBoxMenuItems: MenuItem[]

    bgColor = ''

    private subs: Subscription = new Subscription()

    constructor(
        private router: Router,
        public auth: AuthService,
        protected executionService: ExecutionService,
        private msgSrv: MessageService
    ) {}

    ngOnInit() {
        if (this.run) {
            // prepare menu items for run box
            const opName = this.run.state === 'manual' ? 'Start' : 'Rerun'
            this.runBoxMenuItems = [
                {
                    label: 'Show Details',
                    icon: 'pi pi-folder-open',
                    routerLink: '/runs/' + this.run.id + '/jobs',
                },
                {
                    label: opName,
                    icon:
                        this.run.state === 'manual'
                            ? 'pi pi-caret-right'
                            : 'pi pi-replay',
                    command: () => {
                        this.runRunJobs(opName)
                    },
                    disabled: !this.auth.hasPermission(this.projectId, 'pwrusr'),
                    title: this.auth.permTip(this.projectId, 'pwrusr'),
                },
            ]

            if (
                this.run.state === 'in-progress' ||
                this.run.state === 'creating'
            ) {
                this.runBoxMenuItems.push({
                    label: 'Cancel',
                    icon: 'pi pi-times',
                    command: () => {
                        this.cancelRun()
                    },
                    disabled: !this.auth.hasPermission(this.projectId, 'pwrusr'),
                    title: this.auth.permTip(this.projectId, 'pwrusr'),
                })
            }

            // calculate bg color for box
            if (this.run.jobs_error && this.run.jobs_error > 0) {
                this.bgColor = 'var(--redish)'
            } else if (
                this.run.state === 'completed' ||
                this.run.state === 'processed'
            ) {
                if (
                    (this.run.tests_passed &&
                        this.run.tests_total &&
                        this.run.tests_passed < this.run.tests_total) ||
                    (this.run.issues_total && this.run.issues_total > 0)
                ) {
                    this.bgColor = 'var(--orangish)'
                } else if (this.run.jobs_total === 0) {
                    this.bgColor = 'var(--redish)'
                } else {
                    this.bgColor = 'var(--greenish)'
                }
            } else if (this.run.state === 'manual') {
                this.bgColor = 'var(--blueish)'
            }
        } else {
            // prepare menu items for stage box
            this.runBoxMenuItems = [
                {
                    label: 'Run this stage',
                    icon: 'pi pi-caret-right',
                    command: () => {
                        if (this.stage.schema.parameters.length === 0) {
                            this.subs.add(
                                this.executionService
                                    .createRun(this.flowId, {
                                        stage_id: this.stage.id,
                                    })
                                    .subscribe(
                                        (data) => {
                                            this.msgSrv.add({
                                                severity: 'success',
                                                summary: 'Run succeeded',
                                                detail: 'Run operation succeeded.',
                                            })
                                            this.stageRun.emit(data)
                                        },
                                        (err) => {
                                            this.msgSrv.add({
                                                severity: 'error',
                                                summary: 'Run erred',
                                                detail:
                                                    'Run operation erred: ' +
                                                    err.statusText,
                                                life: 10000,
                                            })
                                        }
                                    )
                            )
                        } else {
                            this.router.navigate([
                                '/flows/' +
                                    this.flowId +
                                    '/stages/' +
                                    this.stage.id +
                                    '/new',
                            ])
                        }
                    },
                    disabled: !this.auth.hasPermission(this.projectId, 'pwrusr'),
                    title: this.auth.permTip(this.projectId, 'pwrusr'),
                },
            ]
        }
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    showRunMenu($event, runMenu, run) {
        runMenu.toggle($event)
    }

    runRunJobs(opName) {
        this.subs.add(
            this.executionService.runRunJobs(this.run.id).subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: opName + ' succeeded',
                        detail: opName + ' operation succeeded.',
                    })
                },
                (err) => {
                    this.msgSrv.add({
                        severity: 'error',
                        summary: opName + ' erred',
                        detail: opName + ' operation erred: ' + err.statusText,
                        life: 10000,
                    })
                }
            )
        )
    }

    cancelRun() {
        this.subs.add(
            this.executionService.cancelRun(this.run.id).subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: ' succeeded',
                        detail: 'Cancel operation succeeded.',
                    })
                },
                (err) => {
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Cancel erred',
                        detail: 'Cancel operation erred: ' + err.statusText,
                        life: 10000,
                    })
                }
            )
        )
    }

    onBoxClick() {
        this.selected = true
        this.boxSelect.emit()
    }
}
