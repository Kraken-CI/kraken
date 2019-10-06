import { Component } from '@angular/core';

//import moment from 'moment';
import moment from "moment-timezone";

import {PanelMenuModule} from 'primeng/panelmenu';
import {MenuModule} from 'primeng/menu';
import {MenuItem} from 'primeng/api';
import {SplitButtonModule} from 'primeng/splitbutton';

import { ExecutionService } from './backend/api/execution.service';
import { Run } from './backend/model/run';


function datetimeToLocal(d) {
    try {
        var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (!tz) {
            tz = moment.tz.guess()
        }
        if (tz) {
            d = moment(d).tz(tz)
            tz = ''
        } else {
            d = moment(d)
            tz = ' UTC'
        }

        return d.format('YYYY-MM-DD hh:mm:ss') + tz;
    } catch(e) {
        return d;
    }
}


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.sass']
})
export class AppComponent {
    title = 'Kraken';

    items: MenuItem[];
    sItems: MenuItem[];
    flows0: any[];
    flows: any[];

    constructor(protected executionService: ExecutionService) {
    }

    ngOnInit() {
        this.flows0 = [{
            name: '278',
            state: 'done',
            created: '2019-09-13 15:30 UTC',
            runs: [{
                name: 'Tarball',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m'
            }, {
                name: 'Package',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'System Tests',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
                jobs_total: 103,
                jobs_error: 78,
                jobs_rerun: 7,
                jobs_pending: 2,
                passed: 987,
                total: 1033,
                issues: 12,
            }, {
                name: 'Deploy',
                state: 'not-run',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod 2',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod 3',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Deploy Prod 4',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }]
        }, {
            name: '277',
            created: '2019-09-13 15:30 UTC',
            state: 'done',
            runs: [{
                name: 'Tarball',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Package',
                state: 'done',
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
            state: 'done',
            runs: [{
                name: 'Tarball',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Package',
                color: '#e6ffe6',
                state: 'done',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'System Tests',
                state: 'done',
                color: '#fff9e6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
                passed: 987,
                total: 1033
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
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'Package',
                state: 'done',
                color: '#e6ffe6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
            }, {
                name: 'System Tests',
                state: 'done',
                color: '#fff9e6',
                started: '2019-09-13 15:30 UTC',
                duration: '3h 40m',
                passed: 987,
                total: 1033
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
        this.items = [{
            label: 'Dashboard',
            icon: 'pi pi-pw pi-home',
            items: [{
                label: 'New',
                icon: 'pi pi-fw pi-plus',
                items: [
                    {label: 'User', icon: 'pi pi-fw pi-user-plus'},
                    {label: 'Filter', icon: 'pi pi-fw pi-filter'}
                ]
            }, {
                label: 'Open', icon: 'pi pi-fw pi-external-link'
            }, {
                separator: true
            }, {
                label: 'Quit', icon: 'pi pi-fw pi-times'
            }, {
                label: 'Edit',
                icon: 'pi pi-fw pi-pencil',
            }]
        }];

        this.sItems = [
            {label: 'Update', icon: 'pi pi-refresh', command: () => {
                //this.update();
            }},
            {label: 'Delete', icon: 'pi pi-times', command: () => {
                //this.delete();
            }},
            {label: 'Angular.io', icon: 'pi pi-info', url: 'http://angular.io'},
            {label: 'Setup', icon: 'pi pi-cog', routerLink: ['/setup']}
        ];

        this.refresh();
    }

    newFlow() {
        this.executionService.createFlow(1).subscribe(data => {
            console.info(data);
        });
    }

    refresh() {
        this.executionService.getFlows(1).subscribe(data => {
            for (let flow of data) {
                flow['created'] = datetimeToLocal(flow['created']);
                for (let run of flow['runs']) {
                    run['started'] = datetimeToLocal(run['started']);
                }
            }
            this.flows = this.flows0.concat(data);
            console.info(data);
        });
    }
}
