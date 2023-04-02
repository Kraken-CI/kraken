import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core'
import { Router, ActivatedRoute } from '@angular/router'
import { Title } from '@angular/platform-browser'

import { Subscription } from 'rxjs'

import { TreeNode } from 'primeng/api'
import { MenuItem } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { AuthService } from '../auth.service'
import { humanBytes, pick } from '../utils'
import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
    selector: 'app-flow-page',
    templateUrl: './flow-page.component.html',
    styleUrls: ['./flow-page.component.sass'],
})
export class FlowPageComponent implements OnInit, OnDestroy {
    projectId = 0
    flowId = 0
    flow = null
    flowData = ''
    runs: any[]
    runsTree: TreeNode[]
    flatTree: any[]

    args: any[]

    nodeMenuItems: MenuItem[]

    // artifacts
    artifacts: any[]
    totalArtifacts = 0
    loadingArtifacts = false

    refreshTimer: any = null
    refreshing = false

    selectedNode: any = {
        stage: {
            name: '',
            id: null,
        },
        run: null,
        selected: false,
    }

    logsPanelVisible = false
    runLogsPanelVisible = false

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        public auth: AuthService,
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
        private titleService: Title,
        private cd: ChangeDetectorRef
    ) {}

    ngOnInit(): void {
        this.subs.add(
            this.route.paramMap.subscribe((params) => {
                const flowId = parseInt(params.get('id'), 10)

                // only when it is the first load or a flow is changed
                if (flowId !== this.flowId) {
                    this.flowId = flowId
                    this.titleService.setTitle('Kraken - Flow ' + this.flowId)

                    this.runsTree = [
                        {
                            label: `Flow [${this.flowId}]`,
                            expanded: true,
                            type: 'root',
                            data: { created: '' },
                            children: [],
                        },
                    ]

                    this.refresh()
                }
            })
        )
    }

    cancelRefreshTimer() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer)
            this.refreshTimer = null
        }
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
        this.cancelRefreshTimer()
    }

    _getRunForStage(stageName) {
        for (const run of this.flow.runs) {
            if (run.stage_name === stageName) {
                return run
            }
        }
        return null
    }

    _getParamFromStage(stageName, paramName) {
        for (const stage of this.flow.stages) {
            if (stage.name === stageName) {
                for (const param of stage.schema.parameters) {
                    if (param.name === paramName) {
                        return param
                    }
                }
            }
        }
        return null
    }

    _buildSubtree(node, allParents, children) {
        for (const c of children) {
            const subtree = {
                label: c.name,
                expanded: true,
                data: {
                    stage: c,
                    run: this._getRunForStage(c.name),
                    selected: false,
                },
            }
            if (allParents[c.name] !== undefined) {
                this._buildSubtree(subtree, allParents, allParents[c.name])
            }
            if (node.children === undefined) {
                node.children = []
            }
            node.children.push(subtree)
        }
    }

    _traverseTree(node, level) {
        if (node.data.run || node.data.stage) {
            let selected = false
            if (this.selectedNode.stage.id === null) {
                this.selectedNode = node.data
                selected = true
            }
            this.flatTree.push({
                level,
                run: node.data.run,
                stage: node.data.stage,
                selected,
            })
        }
        if (node.children) {
            for (const c of node.children) {
                this._traverseTree(c, level + 1)
            }
        }
    }

    prepareFlowDataStr() {
        const data = pick(this.flow, 'id', 'created', 'kind', 'trigger', 'seq', 'data')
        this.flowData = JSON.stringify(data, null, 4);
    }

    refresh() {
        if (this.refreshing) {
            return
        }
        this.refreshing = true

        this.subs.add(
            this.executionService.getFlow(this.flowId).subscribe((flow) => {
                this.refreshing = false
                this.refreshTimer = null

                this.projectId = flow.project_id
                this.flow = flow
                this.prepareFlowDataStr()
                const crumbs = [
                    {
                        label: 'Projects',
                        project_id: flow.project_id,
                        project_name: flow.project_name,
                    },
                    {
                        label: 'Branches',
                        branch_id: flow.branch_id,
                        branch_name: flow.base_branch_name,
                    },
                    {
                        label: 'Results',
                        branch_id: flow.branch_id,
                        flow_kind: flow.kind,
                    },
                    {
                        label: 'Flows',
                        flow_id: flow.id,
                        flow_label: flow.label,
                    },
                ]
                this.breadcrumbService.setCrumbs(crumbs)

                // collect args from flow
                const args = []
                let sectionArgs = []
                if (this.flow.kind === 'dev') {
                    sectionArgs.push({
                        name: 'BRANCH',
                        value: this.flow.branch_name,
                    })
                }
                args.push({
                    name: 'Common',
                    args: sectionArgs,
                })
                // collect args from runs
                for (const run of this.flow.runs) {
                    sectionArgs = []
                    if (!run.args) {
                        console.warn('run does not have args', run)
                        continue
                    }
                    for (const a of Object.keys(run.args)) {
                        const param = this._getParamFromStage(run.stage_name, a)
                        let description = ''
                        let defaultValue
                        if (param) {
                            description = param.description
                            defaultValue = param.default
                        }

                        sectionArgs.push({
                            name: a,
                            value: run.args[a],
                            description,
                            default: defaultValue,
                        })
                    }
                    if (sectionArgs.length > 0) {
                        args.push({
                            name: run.stage_name,
                            args: sectionArgs,
                        })
                    }
                }
                this.args = args

                // build tree of runs
                const allParents = {
                    root: [],
                }
                for (const stage of flow.stages) {
                    if (allParents[stage.schema.parent] === undefined) {
                        allParents[stage.schema.parent] = []
                    }
                    allParents[stage.schema.parent].push(stage)
                }

                this.runsTree = [
                    {
                        label: `Flow [${this.flowId}]`,
                        expanded: true,
                        type: 'root',
                        data: flow,
                    },
                ]
                this._buildSubtree(
                    this.runsTree[0],
                    allParents,
                    allParents.root
                )

                this.flatTree = []
                this._traverseTree(this.runsTree[0], 0)

                // put back selection
                if (this.selectedNode.stage.id) {
                    this.changeSelection(this.selectedNode.stage.id)
                }

                // refresh data every 10secs
                this.refreshTimer = setTimeout(() => {
                    this.refresh()
                }, 10000)
            })
        )
    }

    showNodeMenu($event, nodeMenu, node) {
        // console.info(node)

        if (node.data.run) {
            this.nodeMenuItems = [
                {
                    label: 'Show Details',
                    icon: 'pi pi-folder-open',
                    routerLink: '/runs/' + node.data.run.id + '/jobs',
                },
                {
                    label: 'Rerun',
                    icon: 'pi pi-replay',
                    disabled: !this.auth.hasPermission(
                        this.projectId,
                        'pwrusr'
                    ),
                    title: this.auth.permTip(this.projectId, 'pwrusr'),
                },
            ]
        } else {
            this.nodeMenuItems = [
                {
                    label: 'Run this stage',
                    icon: 'pi pi-caret-right',
                    command: () => {
                        const stage = node.data.stage
                        // console.info(stage.schema.parameters)
                        if (stage.schema.parameters.length === 0) {
                            this.subs.add(
                                this.executionService
                                    .createRun(this.flowId, stage.id)
                                    .subscribe(
                                        (data) => {
                                            this.msgSrv.add({
                                                severity: 'success',
                                                summary: 'Run succeeded',
                                                detail: 'Run operation succeeded.',
                                            })
                                            this.refresh()
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
                                '/flows/' + this.flowId + '/runs/new',
                            ])
                        }
                    },
                    disabled: !this.auth.hasPermission(
                        this.projectId,
                        'pwrusr'
                    ),
                    title: this.auth.permTip(this.projectId, 'pwrusr'),
                },
            ]
        }
        nodeMenu.toggle($event)
    }

    onStageRun(newRun) {
        // console.info(newRun)
        this.refresh()
    }

    humanFileSize(bytes) {
        return humanBytes(bytes, false)
    }

    loadArtifactsLazy(event) {
        // as this method is invoked in child component p-table
        // we need to check changes in parent ie this
        // that were made here to this.loadingArtifacts

        this.loadingArtifacts = true
        this.cd.detectChanges()

        this.subs.add(
            this.executionService
                .getFlowArtifacts(this.flowId, event.first, event.rows)
                .subscribe((data) => {
                    this.artifacts = data.items
                    this.totalArtifacts = data.total
                    this.loadingArtifacts = false

                    this.cd.detectChanges()
                })
        )
    }

    changeSelection(stageId) {
        for (const node of this.flatTree) {
            if (node.stage.id === stageId) {
                node.selected = true
                this.selectedNode = node
            } else {
                node.selected = false
            }
        }
    }

    hasFlowCommits() {
        if (
            this.flow &&
            this.flow.trigger &&
            (this.flow.trigger.commits || this.flow.trigger.pull_request)
        ) {
            return true
        }
        return false
    }

    hasFlowArtifacts() {
        if (
            this.flow &&
            this.flow.artifacts &&
            ((this.flow.artifacts['private'] &&
                this.flow.artifacts['private'].count > 0) ||
                (this.flow.artifacts['public'] &&
                    this.flow.artifacts['public'].count > 0))
        ) {
            return true
        }
        return false
    }

    hasFlowReports() {
        if (
            this.flow &&
            this.flow.report_entries &&
            this.flow.report_entries.length > 0
        ) {
            return true
        }
        return false
    }

    handleTabChange(tabName) {
        if (tabName === 'logs') {
            this.logsPanelVisible = true
        } else {
            this.logsPanelVisible = false
        }
    }

    handleRunTabChange(ev) {
        if (ev.index === 2) {
            this.runLogsPanelVisible = true
        } else {
            this.runLogsPanelVisible = false
        }
    }
}
