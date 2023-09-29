import { Component, OnInit, OnDestroy, ViewChild } from '@angular/core'

import { Subscription } from 'rxjs'

import { Menubar } from 'primeng/menubar'
import { MenuItem } from 'primeng/api'
import { MessageService } from 'primeng/api'

import { environment } from './../environments/environment'

import { AuthService } from './auth.service'
import { ManagementService } from './backend/api/management.service'
import { SettingsService } from './services/settings.service'

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.sass'],
})
export class AppComponent implements OnInit, OnDestroy {
    title = 'Kraken'
    krakenVersion = '0.0'

    @ViewChild('topmenubar') topmenubar: Menubar
    topMenuItems: MenuItem[]
    logoutMenuItems: MenuItem[]

    session: any
    settings: any
    initSettings = {
        idp: {
            google_enabled: false,
        },
    }

    username: string
    password: string

    displayPasswdBox = false

    errorsInLogsCount = 0
    authorizedAgents = 0
    nonAuthorizedAgents = 0

    darkMode = false

    private subs: Subscription = new Subscription()

    constructor(
        protected auth: AuthService,
        private settingsService: SettingsService,
        protected managementService: ManagementService,
        private msgSrv: MessageService
    ) {
        this.session = null
        this.settings = this.initSettings
    }

    initDarkMode() {
        let darkMode = localStorage.getItem('kk-dark-mode') == 'on'
        let sysPref = false
        if (!darkMode) {
            darkMode = window.matchMedia('(prefers-color-scheme: dark)').matches
            sysPref = true
        }
        this.setDarkMode(darkMode, sysPref)

        window
            .matchMedia('(prefers-color-scheme: dark)')
            .addEventListener('change', this.darkModeListener.bind(this))
    }

    darkModeListener(ev) {
        this.setDarkMode(ev.matches, true)
    }

    setDarkMode(darkMode, sysPref) {
        this.darkMode = darkMode
        let cssFileName = ''
        if (darkMode) {
            document.documentElement.setAttribute('data-theme', 'dark')
            this.logoutMenuItems[1].icon = 'pi pi-moon'
            cssFileName = 'vela-blue.css'
            if (!sysPref) {
                localStorage.setItem('kk-dark-mode', 'on')
            }
        } else {
            document.documentElement.setAttribute('data-theme', 'light')
            this.logoutMenuItems[1].icon = 'pi pi-sun'
            cssFileName = 'saga-blue.css'
            if (!sysPref) {
                localStorage.setItem('kk-dark-mode', 'off')
            }
        }

        let themeLink = document.getElementById('app-theme') as HTMLLinkElement
        if (themeLink) {
            themeLink.href = cssFileName
        }
    }

    ngOnInit() {
        this.subs.add(
            this.auth.currentSession.subscribe((session) => {
                this.session = session
                if (this.session) {
                    this.lateInit()
                }
            })
        )

        this.subs.add(
            this.settingsService.settings.subscribe((settings) => {
                if (settings === null) {
                    this.settings = this.initSettings
                } else {
                    this.settings = settings
                }
            })
        )

        this.krakenVersion = environment.krakenVersion
    }

