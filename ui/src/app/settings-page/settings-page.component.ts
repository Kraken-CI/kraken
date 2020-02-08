import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser'
import { FormGroup, FormControl } from '@angular/forms'

import { MessageService } from 'primeng/api'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { ManagementService } from '../backend/api/management.service'

@Component({
  selector: 'app-settings-page',
  templateUrl: './settings-page.component.html',
  styleUrls: ['./settings-page.component.sass']
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

    constructor(
        private msgSrv: MessageService,
        protected breadcrumbService: BreadcrumbsService,
        protected managementService: ManagementService,
        private titleService: Title) { }

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

        this.managementService.getSettings().subscribe(
            settings => {
                console.info(settings)
                this.generalForm.setValue(settings.general)
                this.notificationForm.setValue(settings.notification)
            }
        )
    }

    saveSettings() {
        const settings = {
            general: this.generalForm.value,
            notification: this.notificationForm.value
        }
        this.managementService
            .updateSettings(settings)
            .subscribe(
                settings => {
                    this.settings = settings
                    this.msgSrv.add({
                        severity: 'success',
                        summary: 'Settings update succeeded',
                        detail: 'Settings update operation succeeded.',
                    })
                },
                err => {
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
