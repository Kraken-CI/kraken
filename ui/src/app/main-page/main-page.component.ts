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
    newProjectDlgVisible = false;
    projectName = ""

    projects: any[];

    selectedProject = {name: '', id: 0};
    newBranchDlgVisible = false;
    branchName = ""

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected managementService: ManagementService,
                protected breadcrumbService: BreadcrumbsService,
                private msgSrv: MessageService) { }

    ngOnInit() {
        this.refresh();
    }

    calculateFlowStats(flow) {
        flow.tests_total = 0
        flow.tests_passed = 0
        flow.fix_cnt = 0
        flow.regr_cnt = 0
        flow.issues_new = 0
        for (let run of flow.runs) {
            flow.tests_total += run.tests_total
            flow.tests_passed += run.tests_passed
            flow.fix_cnt += run.fix_cnt
            flow.regr_cnt += run.regr_cnt
            flow.issues_new += run.issues_new
        }
        if (flow.tests_total > 0) {
            flow.tests_pass_ratio = 100 * flow.tests_passed / flow.tests_total
            flow.tests_pass_ratio = flow.tests_pass_ratio.toFixed(1)
            if (flow.tests_total == flow.tests_passed) {
                flow.tests_color = '#beffbe'
            } else if (flow.tests_pass_ratio > 50) {
                flow.tests_color = '#fff089'
            } else {
                flow.tests_color = '#ffc8c8'
            }
        } else {
            flow.tests_color = 'white'
        }
    }

    refresh() {
        this.managementService.getProjects().subscribe(data => {
            this.projects = data.items;
            for (let proj of this.projects) {
                for (let branch of proj.branches) {
                    for (let flow of branch.ci_flows) {
                        this.calculateFlowStats(flow)
                    }
                    for (let flow of branch.dev_flows) {
                        this.calculateFlowStats(flow)
                    }
                }
            }
        });
    }

    getFlows(branch) {
        return [{name: 'CI', flows: branch.ci_flows},
                {name: 'Dev', flows: branch.dev_flows}]
    }

    newProject() {
        this.newProjectDlgVisible = true;
    }

    cancelNewProject() {
        this.newProjectDlgVisible = false;
    }

    newProjectKeyDown(event) {
        if (event.key == "Enter") {
            this.addNewProject();
        }
    }

    addNewProject() {
        this.managementService.createProject({name: this.projectName}).subscribe(
            data => {
                console.info(data);
                this.msgSrv.add({severity:'success', summary:'New project succeeded', detail:'New project operation succeeded.'});
                this.newProjectDlgVisible = false;
                this.selectedProject = data;
                this.refresh();
            },
            err => {
                console.info(err);
                let msg = err.statusText;
                if (err.error && err.error.detail) {
                    msg = err.error.detail;
                }
                this.msgSrv.add({severity:'error', summary:'New project erred', detail:'New project operation erred: ' + msg, life: 10000});
                this.newProjectDlgVisible = false;
            });
    }

    newBranch(project) {
        this.newBranchDlgVisible = true;
        this.selectedProject = project;
    }

    cancelNewBranch() {
        this.newBranchDlgVisible = false;
    }

    newBranchKeyDown(event) {
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
                this.msgSrv.add({severity:'error', summary:'New branch erred', detail:'New branch operation erred: ' + msg, life: 10000});
                this.newBranchDlgVisible = false;
            });
    }
}
