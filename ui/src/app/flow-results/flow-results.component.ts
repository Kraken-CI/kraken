import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {TreeNode} from 'primeng/api';
import {MenuItem} from 'primeng/api';
import {MessageService} from 'primeng/api';

import { ManagementService } from '../backend/api/management.service';
import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';

@Component({
  selector: 'app-flow-results',
  templateUrl: './flow-results.component.html',
  styleUrls: ['./flow-results.component.sass']
})
export class FlowResultsComponent implements OnInit {

    flowId = 0;
    flow = null;
    runs: any[];
    runsTree: TreeNode[];
    flatTree: any[]

    args: any[]

    nodeMenuItems: MenuItem[];

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected managementService: ManagementService,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService,
                private msgSrv: MessageService) { }

    ngOnInit() {
        this.route.paramMap.subscribe(params => {
            this.flowId = parseInt(params.get("id"))

            this.runsTree = [{
                label: `Flow [${this.flowId}]`,
                expanded: true,
                'type': 'root',
                data: {created: ''},
                children: []
            }];

            this.refresh()
        })
    }

    _getRunForStage(stageName) {
        for (let run of this.flow.runs) {
            if (run.name == stageName) {
                return run;
            }
        }
        return null;
    }

    _getParamFromStage(stageName, paramName) {
        for (let stage of this.flow.stages) {
            if (stage.name == stageName) {
                for (let param of stage.schema.parameters) {
                    if (param.name == paramName) {
                        return param
                    }
                }
            }
        }
        return null;
    }

    _buildSubtree(node, allParents, children) {
        for (let c of children) {
            let subtree = {
                label: c.name,
                expanded: true,
                data: {
                    stage: c,
                    run: this._getRunForStage(c.name)
                }
            }
            if (allParents[c.name] != undefined) {
                this._buildSubtree(subtree, allParents, allParents[c.name])
            }
            if (node['children'] == undefined) {
                node['children'] = []
            }
            node['children'].push(subtree)
        }
    }

    _traverseTree(node, level) {
        if (node.data.run || node.data.stage) {
            this.flatTree.push({
                level: level,
                run: node.data.run,
                stage: node.data.stage,
            })
        }
        if (node['children']) {
            for (let c of node['children']) {
                this._traverseTree(c, level + 1)
            }
        }
    }

    refresh() {
        this.executionService.getFlow(this.flowId).subscribe(flow => {
            this.flow = flow;
            let crumbs = [{
                label: 'Projects',
                project_id: flow.project_id,
                project_name: flow.project_name
            }, {
                label: 'Branches',
                branch_id: flow.branch_id,
                branch_name: flow.base_branch_name
            }, {
                label: 'Results',
                branch_id: flow.branch_id,
                flow_kind: flow.kind
            }, {
                label: 'Flows',
                flow_id: flow.id
            }];
            this.breadcrumbService.setCrumbs(crumbs);

            // collect args from flow
            let args = []
            let sectionArgs = []
            if (this.flow.kind == 'dev') {
                sectionArgs.push({
                    name: 'BRANCH',
                    value: this.flow.branch_name,
                })
            }
            args.push({
                name: 'Common',
                args: sectionArgs
            })
            // collect args from runs
            for (let run of this.flow.runs) {
                sectionArgs = []
                for (let a in run.args) {
                    let param = this._getParamFromStage(run.name, a)
                    let description = ''
                    let defaultValue
                    if (param) {
                        description = param.description
                        defaultValue = param['default']
                    }

                    sectionArgs.push({
                        name: a,
                        value: run.args[a],
                        description: description,
                        'default': defaultValue
                    })
                }
                if (sectionArgs.length > 0) {
                    args.push({
                        name: run.name,
                        args: sectionArgs
                    })
                }
            }
            this.args = args

            // build tree of runs
            let allParents = {
                root: []
            }
            for (let stage of flow.stages) {
                if (allParents[stage.schema.parent] == undefined) {
                    allParents[stage.schema.parent] = []
                }
                allParents[stage.schema.parent].push(stage)
            }

            this.runsTree = [{
                label: `Flow [${this.flowId}]`,
                expanded: true,
                'type': 'root',
                data: flow
            }];
            this._buildSubtree(this.runsTree[0], allParents, allParents['root'])
            //console.info(this.runsTree);

            this.flatTree = []
            this._traverseTree(this.runsTree[0], 0)
            //console.info('flatTree', this.flatTree);
        });
    }

    showNodeMenu($event, nodeMenu, node) {
        console.info(node)

        if (node.data.run) {
            this.nodeMenuItems = [{
                label: 'Show Details',
                icon: 'pi pi-folder-open',
                routerLink: "/runs/" + node.data.run.id,
            }, {
                label: 'Rerun',
                icon: 'pi pi-replay',
            }];
        } else {
            this.nodeMenuItems = [{
                label: 'Run this stage',
                icon: 'pi pi-caret-right',
                command: () => {
                    let stage = node.data.stage
                    console.info(stage.schema.parameters)
                    if (stage.schema.parameters.length == 0) {
                        this.executionService.createRun(this.flowId, stage.id).subscribe(
                            data => {
                                this.msgSrv.add({severity:'success', summary:'Run succeeded', detail:'Run operation succeeded.'});
                                this.refresh()
                            },
                            err => {
                                this.msgSrv.add({severity:'error', summary:'Run erred', detail:'Run operation erred: ' + err.statusText, life: 10000});
                            });
                    } else {
                        this.router.navigate(['/flows/' + this.flowId + '/runs/new']);
                    }
                }
            }];
        }
        nodeMenu.toggle($event);
    }

    onStageRun(newRun) {
        //console.info(newRun)
        this.refresh()
    }
}