    lateInit() {
        this.topMenuItems = [
            {
                label: 'Agents',
                icon: 'fa fa-server',
                items: [
                    {
                        label: 'Agents',
                        icon: 'pi pi-user',
                        routerLink: '/agents',
                        badgeStyleClass: 'p-badge ml-3',
                        badge: '0',
                    },
                    {
                        label: 'Groups',
                        icon: 'pi pi-users',
                        routerLink: '/agents-groups',
                    },
                    {
                        label: 'Discovered',
                        icon: 'pi pi-user-plus',
                        badgeStyleClass: 'p-badge ml-3',
                        routerLink: '/discovered-agents',
                        badge: '0',
                    },
                    {
                        label: 'Download',
                        icon: 'pi pi-download',
                        items: [{
                            label: 'For Linux',
                            icon: 'fa-brands fa-linux',
                            command: (event) => {
                                this.downloadAgentInstallScript('sh')
                            },
                        }, {
                            label: 'For Windows',
                            icon: 'fa-brands fa-windows',
                            command: (event) => {
                                this.downloadAgentInstallScript('bat')
                            },
                        }]
                    },
                ],
            },
            {
                label: 'Diagnostics',
                icon: 'fa fa-thermometer-three-quarters',
                routerLink: '/diagnostics/overview',
            },
            {
                label: '0',
                icon: 'fa fa-smile-o',
                routerLink: '/diagnostics/logs',
                queryParams: { level: 'error' },
                title: '0 errors in the last hour',
                styleClass: '',
            },
            {
                label: 'Configuration',
                icon: 'fa fa-cog',
                items: [
                    {
                        label: 'Settings',
                        icon: 'fa fa-cogs',
                        routerLink: '/settings/general',
                        disabled: !this.auth.hasPermission(null, 'admin'),
                        title: this.auth.permTip(null, 'admin'),
                    },
                    {
                        label: 'Users',
                        icon: 'pi pi-user',
                        items: [
                            {
                                label: 'Users',
                                icon: 'pi pi-user',
                                routerLink: '/users',
                                disabled: !this.auth.hasPermission(
                                    null,
                                    'admin'
                                ),
                                title: this.auth.permTip(null, 'admin'),
                            },
                            {
                                label: 'Identity Providers',
                                icon: 'fa fa-users',
                                routerLink: '/settings/identity-providers',
                                disabled: !this.auth.hasPermission(
                                    null,
                                    'admin'
                                ),
                                title: this.auth.permTip(null, 'admin'),
                            },
                        ],
                    },
                    {
                        label: 'Tools',
                        icon: 'fa fa-wrench',
                        routerLink: '/tools',
                    },
                ],
            },
        ]

        this.logoutMenuItems = [
            {
                label: 'Change Password',
                icon: 'pi pi-key',
                command: () => {
                    this.displayPasswdBox = true
                },
            },
            {
                label: 'Dark Mode',
                icon: 'pi pi-sun',
                command: () => {
                    this.setDarkMode(!this.darkMode, false)
                },
            },
        ]

        this.pullLiveData()

        this.initDarkMode()
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    login() {
        if (!this.username) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Login erred',
                detail: 'Username cannot be empty',
                life: 10000,
            })
            return
        }
        if (!this.password) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Login erred',
                detail: 'Password cannot be empty',
                life: 10000,
            })
            return
        }
        this.subs.add(
            this.auth
                .login(this.username, this.password, 'returnUrl')
                .subscribe((msg) => {
                    if (msg) {
                        this.msgSrv.add(msg)
                    }
                })
        )
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
        return window.location.hostname === 'lab.kraken.ci'
    }

    isLocal() {
        return window.location.hostname === 'localhost'
    }

    loginWith(id_provider) {
        this.auth.loginWith(id_provider)
    }

    downloadAgentInstallScript(scriptType: string) {
        if (!this.settings || !this.settings.general) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Agent Install Script download failed',
                detail: 'Cannot retrieve settings',
                life: 10000,
            })
            return
        }

        if (
            !this.settings.general.server_url ||
            this.settings.general.server_url.length < 4
        ) {
            this.msgSrv.add({
                severity: 'error',
                summary: 'Agent Install Script download failed',
                detail: 'Server URL is missing or incorrect in settings. Please, set it on Settings page.',
                life: 10000,
            })
            return
        }

        // invoke download
        const link = document.createElement('a')
        link.href = '/bk/install/kraken-agent-install.' + scriptType
        document.body.appendChild(link)
        link.click()
        link.remove()
    }

    pullLiveData() {
        this.subs.add(
            this.managementService.getLiveData().subscribe((data) => {
                // change menu with errors indicator if needed
                if (this.errorsInLogsCount !== data.error_logs_count) {
                    this.errorsInLogsCount = data.error_logs_count
                    this.topMenuItems[2].label = '' + this.errorsInLogsCount
                    this.topMenuItems[2].title =
                        '' + this.errorsInLogsCount + ' errors in the last hour'
                    if (this.errorsInLogsCount > 0) {
                        this.topMenuItems[2].icon = 'pi pi-exclamation-triangle'
                        this.topMenuItems[2].styleClass = 'error-indicator'
                    } else {
                        this.topMenuItems[2].icon = 'fa fa-smile-o'
                        this.topMenuItems[2].styleClass = ''
                    }

                    // force detection change in menu
                    this.topmenubar.cd.markForCheck()
                }

                if (this.authorizedAgents !== data.authorized_agents) {
                    this.authorizedAgents = data.authorized_agents
                    this.topMenuItems[0].items[0].badge =
                        '' + this.authorizedAgents

                    // force detection change in menu
                    this.topmenubar.cd.markForCheck()
                }

                if (this.nonAuthorizedAgents !== data.non_authorized_agents) {
                    this.nonAuthorizedAgents = data.non_authorized_agents
                    this.topMenuItems[0].items[2].badge =
                        '' + this.nonAuthorizedAgents

                    // force detection change in menu
                    this.topmenubar.cd.markForCheck()
                }

                setTimeout(() => {
                    this.pullLiveData()
                }, 15000)
            })
        )
    }
}
