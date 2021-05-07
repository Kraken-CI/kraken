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

    generalForm = new FormGroup({
        server_url: new FormControl(''),
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
        aws_access_key: new FormControl(''),
        aws_secret_access_key: new FormControl(''),
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
        const settings = {
            general: this.generalForm.value,
            notification: this.notificationForm.value,
            monitoring: this.monitoringForm.value,
            cloud: this.cloudForm.value,
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
}
