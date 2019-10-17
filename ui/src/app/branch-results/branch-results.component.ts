import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';
import { Observable } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import {DropdownModule} from 'primeng/dropdown';
import {MenuModule} from 'primeng/menu';
import {MenuItem} from 'primeng/api';
import {MessageService} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { Run } from '../backend/model/run';
import { datetimeToLocal } from '../utils';

@Component({
  selector: 'app-branch-results',
  templateUrl: './branch-results.component.html',
  styleUrls: ['./branch-results.component.sass']
})
export class BranchResultsComponent implements OnInit {
    branchId = 0;

    flows0: any[];
    flows: any[];

    stagesAvailable: any[];
    selectedStages: any[];
    selectedStage: any;
    filterStageName = 'All';

    runMenuItems: MenuItem[];

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService,
                private msgSrv: MessageService) { }

    ngOnInit() {
        this.runMenuItems = [{
            label: 'Show Details',
            icon: 'pi pi-folder-open',
        },
        {
            label: 'Rerun',
            icon: 'pi pi-replay',
        }];
        this.branchId = parseInt(this.route.snapshot.paramMap.get("id"));
        this.selectedStage = null;
        this.stagesAvailable = [
            {name: 'All'}
        ];
        this.flows0 = [{
            name: '278',
            state: 'completed',
            created: '2019-09-13 15:30 UTC',
            runs: [{
                name: 'Tarball',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m'
            }, {
                name: 'Package',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
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
                issues: 12,
            }, {
                name: 'Deploy',
                state: 'not-run',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod 2',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod 3',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod 4',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }]
        }, {
            name: '277',
            created: '2019-09-13 15:30 UTC',
            state: 'completed',
            runs: [{
                name: 'Tarball',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Package',
                state: 'completed',
                color: '#ffe6e6',
                jobs_total: 18,
                jobs_error: 3,
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy',
                color: '#ffffff',
                state: 'not-run',
                started: 'not run',
                duration: '---',
            }]
        }, {
            name: '276',
            created: '2019-09-13 15:30 UTC',
            state: 'completed',
            runs: [{
                name: 'Tarball',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Package',
                color: '#e6ffe6',
                state: 'completed',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'System Tests',
                state: 'completed',
                color: '#fff9e6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
                tests_passed: 987,
                tests_total: 1033
            }, {
                name: 'Deploy',
                state: 'not-run',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }]
        }, {
            name: '275',
            created: '2019-09-13 15:30 UTC',
            state: 'in-progress',
            runs: [{
                name: 'Tarball',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Package',
                state: 'completed',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'System Tests',
                state: 'completed',
                color: '#fff9e6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
                tests_passed: 987,
                tests_total: 1033
            }, {
                name: 'Static Analysis',
                state: 'not-run',
                color: '#fff9e6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
                issues: 78
            }, {
                name: 'Deploy',
                state: 'not-run',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }]
        }];

        this.executionService.getBranch(this.branchId).subscribe(branch => {
            let crumbs = [{
                label: 'Projects',
                url: '/projects/' + branch.project_id,
                id: branch.project_name
            }, {
                label: 'Branches',
                url: '/branches/' + branch.id,
                id: branch.name
            }];
            this.breadcrumbService.setCrumbs(crumbs);
        });

        this.refresh();
    }

    newFlow() {
        this.executionService.createFlow(1).subscribe(data => {
            //console.info(data);
            let stages = new Set<string>();
            this._processFlowData(data, stages);
            this.flows.unshift(data)
            let newStages = [{name: 'All'}];
            for (let st of Array.from(stages).sort()) {
                newStages.push({name: st});
            }
            this.stagesAvailable = newStages;
        });
    }

    _processFlowData(flow, stages) {
        flow['created'] = datetimeToLocal(flow['created']);
        for (let run of flow['runs']) {
            stages.add(run['name']);
            run['started'] = datetimeToLocal(run['started']);
            if (run['jobs_error'] && run['jobs_error'] > 0) {
                run['color'] = '#ffe6e6';
            }
            else if (run['state'] == 'completed') {
                if (run['tests_passed'] && run['tests_total'] && run['tests_passed'] < run['tests_total']) {
                    run['color'] = '#fff9e6';
                } else {
                    run['color'] = '#e6ffe6';
                }
            }
        }
    }

    refresh() {
        // this.hero$ = this.route.paramMap.pipe(
        //     switchMap((params: ParamMap) =>
        //               this.service.getHero(params.get('id')))
        // );
        this.route.paramMap.pipe(
            switchMap((params: ParamMap) =>
                      this.executionService.getFlows(parseInt(params.get('id'))))
        ).subscribe(data => {
            //console.info(data);
            var flows = [];
            let stages = new Set<string>();
            flows = flows.concat(data);
            flows = flows.concat(this.flows0)
            for (let flow of flows) {
                              this._processFlowData(flow, stages);
            }
            this.flows = flows;
            let newStages = [{name: 'All'}];
            for (let st of Array.from(stages).sort()) {
                newStages.push({name: st});
            }
            this.stagesAvailable = newStages;
        });
    }

    filterStages(event) {
        this.filterStageName = event.value.name;
    }

    showRunMenu($event, runMenu, run) {
        console.info(runMenu);
        console.info(run);
        this.runMenuItems[0].routerLink = "/runs/" + run.id;
        this.runMenuItems[1].command = () => {
            this.executionService.replayRun(run.id).subscribe(
                data => {
                    console.info(data);
                    this.msgSrv.add({severity:'success', summary:'Replay succeeded', detail:'Replay operation succeeded.'});
                },
                err => {
                    console.info(err);
                    this.msgSrv.add({severity:'error', summary:'Replay erred', detail:'Replay operation erred: ' + err.statusText, sticky: true});
                });
        };
        runMenu.toggle($event);
    }
}
