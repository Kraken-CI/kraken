import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'
import { Title } from '@angular/platform-browser'

import { PanelModule } from 'primeng/panel'
import { TreeModule } from 'primeng/tree'
import { TreeNode } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { ExecutionService } from '../backend/api/execution.service'
import { ManagementService } from '../backend/api/management.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { datetimeToLocal } from '../utils'

@Component({
    selector: 'app-main-page',
    templateUrl: './main-page.component.html',
    styleUrls: ['./main-page.component.sass'],
})
export class MainPageComponent implements OnInit {
    newProjectDlgVisible = false
    projectName = ''

    projects: any[]

    selectedProject = { name: '', id: 0 }
    newBranchDlgVisible = false
    branchName = ''

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        protected executionService: ExecutionService,
        protected managementService: ManagementService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
        private titleService: Title
    ) {}

    ngOnInit() {
        this.titleService.setTitle('Kraken - Main')
        this.breadcrumbService.setCrumbs([
            {
                label: 'Home',
            },
        ])

        this.refresh()
    }

    refresh() {
        this.managementService.getProjects().subscribe(data => {
            this.projects = data.items
        })
    }

    newProject() {
        this.newProjectDlgVisible = true
    }

    cancelNewProject() {
        this.newProjectDlgVisible = false
    }

    newProjectKeyDown(event) {
        if (event.key === 'Enter') {
            this.addNewProject()
        }
    }

    addNewProject() {
        this.managementService
            .createProject({ name: this.projectName })
            .subscribe(
                data => {
                    console.info(data)
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'New project succeeded',
                        detail: 'New project operation succeeded.',
                    })
                    this.newProjectDlgVisible = false
                    this.selectedProject = data
                    this.router.navigate(['/projects/' + data.id])
                },
                err => {
                    console.info(err)
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'New project erred',
                        detail: 'New project operation erred: ' + msg,
                        life: 10000,
                    })
                    this.newProjectDlgVisible = false
                }
            )
    }

    newBranch(project) {
        this.newBranchDlgVisible = true
        this.selectedProject = project
    }

    cancelNewBranch() {
        this.newBranchDlgVisible = false
    }

    newBranchKeyDown(event) {
        if (event.key === 'Enter') {
            this.addNewBranch()
        }
    }

    addNewBranch() {
        this.managementService
            .createBranch(this.selectedProject.id, { name: this.branchName })
            .subscribe(
                data => {
                    console.info(data)
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'New branch succeeded',
                        detail: 'New branch operation succeeded.',
                    })
                    this.newBranchDlgVisible = false
                    this.router.navigate(['/branches/' + data.id])
                },
                err => {
                    console.info(err)
                    let msg = err.statusText
                    if (err.error && err.error.detail) {
                        msg = err.error.detail
                    }
                    this.msgSrv.add({
                        severity: 'error',
                        summary: 'New branch erred',
                        detail: 'New branch operation erred: ' + msg,
                        life: 10000,
                    })
                    this.newBranchDlgVisible = false
                }
            )
    }
}
