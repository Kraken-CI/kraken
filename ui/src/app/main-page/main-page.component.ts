import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {PanelModule} from 'primeng/panel';
import {TreeModule} from 'primeng/tree';
import {TreeNode} from 'primeng/api';
import {MessageService} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { ManagementService } from '../backend/api/management.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { datetimeToLocal } from '../utils';

@Component({
  selector: 'app-main-page',
  templateUrl: './main-page.component.html',
  styleUrls: ['./main-page.component.sass']
})
export class MainPageComponent implements OnInit {

    projects: any[];

    selectedProject = {name: '', id: 0};
    newBranchDlgVisible = false;
    branchName = "";

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected managementService: ManagementService,
                protected breadcrumbService: BreadcrumbsService,
                private msgSrv: MessageService) { }

    ngOnInit() {
        this.breadcrumbService.setCrumbs([{
            label: 'Projects',
            url: '/',
            id: 0
        }]);

        this.refresh();
    }

    refresh() {
        this.executionService.getProjects().subscribe(data => {
            for (let proj of data.items) {
                let branches = []
                for (let b of proj.branches) {
                    let ciExtraText = 'no flows yet';
                    if (b.ci_flows.length > 0) {
                        ciExtraText = 'last flow: ' + datetimeToLocal(b.ci_flows[0].created);
                    }
                    let devExtraText = 'no flows yet';
                    if (b.dev_flows.length > 0) {
                        devExtraText = 'last flow: ' + datetimeToLocal(b.dev_flows[0].created);
                    }
                    let br = {
                        label: b.name,
                        branchId: b.id,
                        'type': 'branch',
                        icon: "fa fa-code-fork",
                        children: [{
                            label: 'CI',
                            'type': 'ci_dev',
                            extraText: ciExtraText,
                            url: '/branches/' + b.id + '/ci',
                            children: []
                        }, {
                            label: 'dev',
                            'type': 'ci_dev',
                            extraText: devExtraText,
                            url: '/branches/' + b.id + '/dev',
                            children: []
                        }]
                    };
                    for (let f of b.ci_flows) {
                        br.children[0].children.push({
                            label: datetimeToLocal(f.created) + ', stages:' + f.runs.length,
                            icon: 'fa fa-th-list',
                            id: f.id
                        });
                    }
                    for (let f of b.dev_flows) {
                        br.children[1].children.push({
                            label: datetimeToLocal(f.created) + ', stages:' + f.runs.length,
                            icon: 'fa fa-th-list',
                            id: f.id
                        });
                    }
                    branches.push(br);
                }
                proj.branches = branches;
            }
            this.projects = data.items;
        });
    }

    newBranch(project) {
        this.newBranchDlgVisible = true;
        this.selectedProject = project;
    }

    cancelNewBranch() {
        this.newBranchDlgVisible = false;
    }

    keyDown(event) {
        if (event.key == "Enter") {
            this.addNewBranch();
        }
    }

    addNewBranch() {
        this.managementService.createBranch(this.selectedProject.id, {name: this.branchName}).subscribe(
            data => {
                console.info(data);
                this.msgSrv.add({severity:'success', summary:'New branch succeeded', detail:'New branch operation succeeded.'});
                this.newBranchDlgVisible = false;
                this.refresh();
            },
            err => {
                console.info(err);
                let msg = err.statusText;
                if (err.error && err.error.detail) {
                    msg = err.error.detail;
                }
                this.msgSrv.add({severity:'error', summary:'New branch erred', detail:'New branch operation erred: ' + msg, sticky: true});
                this.newBranchDlgVisible = false;
            });
    }
}
