import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core'
import { Router } from '@angular/router'

import { MenuItem } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { ExecutionService } from '../backend/api/execution.service'
import { Run, Stage } from '../backend/model/models'

@Component({
    selector: 'app-run-box',
    templateUrl: './run-box.component.html',
    styleUrls: ['./run-box.component.sass'],
})
export class RunBoxComponent implements OnInit {
    @Input() run: Run
    @Input() stage: Stage
    @Input() flowId: number
    @Output() stageRun = new EventEmitter<any>()

    runBoxMenuItems: MenuItem[]

    bgColor = ''

    constructor(
        private router: Router,
        protected executionService: ExecutionService,
        private msgSrv: MessageService
    ) {}

    ngOnInit() {
        if (this.run) {
            // prepare menu items for run box
            this.runBoxMenuItems = [
                {
                    label: 'Show Details',
                    icon: 'pi pi-folder-open',
                    routerLink: '/runs/' + this.run.id + '/jobs',
                },
                {
                    label: 'Rerun',
                    icon: 'pi pi-replay',
                    command: () => {
                        this.executionService.replayRun(this.run.id).subscribe(
                            data => {
                                this.msgSrv.add({
                                    severity: 'success',
                                    summary: 'Replay succeeded',
                                    detail: 'Replay operation succeeded.',
                                })
                            },
                            err => {
                                this.msgSrv.add({
                                    severity: 'error',
                                    summary: 'Replay erred',
                                    detail:
                                        'Replay operation erred: ' +
                                        err.statusText,
                                    life: 10000,
                                })
                            }
                        )
                    },
                },
            ]

            // calculate bg color for box
            if (this.run.jobs_error && this.run.jobs_error > 0) {
                this.bgColor = 'linear-gradient(90deg, rgba(255,230,230,1) 0%, rgba(227,193,193,1) 100%)' // redish
            } else if (this.run.state === 'completed' || this.run.state === 'processed') {
                if (
                    this.run.tests_passed &&
                    this.run.tests_total &&
                    this.run.tests_passed < this.run.tests_total
                ) {
                    this.bgColor = 'linear-gradient(90deg, rgba(255,230,230,1) 0%, rgba(227,193,193,1) 100%)' // redish
                } else {
                    this.bgColor = 'linear-gradient(90deg, rgba(230,255,230,1) 0%, rgba(193,227,193,1) 100%)' // greenish
                }
            }
        } else {
            // prepare menu items for stage box
            this.runBoxMenuItems = [
                {
                    label: 'Run this stage',
                    icon: 'pi pi-caret-right',
                    command: () => {
                        if (this.stage.schema.parameters.length === 0) {
                            this.executionService
                                .createRun(this.flowId, {
                                    stage_id: this.stage.id,
                                })
                                .subscribe(
                                    data => {
                                        this.msgSrv.add({
                                            severity: 'success',
                                            summary: 'Run succeeded',
                                            detail: 'Run operation succeeded.',
                                        })
                                        this.stageRun.emit(data)
                                    },
                                    err => {
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
                },
            ]
        }
    }

    showRunMenu($event, runMenu, run) {
        runMenu.toggle($event)
    }
}
