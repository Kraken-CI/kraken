import { Component, OnInit } from '@angular/core'

import { PanelMenuModule } from 'primeng/panelmenu'
import { MenuModule } from 'primeng/menu'
import { MenuItem } from 'primeng/api'
import { SplitButtonModule } from 'primeng/splitbutton'
import { MultiSelectModule } from 'primeng/multiselect'
import { ToastModule } from 'primeng/toast'
import { MessageService } from 'primeng/api'

import { environment } from './../environments/environment'

import { AuthService } from './auth.service'
import { UsersService } from './backend/api/users.service'

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.sass'],
})
export class AppComponent implements OnInit {
    title = 'Kraken'
    logoClass = 'logo1'
    krakenVersion = '0.4'

    topMenuItems: MenuItem[]
    logoutMenuItems: MenuItem[]

    session: any

    displayPasswdBox = false
    username: string
    password: string

    passwordOld: string
    passwordNew1: string
    passwordNew2: string

    constructor(private auth: AuthService,
                private api: UsersService,
                private msgSrv: MessageService) {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 9) + 1)
        this.session = null
    }

    ngOnInit() {
        this.auth.currentSession.subscribe(
            session => {
                this.session = session
            }
        )

        this.krakenVersion = environment.krakenVersion

        this.topMenuItems = [
            {
                label: 'Agents',
                icon: 'fa fa-server',
                items: [
                    {
                        label: 'Agents',
                        routerLink: '/agents',
                    },
                    {
                        label: 'Groups',
                        routerLink: '/agents-groups',
                    },
                    {
                        label: 'Discovered',
                        routerLink: '/discovered-agents',
                    },
                    {
                        label: 'Download',
                        url: '/install/kraken-agent-install.sh',
                    },
                ],
            },
            {
                label: 'Diagnostics',
                icon: 'fa fa-thermometer-three-quarters',
                routerLink: '/diagnostics',
            },
            {
                label: 'Settings',
                icon: 'fa fa-wrench',
                routerLink: '/settings',
                disabled: !this.auth.hasPermission('manage'),
                title: this.auth.permTip('manage'),
            },
        ]

        this.logoutMenuItems = [{
            label: 'Change Password',
            icon: 'pi pi-key',
            command: () => {
                this.displayPasswdBox = true
                console.info('this.displayPasswdBox', this.displayPasswdBox)
            },
            disabled: !this.auth.hasPermission('manage'),
            title: this.auth.permTip('manage'),
        }]
    }

    randomLogoFont() {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 3) + 1)
    }

    login() {
        this.auth.login(this.username, this.password, 'returnUrl')
    }

    passwdKeyUp(evKey) {
        if (evKey === 'Enter') {
            this.login()
        }
    }

    logout() {
        this.auth.logout()
    }

    isDemo() {
        return window.location.hostname === "lab.kraken.ci"
    }

    isLocal() {
        return window.location.hostname === "localhost"
    }

    changePassword() {
        if (this.passwordNew1 !== this.passwordNew2) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Changing password erred',
                detail: 'New passwords are not the same',
                life: 10000,
            })
            return
        }
        if (!this.passwordNew1) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Changing password erred',
                detail: 'New password cannot be empty',
                life: 10000,
            })
            return
        }

        const passwds = {
            password_old: this.passwordOld,
            password_new: this.passwordNew1,
        }
        this.api.changePassword(this.auth.session.user.id, passwds).subscribe(
            data => {
                this.msgSrv.add({
                    severity: 'success',
                    summary: 'Password changed',
                    detail: 'Changing password succeeded.',
                })
                this.displayPasswdBox = false
                this.passwordOld = ''
                this.passwordNew1 = ''
                this.passwordNew2 = ''
            },
            err => {
                let msg = err.statusText
                if (err.error && err.error.detail) {
                    msg = err.error.detail
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Changing password erred',
                    detail: 'Changing password erred: ' + msg,
                    life: 10000,
                })
            }
        )
    }

    passwdChangeKeyUp(evKey) {
        if (evKey === 'Enter') {
            this.changePassword()
        }
    }
}
