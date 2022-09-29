import { Component, OnInit, OnDestroy } from '@angular/core';
import { Title } from '@angular/platform-browser'

import { MessageService } from 'primeng/api'

import { Subscription } from 'rxjs'

import { UsersService } from '../backend/api/users.service'
import { BreadcrumbsService } from '../breadcrumbs.service'

@Component({
  selector: 'app-users-page',
  templateUrl: './users-page.component.html',
  styleUrls: ['./users-page.component.sass']
})
export class UsersPageComponent implements OnInit, OnDestroy {
    private subs: Subscription = new Subscription()

    users: any[] = []
    totalUsers = 0
    loadingUsers = false
    selectedUser: any

    addUserDlgVisible = false
    username = ''
    password = ''

    displayPasswdBox = false

    roles: any[];
    projects: any[] = []
    selectedProject: any
    selectedRole: any

    constructor(
        protected usersService: UsersService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
        private titleService: Title
    ) {
        this.roles = [
            {name: 'Viewer', value: 'viewer'},
            {name: 'Power User', value: 'pwrusr'},
            {name: 'Admin', value: 'admin'},
        ];

    }

    ngOnInit(): void {
        this.titleService.setTitle('Kraken - Users')
        const crumbs = [
            {
                label: 'Home',
            },
            {
                label: 'Users',
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    loadUsersLazy(event) {
        this.loadingUsers = true

        let sortField = 'name'
        if (event.sortField) {
            sortField = event.sortField
        }
        let sortDir = 'asc'
        if (event.sortOrder === -1) {
            sortDir = 'desc'
        }

        this.subs.add(
            this.usersService
                .getUsers(event.first, event.rows, sortField, sortDir)
                .subscribe((data) => {
                    this.users = data.items
                    this.totalUsers = data.total
                    this.loadingUsers = false

                    if (!this.selectedUser) {
                        this.selectedUser = this.users[0]
                        this.loadUserDetails(this.selectedUser)
                    }
                })
        )
    }

    loadUserDetails(user) {
        this.subs.add(
            this.usersService
                .getUser(user.id)
                .subscribe((data) => {
                    user.projects = [
                        {id: 1, name: 'Proj1', role: 'viewer'},
                        {id: 2, name: 'Proj2', role: 'admin'},
                        {id: 3, name: 'Proj3', role: 'pwrusr'},
                    ]
                    //this.toolVersions = data.items

                    this.selectedProject = null
                })
        )
    }

    showAddUserDialog() {
        this.addUserDlgVisible = true
    }

    cancelAddUser() {
        this.addUserDlgVisible = false
    }

    addUser() {
        let user = {name: this.username, password: this.password}

        this.subs.add(
            this.usersService
                .createUser(user)
                .subscribe(
                    (data) => {
                        this.users.unshift(data)
                        this.addUserDlgVisible = false

                        this.username = ''
                        this.password = ''

                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'User added',
                            detail: 'Adding user succeeded.',
                        })
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Adding user erred',
                            detail: 'Adding user erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    addUserKeyDown(event) {
        if (event.key === 'Enter') {
            this.addUser()
        }
        if (event.key === 'Escape') {
            this.cancelAddUser()
        }
    }

    enableUser() {
        let user = {enabled: true}

        this.subs.add(
            this.usersService
                .changeUserDetails(this.selectedUser.id, user)
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'User enabled',
                            detail: 'Enabling user succeeded.',
                        })
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Enabling user erred',
                            detail: 'Enabling user erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    disableUser() {
        let user = {enabled: false}

        this.subs.add(
            this.usersService
                .changeUserDetails(this.selectedUser.id, user)
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'User disabled',
                            detail: 'Disabling user succeeded.',
                        })
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Disabling user erred',
                            detail: 'Disabling user erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    addUserFromProject(user, project) {
    }

    removeUserFromProject(user, proj) {
    }
}
