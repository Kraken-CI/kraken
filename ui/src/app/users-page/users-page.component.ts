import { Component, OnInit, OnDestroy } from '@angular/core';
import { Title } from '@angular/platform-browser'

import { MessageService } from 'primeng/api'

import { Subscription } from 'rxjs'

import { ManagementService } from '../backend/api/management.service'
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
    superadmin = false

    addUserDlgVisible = false
    username = ''
    password = ''

    displayPasswdBox = false

    roles: any[];
    projects: any[] = []
    projectsById = {}
    selectedProject: any
    selectedRole: any

    constructor(
        protected managementService: ManagementService,
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

        this.subs.add(
            this.managementService.getProjects().subscribe((data) => {
                this.projects = data.items
                for (let p of this.projects) {
                    this.projectsById[p.id] = p
                }
            })
        )
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
                .subscribe(
                    (data) => {
                        this.users = data.items
                        this.totalUsers = data.total
                        this.loadingUsers = false

                        if (!this.selectedUser) {
                            this.selectedUser = this.users[0]
                            this.loadUserDetails(this.selectedUser)
                        }
                    },
                    (err) => {
                        this.loadingUsers = false
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Getting users erred',
                            detail: 'Getting  users erred: ' + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    reflecUserChangesLocally(user, data) {
        for (var k in data) {
            user[k] = data[k]
        }

        let userProjectsById = {}
        user.userProjects = []
        for (const [projId, role] of Object.entries(user.projects)) {
            let p = this.projectsById[projId]
            if (!p) {
                return
            }
            userProjectsById[projId] = p
            user.userProjects.push({
                id: projId,
                name: p.name,
                role: role
            })
        }
        user.userProjects.sort((a, b) => a.name.localeCompare(b.name))

        user.nonUserProjects = []
        for (let p of this.projects) {
            if (!(p.id in userProjectsById)) {
                user.nonUserProjects.push(p)
            }
        }
    }

    loadUserDetails(user) {
        this.subs.add(
            this.usersService
                .getUser(user.id)
                .subscribe((data) => {
                    this.selectedProject = null
                    this.reflecUserChangesLocally(user, data)
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

    changeUserDetails(details, okSummary, okDetails, errSummary, errDetails) {
        this.subs.add(
            this.usersService
                .changeUserDetails(this.selectedUser.id, details)
                .subscribe(
                    (data) => {
                        this.reflecUserChangesLocally(this.selectedUser, data)

                        this.msgSrv.add({
                            severity: 'success',
                            summary: okSummary,
                            detail: okDetails,
                        })
                    },
                    (err) => {
                        let msg = err.statusText
                        if (err.error && err.error.detail) {
                            msg = err.error.detail
                        }
                        this.msgSrv.add({
                            severity: 'error',
                            summary: errSummary,
                            detail: errDetails + msg,
                            life: 10000,
                        })
                    }
                )
        )
    }

    enableUser() {
        let details = {enabled: true}
        this.changeUserDetails(details,
                               'User enabled', 'Enabling user succeeded.',
                               'Enabling user erred', 'Enabling user erred: ')
    }

    disableUser() {
        let details = {enabled: false}
        this.changeUserDetails(details,
                               'User disabled', 'Disabling user succeeded.',
                               'Disabling user erred','Disabling user erred: ')
    }

    superadminChange() {
        let user = {superadmin: this.selectedUser.superadmin}
        this.changeUserDetails(user,
                               'Super admin role changed', 'Changing super admin role succeeded.',
                               'Changing super admin role erred','Changing super admin role erred: ')
    }

    addUserToProject(project, role) {
        let projs = {}
        projs[project.id] = role.value
        let details = {projects: projs}

        this.changeUserDetails(details,
                               'User added to project', `User added to project ${project.name} as ${role.name}.`,
                               'Adding user from project erred','Adding user from project erred: ')
    }

    changeUserRoleInProject(project) {
        let projs = {}
        projs[project.id] = project.role
        let details = {projects: projs}

        this.changeUserDetails(details,
                               'User role changed', `User role changed in project ${project.name} to ${project.role}.`,
                               'Changing user role erred','Changing user role erred: ')
    }

    removeUserFromProject(project) {
        let projs = {}
        projs[project.id] = null
        let details = {projects: projs}

        this.changeUserDetails(details,
                               'User removed from project', `User removed from project ${project.name}.`,
                               'Removing user from project erred','Removing user from project erred: ')
    }
}
