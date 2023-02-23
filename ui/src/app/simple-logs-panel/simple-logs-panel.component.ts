import { Component, OnInit, OnDestroy, Input, OnChanges, SimpleChanges } from '@angular/core';

import { MessageService } from 'primeng/api'
import { Subscription } from 'rxjs'
import { parse } from 'ansicolor'

import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { showErrorBox } from '../utils'

@Component({
    selector: 'app-simple-logs-panel',
    templateUrl: './simple-logs-panel.component.html',
    styleUrls: ['./simple-logs-panel.component.sass'],
})
export class SimpleLogsPanelComponent implements OnInit, OnDestroy, OnChanges {
    @Input() visible: boolean
    @Input() logLevel: string
    @Input() topOffset: number = 0
    @Input() branchId: number
    @Input() flowId: number
    @Input() runId: number
    @Input() jobId: number
    @Input() agentId: number
    @Input() initServices: string[] = []

    private subs: Subscription = new Subscription()

    _visible = false

    services: any = []
    selectedServices: any = []

    logLevels: any[]
    selectedlogLevel: any

    rqJobs: any[]
    rqJob: any = 'all'

    logs: any = []
    loading = false

    constructor(
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
        private msgSrv: MessageService,
    ) {
        this.services = [
            { name: 'agent', value: 'agent' },
            { name: 'server', value: 'server' },
            { name: 'server/api', value: 'server/api' },
            { name: 'server/backend', value: 'server/backend' },
            { name: 'server/webhooks', value: 'server/webhooks' },
            { name: 'server/artifacts', value: 'server/artifacts' },
            { name: 'server/install', value: 'server/install' },
            { name: 'server/job-log', value: 'server/job-log' },
            { name: 'server/badge', value: 'server/badge' },
            { name: 'server/other', value: 'server/other' },
            { name: 'rq', value: 'rq' },
            { name: 'scheduler', value: 'scheduler' },
            { name: 'planner', value: 'planner' },
            { name: 'watchdog', value: 'watchdog' },
        ]

        this.logLevels = [
            { label: 'Info', value: 'info' },
            { label: 'Warning', value: 'warning' },
            { label: 'Error', value: 'error' },
        ]
    }

    ngOnInit(): void {
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
        //this.resetLogging()
    }

    ngOnChanges(changes: SimpleChanges) {
        let reload = false
        if (changes?.logLevel?.currentValue) {
            this.selectedlogLevel = changes.logLevel.currentValue
            reload = true
        }
        if (changes?.visible?.currentValue) {
            this._visible = changes.visible.currentValue
            reload = true
        }
        if (this.selectedServices.length === 0 && changes?.initServices?.currentValue) {
            this.selectedServices = this.initServices.map(svc => ({name: svc, value: svc}))
        }

        if (this._visible && reload) {
            this.loadLogs()
            this.loadLastRQJobsNames()
        }
    }

    loadLastRQJobsNames() {
        this.subs.add(
            this.managementService.getLastRqJobsNames().subscribe((data) => {
                this.rqJobs = [{ label: '-- all --', value: 'all' }]
                for (const t of data.items) {
                    this.rqJobs.push({ label: t.name, value: t.name, time: t.time })
                }
            })
        )
    }

    loadLogs() {
        let start = 0
        let limit = 100
        let branchId = this.branchId
        let flowKind
        let flowId = this.flowId
        let runId = this.runId
        let jobId = this.jobId
        let stepIdx
        let agentId = this.agentId
        let services = this.selectedServices.map(svc => svc.value)
        let level = this.selectedlogLevel ? this.selectedlogLevel : 'info'
        let order = 'desc'

        if (services.length > 0 && this.rqJob && this.rqJob !== 'all') {
            let services2 = []
            for (let s of services) {
                if (s === 'rq') {
                    s = 'rq/' + this.rqJob
                }
                services2.push(s)
            }
            services = services2
        }


        this.loading = true
        this.subs.add(
            this.executionService
                .getLogs(start, limit, branchId, flowKind, flowId, runId, jobId, stepIdx, agentId, services, level, order)
                .subscribe(
                    (data) => {
                        this.logs = data.items.reverse()
                        this.loading = false
                    },
                    (err) => {
                        this.loading = false
                        showErrorBox(
                            this.msgSrv,
                            err,
                            'Getting branch flows erred'
                        )
                    }
                )
        )
    }

    prepareLogLine(msg) {
        // turn <Entity 123> into links
        const regex = /<([A-Za-z]+)\ (\d+)(>|[,\ >]+?.*?>)/g;
        const m1 = msg.matchAll(regex)
        if (m1) {
            const m2 = [...m1]
            for (const m of m2) {
                let txt = m[0]
                txt = txt.replace('<', '&lt;')
                txt = txt.replace('>', '&gt;')
                let entity = m[1].toLowerCase()
                switch (entity) {
                case 'run': entity = 'runs'; break;
                case 'branch': entity = 'branches'; break;
                case 'flow': entity = 'flows'; break;
                default: entity = null
                }
                let newTxt = ''
                if (entity) {
                    const entId = m[2]
                    newTxt = `<a href="/${entity}/${entId}" target="blank" style="color: #5bb7ff;">${txt}</a>`
                } else {
                    newTxt = m[0].replaceAll('<', '&lt;').replaceAll('>', '&gt;')
                }
                msg = msg.replace(m[0], newTxt)
            }
        }
        // msg = msg.replaceAll('<', '&lt;')
        // msg = msg.replaceAll('>', '&gt;')

        // turn ansi codes into spans with css colors
        const p = parse(msg)
        const spans = []
        for (const el of p.spans) {
            spans.push(`<span style="${el.css}">${el.text}</span>`)
        }
        msg = spans.join('')

        return msg
    }
}
