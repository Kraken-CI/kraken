import {
    Component,
    OnInit,
    OnDestroy,
    ViewChild,
    ChangeDetectorRef,
} from '@angular/core'
import { Router, ActivatedRoute } from '@angular/router'
import { FormGroup, FormControl } from '@angular/forms'
import { Title } from '@angular/platform-browser'

import { Subscription } from 'rxjs'

import { MessageService } from 'primeng/api'
import { ConfirmationService } from 'primeng/api'

import { AuthService } from '../auth.service'
import { ManagementService } from '../backend/api/management.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { Branch } from '../backend/model/models'

@Component({
    selector: 'app-branch-mgmt',
    templateUrl: './branch-mgmt.component.html',
    styleUrls: ['./branch-mgmt.component.sass'],
})
export class BranchMgmtComponent implements OnInit, OnDestroy {
    branchId: number
    branch: Branch = {
        id: 0,
        name: 'noname',
        branch_name: 'noname',
        stages: [],
    }

    newBranchDisplayName: string
    newBranchRepoName: string
    branchNameDlgVisible = false

    forkBranchDisplayName: string
    forkBranchRepoName: string
    forkBranchDlgVisible = false
    forkingModel = 'model-1'

    newStageDlgVisible = false
    stageName = ''
    newStageName: string
    newStageDescr: string

    moveBranchDlgVisible = false
    projects = []
    targetProject: any = null

    stage: any = { id: 0, name: '', description: '', schedules: [] }
    saveErrorMsg = ''

    codeMirrorOpts = {
        lineNumbers: true,
        theme: 'material',
        mode: 'text/x-python',
        indentUnit: 4,
        gutters: ['CodeMirror-lint-markers'],
        lint: true,
    }

    codeMirrorJsonOpts = {
        lineNumbers: true,
        theme: 'material',
        mode: 'application/json',
    }

    @ViewChild('cmEditor') cmEditor

    prepareStepDlgVisible = false
    wfSchema: any
    stepTools: any[] = []
    stepTool: any
    stepFields: any[] = []
    generatedStep = ''

    schemaCheckDisplay = false
    schemaCheckContent: any

    schemaFromRepoForm = new FormGroup({
        repo_url: new FormControl(''),
        repo_branch: new FormControl(''),
        repo_access_token: new FormControl(''),
        schema_file: new FormControl(''),
        repo_refresh_interval: new FormControl(''),
        git_clone_params: new FormControl(''),
    })

