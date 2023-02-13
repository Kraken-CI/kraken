import { Component, OnInit, OnDestroy } from '@angular/core'
import { Title } from '@angular/platform-browser'
import {
    UntypedFormGroup,
    UntypedFormControl,
    FormGroup,
    FormControl,
} from '@angular/forms'

import { Subscription } from 'rxjs'

import { AuthService } from '../auth.service'
import { MessageService } from 'primeng/api'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { SettingsService } from '../services/settings.service'

@Component({
    selector: 'app-settings-page',
    templateUrl: './settings-page.component.html',
    styleUrls: ['./settings-page.component.sass'],
})
export class SettingsPageComponent implements OnInit, OnDestroy {
    settings: any

    tabName = 'general'

    emailState = ''
    emailChecking = false
    slackState = ''
    slackChecking = false
    awsState = ''
    awsChecking = false
    azureState = ''
    azureChecking = false
    kubernetesState = ''
    kubernetesChecking = false
    ldapState = ''
    ldapChecking = false

    generalForm = new UntypedFormGroup({
        server_url: new UntypedFormControl(''),
        minio_addr: new UntypedFormControl(''),
        clickhouse_addr: new UntypedFormControl(''),
        clickhouse_log_ttl: new FormControl(''),
    })

    notificationForm = new UntypedFormGroup({
        smtp_server: new UntypedFormControl(''),
        smtp_tls: new UntypedFormControl(''),
        smtp_from: new UntypedFormControl(''),
        smtp_user: new UntypedFormControl(''),
        smtp_password: new UntypedFormControl(''),
        slack_token: new UntypedFormControl(''),
    })

    monitoringForm = new UntypedFormGroup({
        sentry_dsn: new UntypedFormControl(''),
    })

    cloudForm = new UntypedFormGroup({
        // AWS
        aws_access_key: new UntypedFormControl(''),
        aws_secret_access_key: new UntypedFormControl(''),
        // Azure
        azure_subscription_id: new UntypedFormControl(''),
        azure_tenant_id: new UntypedFormControl(''),
        azure_client_id: new UntypedFormControl(''),
        azure_client_secret: new UntypedFormControl(''),
        // Kubernetes
        k8s_api_server_url: new UntypedFormControl(''),
        k8s_namespace: new UntypedFormControl(''),
        k8s_token: new UntypedFormControl(''),
    })

    idpForm = new FormGroup({
        // LDAP
        ldap_enabled: new FormControl(false),
        ldap_server: new FormControl(''),
        bind_dn: new FormControl(''),
        bind_password: new FormControl(''),
        base_dn: new FormControl(''),
        search_filter: new FormControl(''),

        // Google OIDC
        google_enabled: new FormControl(false),
        google_client_id: new FormControl(''),
        google_client_secret: new FormControl(''),

        // Microsoft Azure
        microsoft_enabled: new FormControl(false),
        microsoft_client_id: new FormControl(''),
        microsoft_client_secret: new FormControl(''),

        // GitHub
        github_enabled: new FormControl(false),
        github_client_id: new FormControl(''),
        github_client_secret: new FormControl(''),

        // Auth0
        auth0_enabled: new FormControl(false),
        auth0_client_id: new FormControl(''),
        auth0_client_secret: new FormControl(''),
        auth0_openid_config_url: new FormControl(''),
    })

    private subs: Subscription = new Subscription()

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

        this.subs.add(
            this.settingsService.settings.subscribe((settings) => {
                if (settings === null || !settings.general) {
                    return
                }
                this.generalForm.setValue(settings.general)
                this.notificationForm.setValue(settings.notification)
                this.monitoringForm.setValue(settings.monitoring)
                this.cloudForm.setValue(settings.cloud)
                this.idpForm.setValue(settings.idp)
            })
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    handleTabChange(tabName) {
        this.tabName = tabName
    }

    saveSettings() {
        const settings: any = {}

        // save settings from current tab
        switch (this.tabName) {
            case 'general':
                settings.general = this.generalForm.value
                break
            case 'notifications':
                settings.notification = this.notificationForm.value
                break
            case 'monitoring':
                settings.monitoring = this.monitoringForm.value
                break
            case 'cloud':
                settings.cloud = this.cloudForm.value
                break
            case 'identity-providers':
                settings.idp = this.idpForm.value
                break
        }

        this.subs.add(
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
            case 'kubernetes':
                this.kubernetesChecking = true
                break
            case 'ldap':
                this.ldapChecking = true
                break
        }
        this.subs.add(
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
                        case 'kubernetes':
                            this.kubernetesState = data.state
                            this.kubernetesChecking = false
                            break
                        case 'ldap':
                            this.ldapState = data.state
                            this.ldapChecking = false
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
                        case 'kubernetes':
                            this.kubernetesChecking = false
                            break
                        case 'ldap':
                            this.ldapChecking = false
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
        )
    }
}
