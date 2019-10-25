import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import 'codemirror/mode/javascript/javascript';

import {MessageService} from 'primeng/api';

import { ManagementService } from '../backend/api/management.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { Branch } from '../backend/model/models';

@Component({
  selector: 'app-branch-mgmt',
  templateUrl: './branch-mgmt.component.html',
  styleUrls: ['./branch-mgmt.component.sass']
})
export class BranchMgmtComponent implements OnInit {

    branchId: number;
    branch: Branch = {id: 0, name: 'noname', stages: []};

    newStageDlgVisible = false
    stageName = ""

    stage: any = {name: '', description: ''};
    saveErrorMsg = "";

    codeMirrorOpts = {
        lineNumbers: true,
        theme: 'material',
        mode: "application/json",
        gutters: ["CodeMirror-lint-markers"],
        lint: true
    };

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected managementService: ManagementService,
                protected breadcrumbService: BreadcrumbsService,
                private msgSrv: MessageService) {
    }

    ngOnInit() {
        this.branchId = parseInt(this.route.snapshot.paramMap.get("id"));
        this.refresh()
    }

    refresh() {
        this.managementService.getBranch(this.branchId).subscribe(branch => {
            this.branch = branch;
            this.stage = branch.stages[0];
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
    }

    selectStage(stage) {
        this.stage = stage;
    }

    newStage() {
        this.newStageDlgVisible = true;
    }

    cancelNewStage() {
        this.newStageDlgVisible = false;
    }

    keyDown(event) {
        if (event.key == "Enter") {
            this.addNewStage();
        }
    }

    addNewStage() {
        this.managementService.createStage(this.branchId, {name: this.stageName}).subscribe(
            data => {
                console.info(data);
                this.msgSrv.add({severity:'success', summary:'New stage succeeded', detail:'New stage operation succeeded.'});
                this.newStageDlgVisible = false;
                this.refresh();
            },
            err => {
                console.info(err);
                let msg = err.statusText;
                if (err.error && err.error.detail) {
                    msg = err.error.detail;
                }
                this.msgSrv.add({severity:'error', summary:'New stage erred', detail:'New stage operation erred: ' + msg, sticky: true});
                this.newStageDlgVisible = false;
            });
    }

    saveStage() {
        let schema: string
        try {
            schema = JSON.parse(this.stage.schema_txt);
        } catch (e) {
            this.saveErrorMsg = 'Syntax error in schema content: ' + e.message;
            return
        }
        let stage = {
            name: this.stage.name,
            schema: schema
        }
        this.managementService.updateStage(this.stage.id, stage).subscribe(stage => {
            this.stage = stage
            for (let idx in this.branch.stages) {
                if (this.branch.stages[idx].id == stage.id) {
                    this.branch.stages[idx] = stage
                    break
                }
            }
        });
    }
}