    sequences = []

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        public auth: AuthService,
        protected managementService: ManagementService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
        private confirmationService: ConfirmationService,
        private titleService: Title,
        private changeDetectorRef: ChangeDetectorRef
    ) {}

    ngOnInit() {
        this.schemaCheckContent = { schema: '', error: '' }
        this.subs.add(
            this.route.paramMap.subscribe((params) => {
                this.branchId = parseInt(params.get('id'), 10)
                this.refresh()
            })
        )

        this.subs.add(
            this.managementService.getWorkflowSchema().subscribe((wfSchema) => {
                this.wfSchema = wfSchema
                // console.info('wfSchema', wfSchema)
                // console.info('wfSchema', wfSchema['properties']['jobs']['items']['properties']['steps']['items']['oneOf'])
                for (const t of wfSchema['properties']['jobs']['items'][
                    'properties'
                ]['steps']['items']['oneOf']) {
                    const tt = t['then']['properties']['tool']
                    this.stepTools.push({
                        name: tt['const'],
                        descr: tt['description'],
                        schema: t['then']['properties'],
                    })
                }
                this.stepTool = this.stepTools[0]
                this.stepTools.sort((a, b) => a.name.localeCompare(b.name))

                this.generateStep()
            })
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    refresh() {
        this.subs.add(
            this.managementService
                .getBranch(this.branchId)
                .subscribe((branch) => {
                    this.titleService.setTitle(
                        'Kraken - Branch Management - ' + branch.name
                    )
                    this.branch = branch
                    this.stage = null // reset selected stage
                    if (this.stageName !== '') {
                        // this is a finish of adding new stage ie. select newly created stage
                        for (const s of this.branch.stages) {
                            if (s.name === this.stageName) {
                                this.selectStage(s)
                                this.stageName = ''
                                break
                            }
                        }
                    }
                    if (
                        this.stage === null &&
                        branch.stages &&
                        branch.stages.length > 0
                    ) {
                        this.selectStage(branch.stages[0])
                    }

                    const crumbs = [
                        {
                            label: 'Projects',
                            project_id: branch.project_id,
                            project_name: branch.project_name,
                        },
                        {
                            label: 'Branches',
                            branch_id: branch.id,
                            branch_name: branch.name,
                        },
                    ]
                    this.breadcrumbService.setCrumbs(crumbs)
                })
        )

        this.subs.add(
            this.managementService
                .getBranchSequences(this.branchId)
                .subscribe((data) => {
                    this.sequences = data.items
                })
        )
    }

    selectStage(stage) {
        if (this.stage) {
            this.stage.selectedClass = ''
        }
        this.stage = stage
        this.stage.selectedClass = 'selectedClass'

        const val = {
            repo_url: stage.repo_url,
            repo_branch: stage.repo_branch,
            repo_access_token: stage.repo_access_token,
            schema_file: stage.schema_file,
            repo_refresh_interval: stage.repo_refresh_interval,
            git_clone_params: stage.git_clone_params,
        }
        this.schemaFromRepoForm.setValue(val)

        if (stage.repo_error) {
            this.saveErrorMsg =
                'loading schema erred:<br>' +
                stage.repo_error.replaceAll('\n', '<br>')
        }
    }

    newStage() {
        this.newStageDlgVisible = true
    }

    cancelNewStage() {
        this.newStageDlgVisible = false
    }

    newStageKeyDown(event) {
        if (event.key === 'Enter') {
            this.addNewStage()
        }
    }

    addNewStage() {
        this.subs.add(
            this.managementService
                .createStage(this.branchId, { name: this.stageName })
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'New stage succeeded',
                            detail: 'New stage operation succeeded.',
                        })
                        this.newStageDlgVisible = false
                        this.refresh()
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'New stage erred',
                            detail: 'New stage operation erred: ' + msg,
                            life: 10000,
                        })
                        this.newStageDlgVisible = false
                    }
                )
        )
    }

    saveStage() {
        this.saveErrorMsg = ''

        let stage = {
            name: this.stage.name,
            schema_code: this.stage.schema_code,
            enabled: this.stage.enabled,
            schema_from_repo_enabled: this.stage.schema_from_repo_enabled,
        }
        stage = Object.assign(stage, this.schemaFromRepoForm.value)
        this.doSaveStage(stage)
    }

    checkStageSchema() {
        this.subs.add(
            this.managementService
                .getStageSchemaAsJson(this.stage.id, {
                    schema_code: this.stage.schema_code,
                })
                .subscribe(
                    (data) => {
                        this.schemaCheckContent = data
                        this.schemaCheckDisplay = true
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Check schema erred',
                            detail: 'Check schema operation erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    deleteStage() {
        this.confirmationService.confirm({
            message:
                'Do you really want to delete stage "' + this.stage.name + '"?',
            accept: () => {
                this.subs.add(
                    this.managementService.deleteStage(this.stage.id).subscribe(
                        (stage) => {
                            this.selectStage(this.branch.stages[0])
                            this.msgSrv.add({
                                severity: 'success',
                                summary: 'Stage deletion succeeded',
                                detail: 'Stage deletion operation succeeded.',
                            })
                            this.refresh()
                        },
                        (err) => {
                            let msg = err.statusText
                            if (err.error && err.error.detail) {
                                msg = err.error.detail
                            }
                            this.msgSrv.add({
                                severity: 'error',
                                summary: 'Stage deletion erred',
                                detail:
                                    'Stage deletion operation erred: ' + msg,
                                life: 10000,
                            })
                        }
                    )
                )
            },
        })
    }

    branchNameKeyDown(event) {
        if (event.key === 'Enter') {
            this.saveBranchName()
        }
        if (event.key === 'Escape') {
            this.cancelBranchNameChange()
        }
    }

    displayBranchNameEdit() {
        this.newBranchDisplayName = this.branch.name
        this.newBranchRepoName = this.branch.branch_name
        this.branchNameDlgVisible = true
    }

    cancelBranchNameChange() {
        this.branchNameDlgVisible = false
    }

    saveBranchName() {
        this.doSaveBranch(this.branch.id, {
            name: this.newBranchDisplayName,
            branch_name: this.newBranchRepoName,
        })
        this.branchNameDlgVisible = false
    }

    doSaveBranch(branchId, branchData) {
        this.subs.add(
            this.managementService.updateBranch(branchId, branchData).subscribe(
                (branch) => {
                    this.branch = branch
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Branch update succeeded',
                        detail: 'Branch update operation succeeded.',
                    })
                },
                (err) => {
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Branch update erred',
                        detail: 'Branch update operation erred: ' + msg,
                        life: 10000,
                    })
                }
            )
        )
    }

    doSaveStage(stageData) {
        this.subs.add(
            this.managementService
                .updateStage(this.stage.id, stageData)
                .subscribe(
                    (stage) => {
                        this.selectStage(stage)
                        for (const idx in this.branch.stages) {
                            if (this.branch.stages[idx].id === stage.id) {
                                this.branch.stages[idx] = stage
                                break
                            }
                        }
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Stage update succeeded',
                            detail: 'Stage update operation succeeded.',
                        })

                        // if repo schema is being refreshed then refresh stage again in 10s
                        if (stage.repo_state === 1) {
                            setTimeout(() => {
                                this.refreshStage(stage.id)
                            }, 10000)
                        }
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Stage update erred',
                            detail: 'Stage update operation erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    refreshStage(stageId) {
        this.subs.add(
            this.managementService.getStage(stageId).subscribe((stage) => {
                // update stage data in ui
                for (const idx in this.branch.stages) {
                    if (this.branch.stages[idx].id === stage.id) {
                        this.branch.stages[idx] = stage
                        if (this.stage.id === stage.id) {
                            this.selectStage(stage)
                        }
                        break
                    }
                }

                // if repo schema is still being refreshed then refresh stage again in 10s
                if (stage.repo_state === 1) {
                    setTimeout(() => {
                        this.refreshStage(stage.id)
                    }, 10000)
                }
            })
        )
    }

    stageNameInplaceActivated() {
        this.newStageName = this.stage.name
    }

    stageNameKeyDown(event, stageNameInplace) {
        if (event.key === 'Enter') {
            stageNameInplace.deactivate()
            const stage = {
                name: this.newStageName,
            }
            this.doSaveStage(stage)
        }
        if (event.key === 'Escape') {
            stageNameInplace.deactivate()
        }
    }

    stageDescrInplaceActivated() {
        this.newStageDescr = this.stage.description
    }

    stageDescrKeyDown(event, stageDescrInplace) {
        if (event.key === 'Enter') {
            stageDescrInplace.deactivate()
            const stage = {
                name: this.stage.name,
                description: this.newStageDescr,
            }
            this.doSaveStage(stage)
        }
        if (event.key === 'Escape') {
            stageDescrInplace.deactivate()
        }
    }

    showForkBranchDialog() {
        this.forkBranchDlgVisible = true
    }

    cancelForkBranch() {
        this.forkBranchDlgVisible = false
    }

    forkBranchKeyDown(event) {
        if (event.key === 'Enter') {
            this.forkBranch()
        }
        if (event.key === 'Escape') {
            this.cancelForkBranch()
        }
    }

    forkBranch() {
        this.subs.add(
            this.managementService
                .createBranch(this.branch.project_id, {
                    id: this.branchId,
                    name: this.forkBranchDisplayName,
                    branch_name: this.forkBranchRepoName,
                    forking_model: this.forkingModel,
                })
                .subscribe(
                    (branch) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Fork branch succeeded',
                            detail: 'Fork branch operation succeeded.',
                        })
                        this.forkBranchDlgVisible = false
                        this.router.navigate(['/branches/' + branch.id])
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Fork branch erred',
                            detail: 'Fork branch operation erred: ' + msg,
                            life: 10000,
                        })
                        this.forkBranchDlgVisible = false
                    }
                )
        )
    }

    getSeqTypeName(seq) {
        switch (seq.kind) {
            case 0:
                return 'flow'
            case 1:
                return 'CI flow'
            case 2:
                return 'DEV flow'
            case 3:
                return 'run'
            case 4:
                return 'CI run'
            case 5:
                return 'DEV run'
        }
        return 'unknown'
    }

    deleteBranch() {
        this.subs.add(
            this.managementService.deleteBranch(this.branchId).subscribe(
                (data) => {
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Branch deletion succeeded',
                        detail: 'Branch delete operation succeeded.',
                    })
                    this.router.navigate([
                        '/projects/' + this.branch.project_id,
                    ])
                },
                (err) => {
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Branch deletion erred',
                        detail: 'Branch delete operation erred: ' + msg,
                        life: 10000,
                    })
                }
            )
        )
    }

    showMoveBranchDialog() {
        this.moveBranchDlgVisible = true
        this.subs.add(
            this.managementService.getProjects().subscribe((data) => {
                this.projects = data.items
            })
        )
    }

    cancelMoveBranch() {
        this.moveBranchDlgVisible = false
    }

    moveBranch() {
        if (!this.targetProject) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Move branch',
                detail: 'Destination project not selected',
                life: 10000,
            })
        }
        this.subs.add(
            this.managementService
                .moveBranch(this.branchId, {
                    project_id: this.targetProject.id,
                })
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Branch move succeeded',
                            detail: 'Branch move operation succeeded.',
                        })
                        window.location.reload()
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Branch move erred',
                            detail: 'Branch move operation erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    handleTabChange(ev) {
        if (ev.index === 2) {
            this.subs.add(
                this.managementService
                    .getStageSchedule(this.stage.id)
                    .subscribe((data) => {
                        this.stage.schedules = data.schedules
                    })
            )
        }
    }

    getBadgeUrl(what) {
        const url = window.location.origin + '/branch-badge/' + this.branchId
        if (what === 'tests') {
            return url + '/tests'
        } else if (what === 'issues') {
            return url + '/issues'
        }
        return url
    }

    copyBadgeUrl(badgeUrlEl) {
        badgeUrlEl.select()
        document.execCommand('copy')
        badgeUrlEl.setSelectionRange(0, 0)
    }

    showPrepareStepDialog() {
        this.prepareStepDlgVisible = true
    }

    generateStep() {
        this.stepFields = []
        for (const [fn, fv] of Object.entries(this.stepTool.schema)) {
            // prepare step help table
            const fld = {
                name: fn,
                type: fv['type'],
                descr: fv['description'],
                default: fv['default'],
                value: fv['default'] !== undefined ? fv['default'] : '',
            }
            if (fv['type'] === 'array') {
                if (fv['items']['type'] === 'object') {
                    fld['type'] += ' of objects'
                } else {
                    fld['type'] += ' of ' + fv['items']['type'] + 's'
                }
            }
            if (fn === 'tool') {
                fld['type'] = 'string'
                fld['value'] = fv['const']
            }
            this.stepFields.push(fld)
        }
        this.generateStep2()
    }

    generateStep2() {
        // prepare generated step example
        const json = {}
        for (const fv of this.stepFields) {
            const fn = fv.name
            if (fv['type'] === 'string') {
                if (fv['default'] !== undefined && fv['default'] === fv.value) {
                    // nothing
                } else if (fv['enum']) {
                    json[fn] = fv['enum'][0]
                } else {
                    json[fn] = fv.value
                }
            } else if (fv['type'] === 'integer') {
                if (fv['default'] !== undefined && fv['default'] === fv.value) {
                    // nothing
                } else if (fv['minimum']) {
                    json[fn] = fv['minimum']
                } else {
                    json[fn] = fv.value
                }
            } else if (fv['type'] === 'boolean') {
                if (fv['default'] !== undefined && fv['default'] === fv.value) {
                    // nothing
                } else {
                    json[fn] = false
                }
            } else if (fv['type'].startsWith('array')) {
                json[fn] = []
            } else if (fv['type'] === 'object') {
                json[fn] = {}
            }

            if (fn === 'tool') {
                json['tool'] = fv['value']
                continue
            }
        }
        this.generatedStep = JSON.stringify(json, null, 4)
    }

    copyGeneratedStep() {
        //this.changeDetectorRef.detectChanges();
        //const doc = this.cmEditor.getDoc()
        //const cursor = doc.getCursor()
        //console.info('cursor', cursor)
        //doc.replaceRange(text, cursor);

        const selBox = document.createElement('textarea')
        selBox.style.position = 'fixed'
        selBox.style.left = '0'
        selBox.style.top = '0'
        selBox.style.opacity = '0'
        selBox.value = this.generatedStep
        document.body.appendChild(selBox)
        selBox.focus()
        selBox.select()
        document.execCommand('copy')
        document.body.removeChild(selBox)

        this.prepareStepDlgVisible = false
    }
}
