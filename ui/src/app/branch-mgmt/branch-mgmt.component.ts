import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {MessageService} from 'primeng/api';
import {ConfirmationService} from 'primeng/api';

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
    newBranchName: string

    newStageDlgVisible = false
    stageName = ""
    newStageName: string
    newStageDescr: string

    stage: any = {id: 0, name: '', description: ''};
    saveErrorMsg = "";

    codeMirrorOpts = {
        lineNumbers: true,
        theme: 'material',
        mode: "text/x-python",
        indentUnit: 4,
        gutters: ["CodeMirror-lint-markers"],
        lint: true
    };

    codeMirrorJsonOpts = {
        lineNumbers: true,
        theme: 'material',
        mode: "application/json"
    };

    schemaCheckDisplay = false
    schemaCheckContent: any

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected managementService: ManagementService,
                protected breadcrumbService: BreadcrumbsService,
                private msgSrv: MessageService,
                private confirmationService: ConfirmationService) {
    }

    ngOnInit() {
        this.schemaCheckContent = {schema: '', error: ''}
        this.branchId = parseInt(this.route.snapshot.paramMap.get("id"));
        this.refresh()
    }

    refresh() {
        this.managementService.getBranch(this.branchId).subscribe(branch => {
            this.branch = branch;
            this.newBranchName = branch.name
            if (this.stageName != '') {
                // this is a finish of adding new stage ie. select newly created stage
                for (let s of this.branch.stages) {
                    if (s.name == this.stageName) {
                        this.stage = s
                        this.stageName = ''
                        break
                    }
                }
            }
            if (this.stage.id === 0) {
                this.selectStage(branch.stages[0])
            }

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
        if (this.stage) {
            this.stage.selectedClass = ''
        }
        this.stage = stage
        this.stage.selectedClass = 'selectedClass'
    }

    newStage() {
        this.newStageDlgVisible = true;
    }

    cancelNewStage() {
        this.newStageDlgVisible = false;
    }

    newStageKeyDown(event) {
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
                this.msgSrv.add({severity:'error', summary:'New stage erred', detail:'New stage operation erred: ' + msg, life: 10000});
                this.newStageDlgVisible = false;
            });
    }

    saveStage() {
        this.saveErrorMsg = ""
        let stage = {
            name: this.stage.name,
            schema_code: this.stage.schema_code,
            enabled: this.stage.enabled,
        }
        this.doSaveStage(stage)
    }

    checkStageSchema() {
        this.managementService.getStageSchemaAsJson(this.stage.id, {schema_code: this.stage.schema_code}).subscribe(
            data => {
                console.info(data);
                this.schemaCheckContent = data
                this.schemaCheckDisplay = true
            },
            err => {
                console.info(err);
                let msg = err.statusText;
                if (err.error && err.error.detail) {
                    msg = err.error.detail;
                }
                this.msgSrv.add({severity:'error', summary:'Check schema erred', detail:'Check schema operation erred: ' + msg, life: 10000});
            });
    }

    deleteStage() {
        this.confirmationService.confirm({
            message: 'Do you really want to delete stage "' + this.stage.name + '"?',
            accept: () => {
                this.managementService.deleteStage(this.stage.id).subscribe(
                    stage => {
                        this.selectStage(this.branch.stages[0])
                        this.msgSrv.add({severity:'success', summary:'Stage deletion succeeded', detail:'Stage deletion operation succeeded.'});
                        this.refresh()
                    },
                    err => {
                        console.info(err);
                        let msg = err.statusText;
                        if (err.error && err.error.detail) {
                            msg = err.error.detail;
                        }
                        this.msgSrv.add({severity:'error', summary:'Stage deletion erred', detail:'Stage deletion operation erred: ' + msg, life: 10000});
                    }
                );
            }
        })
    }

    branchNameKeyDown(event, branchNameInplace) {
        if (event.key == "Enter") {
            branchNameInplace.deactivate()
        }
        if (event.key == "Escape") {
            branchNameInplace.deactivate()
            this.newBranchName = this.branch.name
        }
    }

    doSaveStage(stageData) {
        this.managementService.updateStage(this.stage.id, stageData).subscribe(
            stage => {
                this.selectStage(stage)
                for (let idx in this.branch.stages) {
                    if (this.branch.stages[idx].id == stage.id) {
                        this.branch.stages[idx] = stage
                        break
                    }
                }
                this.msgSrv.add({severity:'success', summary:'Stage update succeeded', detail:'Stage update operation succeeded.'});
            },
            err => {
                console.info(err);
                let msg = err.statusText;
                if (err.error && err.error.detail) {
                    msg = err.error.detail;
                }
                this.msgSrv.add({severity:'error', summary:'Stage update erred', detail:'Stage update operation erred: ' + msg, life: 10000});
            }
        );
    }

    stageNameInplaceActivated() {
        this.newStageName = this.stage.name
    }

    stageNameKeyDown($event, stageNameInplace) {
        if (event['key'] == "Enter") {
            stageNameInplace.deactivate()
            let stage = {
                name: this.newStageName,
            }
            this.doSaveStage(stage)
        }
        if (event['key'] == "Escape") {
            stageNameInplace.deactivate()
        }
    }

    stageDescrInplaceActivated() {
        this.newStageDescr = this.stage.description
    }

    stageDescrKeyDown($event, stageDescrInplace) {
        if (event['key'] == "Enter") {
            stageDescrInplace.deactivate()
            let stage = {
                name: this.stage.name,
                description: this.newStageDescr,
            }
            this.doSaveStage(stage)
        }
        if (event['key'] == "Escape") {
            stageDescrInplace.deactivate()
        }
    }

    forkBranch() {
    }
}
