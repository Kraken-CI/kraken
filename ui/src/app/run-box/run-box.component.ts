import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';

import {MenuItem} from 'primeng/api';
import {MessageService} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { Run } from '../backend/model/run';

@Component({
  selector: 'app-run-box',
  templateUrl: './run-box.component.html',
  styleUrls: ['./run-box.component.sass']
})
export class RunBoxComponent implements OnInit {

    @Input() run: Run
    @Input() flowId: number
    @Output() onStageRun = new EventEmitter<any>();

    runBoxMenuItems: MenuItem[];

    bgColor = '#fff';

    constructor(protected executionService: ExecutionService,
                private msgSrv: MessageService) { }

    ngOnInit() {
        if (this.run.started) {
            // prepare menu items for run box
            this.runBoxMenuItems = [{
                label: 'Show Details',
                icon: 'pi pi-folder-open',
                routerLink: "/runs/" + this.run.id
            }, {
                label: 'Rerun',
                icon: 'pi pi-replay',
                command: () => {
                    this.executionService.replayRun(this.run.id).subscribe(
                        data => {
                            this.msgSrv.add({severity:'success', summary:'Replay succeeded', detail:'Replay operation succeeded.'});
                        },
                        err => {
                            this.msgSrv.add({severity:'error', summary:'Replay erred', detail:'Replay operation erred: ' + err.statusText, sticky: true});
                        });
                }
            }];

            // calculate bg color for box
            if (this.run['jobs_error'] && this.run['jobs_error'] > 0) {
                this.bgColor = '#ffe6e6';
            }
            else if (this.run['state'] == 'completed') {
                if (this.run['tests_passed'] && this.run['tests_total'] && this.run['tests_passed'] < this.run['tests_total']) {
                    this.bgColor = '#fff9e6';
                } else {
                    this.bgColor = '#e6ffe6';
                }
            }

        } else {
            // prepare menu items for stage box
            this.runBoxMenuItems = [{
                label: 'Run this stage',
                icon: 'pi pi-caret-right',
                command: () => {
                    this.executionService.createRun(this.flowId, {stage_id: this.run.id}).subscribe(
                        data => {
                            this.msgSrv.add({severity:'success', summary:'Run succeeded', detail:'Run operation succeeded.'});
                            this.onStageRun.emit(data)
                        },
                        err => {
                            this.msgSrv.add({severity:'error', summary:'Run erred', detail:'Run operation erred: ' + err.statusText, sticky: true});
                        });
                }
            }];
        }
    }

    showRunMenu($event, runMenu, run) {
        runMenu.toggle($event);
    }

}
