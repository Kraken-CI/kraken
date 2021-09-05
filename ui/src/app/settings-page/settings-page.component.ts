import { Component, OnInit } from '@angular/core'
import { Title } from '@angular/platform-browser'
import { FormGroup, FormControl } from '@angular/forms'

import { AuthService } from '../auth.service'
import { MessageService } from 'primeng/api'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { SettingsService } from '../services/settings.service'

@Component({
    selector: 'app-settings-page',
    templateUrl: './settings-page.component.html',
    styleUrls: ['./settings-page.component.sass'],
})
export class SettingsPageComponent implements OnInit {
    settings: any

    tabIndex = 0

    emailState = ''
    emailChecking = false
    slackState = ''
    slackChecking = false
    awsState = ''
    awsChecking = false
    azureState = ''
    azureChecking = false

    generalForm = new FormGroup({
        server_url: new FormControl(''),
        minio_addr: new FormControl(''),
        clickhouse_addr: new FormControl(''),
    })

    notificationForm = new FormGroup({
        smtp_server: new FormControl(''),
        smtp_tls: new FormControl(''),
        smtp_from: new FormControl(''),
        smtp_user: new FormControl(''),
        smtp_password: new FormControl(''),
        slack_token: new FormControl(''),
    })

    monitoringForm = new FormGroup({
        sentry_dsn: new FormControl(''),
    })

    cloudForm = new FormGroup({
        // AWS
        aws_access_key: new FormControl(''),
        aws_secret_access_key: new FormControl(''),
        // Azure
        azure_subscription_id: new FormControl(''),
        azure_tenant_id: new FormControl(''),
        azure_client_id: new FormControl(''),
        azure_client_secret: new FormControl(''),
    })

    constructor(
        public auth: AuthService,
        private msgSrv: MessageService,
        protected breadcrumbService: BreadcrumbsService,
        protected settingsService: SettingsService,
        private titleService: Title
    ) {}

    ngOnInit() {
        this.titleService.setTitle('Kraken - Settings')

        this.breadcrumbService.setCrumbs([
            {
                label: 'Home',
            },
            {
                label: 'Settings',
            },
        ])

        this.settingsService.settings.subscribe((settings) => {
            if (settings === null) {
                return
            }
            this.generalForm.setValue(settings.general)
            this.notificationForm.setValue(settings.notification)
            this.monitoringForm.setValue(settings.monitoring)
            this.cloudForm.setValue(settings.cloud)
        })
    }

    saveSettings() {
        const settings: any = {}

        // save settings from current tab
        switch (this.tabIndex) {
            case 0:
                settings.general = this.generalForm.value
                break
            case 1:
                settings.notification = this.notificationForm.value
                break
            case 2:
                settings.monitoring = this.monitoringForm.value
                break
            case 3:
                settings.cloud = this.cloudForm.value
                break
        }

        this.settingsService.updateSettings(settings).subscribe(
            (settings2) => {
                this.settings = settings2
                this.msgSrv.add({
                    severity: 'success',
                    summary: 'Settings update succeeded',
                    detail: 'Settings update operation succeeded.',
                })
            },
            (err) => {
                let msg = err.statusText
                if (err.error && err.error.detail) {
                    msg = err.error.detail
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Settings update erred',
                    detail: 'Settings update operation erred: ' + msg,
                    life: 10000,
                })
            }
        )
    }

    checkResourceWorkingState(resource) {
        switch (resource) {
            case 'email':
                this.emailChecking = true
                break
            case 'slack':
                this.slackChecking = true
                break
            case 'aws':
                this.awsChecking = true
                break
            case 'azure':
                this.azureChecking = true
                break
        }
        this.settingsService.checkResourceWorkingState(resource).subscribe(
            (data) => {
                console.info(data)
                switch (resource) {
                    case 'email':
                        this.emailState = data.state
                        this.emailChecking = false
                        break
                    case 'slack':
                        this.slackState = data.state
                        this.slackChecking = false
                        break
                    case 'aws':
                        this.awsState = data.state
                        this.awsChecking = false
                        break
                    case 'azure':
                        this.azureState = data.state
                        this.azureChecking = false
                        break
                }
            },
            (err) => {
                switch (resource) {
                    case 'email':
                        this.emailChecking = false
                        break
                    case 'slack':
                        this.slackChecking = false
                        break
                    case 'aws':
                        this.awsChecking = false
                        break
                    case 'azure':
                        this.azureChecking = false
                        break
                }
                let msg = err.statusText
                if (err.error && err.error.detail) {
                    msg = err.error.detail
                }
                this.msgSrv.add({
                    severity: 'error',
                    summary: 'Checking failed',
                    detail: 'Checking erred: ' + msg,
                    life: 10000,
                })
            }
        )
    }
}
