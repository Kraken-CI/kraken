import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'
import { FormGroup, FormControl } from '@angular/forms'

import { MessageService } from 'primeng/api'
import { ConfirmationService } from 'primeng/api'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { ManagementService } from '../backend/api/management.service'

@Component({
    selector: 'app-project-settings',
    templateUrl: './project-settings.component.html',
    styleUrls: ['./project-settings.component.sass'],
})
export class ProjectSettingsComponent implements OnInit {
    projectId = 0
    project: any = {
        name: '',
        branches: [],
        secrets: [],
        webhooks: { github_enabled: false },
    }

    // secret form
    secretMode = 0
    secretForm = new FormGroup({
        id: new FormControl(''),
        name: new FormControl(''),
        kind: new FormControl(''),
        username: new FormControl(''),
        key: new FormControl(''),
        secret: new FormControl(''),
    })

    selectedSecret: any

    constructor(
        private route: ActivatedRoute,
        private msgSrv: MessageService,
        private confirmationService: ConfirmationService,
        protected breadcrumbService: BreadcrumbsService,
        protected managementService: ManagementService
    ) {}

    ngOnInit() {
        this.route.paramMap.subscribe(params => {
            this.projectId = parseInt(params.get('id'))

            this.managementService
                .getProject(this.projectId)
                .subscribe(project => {
                    this.project = project

                    this.breadcrumbService.setCrumbs([
                        {
                            label: 'Projects',
                            project_id: this.projectId,
                            project_name: this.project.name,
                        },
                    ])

                    if (this.project.secrets.length === 0) {
                        this.secretMode = 1
                    } else {
                        this.selectSecret(this.project.secrets[0])
                    }
                })
        })
    }

    newSecret() {
        this.secretMode = 1
        this.secretForm.reset()
    }

    prepareSecret(secret) {
        const secretVal = {
            name: secret.name,
            kind: secret.kind,
        }
        if (secret.kind === 'simple') {
            secretVal.secret = secret.secret
        } else if (secret.kind === 'ssh-key') {
            secretVal.username = secret.username
            secretVal.key = secret.key
        }
        return secretVal
    }

    secretAdd() {
        const secretVal = this.prepareSecret(this.secretForm.value)
        this.managementService
            .createSecret(this.projectId, secretVal)
            .subscribe(
                data => {
                    console.info(data)
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'New secret succeeded',
                        detail: 'New secret operation succeeded.',
                    })
                    this.project.secrets.push(data)
                },
                err => {
                    console.info(err)
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'New secret erred',
                        detail: 'New secret operation erred: ' + msg,
                        life: 10000,
                    })
                }
            )
    }

    secretSave() {
        const secretVal = this.prepareSecret(this.secretForm.value)
        this.managementService
            .updateSecret(this.secretForm.value.id, secretVal)
            .subscribe(
                secret => {
                    for (const idx in this.project.secrets) {
                        if (this.project.secrets[idx].id == secret.id) {
                            this.project.secrets[idx] = secret
                            break
                        }
                    }
                    this.selectSecret(secret)
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Secret update succeeded',
                        detail: 'Secret update operation succeeded.',
                    })
                },
                err => {
                    console.info(err)
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Secret update erred',
                        detail: 'Secret update operation erred: ' + msg,
                        life: 10000,
                    })
                }
            )
    }

    secretDelete() {
        const secretVal = this.secretForm.value
        this.confirmationService.confirm({
            message:
                'Do you really want to delete secret "' + secretVal.name + '"?',
            accept: () => {
                this.managementService.deleteSecret(secretVal.id).subscribe(
                    secret => {
                        this.selectSecret(this.project.secrets[0]) // TODO: what if this is deleted, same in list of stages
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Secret deletion succeeded',
                            detail: 'Secret deletion operation succeeded.',
                        })
                    },
                    err => {
                        console.info(err)
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Secret deletion erred',
                            detail: 'Secret deletion operation erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
            },
        })
    }

    selectSecret(secret) {
        if (this.selectedSecret) {
            this.selectedSecret.selectedClass = ''
        }
        this.selectedSecret = secret
        this.selectedSecret.selectedClass = 'selectedClass'

        const secretVal = this.prepareSecret(secret)
        secretVal.id = secret.id
        if (secretVal.secret === undefined) {
            secretVal.secret = ''
        }
        if (secretVal.username === undefined) {
            secretVal.username = ''
        }
        if (secretVal.key === undefined) {
            secretVal.key = ''
        }
        this.secretForm.setValue(secretVal)

        this.secretMode = 2
    }

    getBaseUrl() {
        return window.location.origin
    }

    getOrGenerateSecret() {
        if (!this.project.webhooks.github_secret) {
            this.project.webhooks.github_secret = [...Array(20)]
                .map(i => (~~(Math.random() * 36)).toString(36))
                .join('')
        }
        return this.project.webhooks.github_secret
    }

    saveWebhooks() {
        const projectVal = { webhooks: this.project.webhooks }
        this.managementService
            .updateProject(this.projectId, projectVal)
            .subscribe(
                project => {
                    this.project = project
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Project update succeeded',
                        detail: 'Project update operation succeeded.',
                    })
                },
                err => {
                    console.info(err)
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'Project update erred',
                        detail: 'Project update operation erred: ' + msg,
                        life: 10000,
                    })
                }
            )
    }
}
