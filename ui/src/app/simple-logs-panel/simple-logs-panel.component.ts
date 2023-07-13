import { Component, OnDestroy, Input, OnChanges, SimpleChanges } from '@angular/core';

import { Subscription } from 'rxjs'
import { parse } from 'ansicolor'

import { MessageService } from 'primeng/api'
import { MenuItem } from 'primeng/api';

import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { showErrorBox, replaceEntityIntoLink } from '../utils'

@Component({
    selector: 'app-simple-logs-panel',
    templateUrl: './simple-logs-panel.component.html',
    styleUrls: ['./simple-logs-panel.component.sass'],
})
export class SimpleLogsPanelComponent implements OnDestroy, OnChanges {
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
    logsBegin = 0
    logsEnd = 0
    logsTotal = 0
    loading = false

    menuItems: MenuItem[];

    textSize = 0.8
    columns = [true, true, false, true, true,
               false, false, false, false, false,
               false, false, true]

    stickySide = 'top: calc(100% - 5.5rem);'

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

        this.menuItems = [{
            label: 'Text Size',
            items: [{
                label: 'Bigger',
                icon: 'pi pi-plus-circle',
                command: () => {
                    this.textSize += 0.1
                }
            }, {
                label: 'Smaller',
                icon: 'pi pi-minus-circle',
                command: () => {
                    if (this.textSize > 0) {
                        this.textSize -= 0.1
                    }
                }
            }, {
                label: 'Reset',
                icon: 'pi pi-circle',
                command: () => {
                    this.textSize = 0.8
                }
            }]
        }, {
            label: 'Columns',
            items: []
        }, {
            label: 'Download',
            icon: 'pi pi-download',
            url: '/bk/any_log'
        }]

        let cols = ['Timestamp', 'Host', 'Path:LineNo', 'Service', 'Tool', 'Step',
                    'Branch', 'Flow Kind', 'Flow', 'Run', 'Job', 'Agent', 'Level']
        for (let i = 0; i < cols.length; i++) {
            this.menuItems[1].items.push({
                label: cols[i],
                icon: this.columns[i] ? 'pi pi-circle-fill' : 'pi pi-circle',
                command: (ev) => {
                    this.toggleColumn(ev.item.state.idx)
                },
                state: {idx: i}
            })
        }
    }

    toggleColumn(colIdx) {
        this.columns[colIdx] = !this.columns[colIdx]
        if (this.columns[colIdx]) {
            this.menuItems[1].items[colIdx].icon = 'pi pi-circle-fill'
        } else {
            this.menuItems[1].items[colIdx].icon = 'pi pi-circle'
        }
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
            this.loadLogs('last')
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

    setLogDownloadsLink(branchId, flowId, runId, jobId, agentId, services, level) {
        let link = '/bk/any_log?'
        let params = []
        if (branchId) {
            params.push('branch_id=' + branchId)
        }
        if (flowId) {
            params.push('flow_id=' + flowId)
        }
        if (runId) {
            params.push('run_id=' + runId)
        }
        if (jobId) {
            params.push('job_id=' + jobId)
        }
        if (agentId) {
            params.push('agent_id=' + agentId)
        }
        if (services) {
            for (const s of services) {
                params.push('services=' + s)
            }
        }
        if (level) {
            params.push('level=' + level)
        }
        link += params.join('&')

        this.menuItems[2].url = link
    }

    loadLogs(what) {
        let branchId = this.branchId
        let flowKind
        let flowId = this.flowId
        let runId = this.runId
        let jobId = this.jobId
        let stepIdx
        let agentId = this.agentId
        let services = this.selectedServices.map(svc => svc.value)
        let level = this.selectedlogLevel ? this.selectedlogLevel : 'info'
        let start
        let limit = 100
        let order = 'asc'

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

        if (this.logsBegin === 0 && what === 'prev') {
            return
        }

        switch (what) {
        case 'first':
            start = 0
            break
        case 'prev':
            start = this.logsBegin - 100
            if (start < 0) {
                start = 0
                limit = this.logsBegin
            }
            break
        case 'next':
            start = this.logsEnd
            break
        case 'last':
            start = 0
            order = 'desc'
            break
        }

        this.setLogDownloadsLink(branchId, flowId, runId, jobId, agentId, services, level)

        this.loading = true
        this.subs.add(
            this.executionService
                .getLogs(start, limit, branchId, flowKind, flowId, runId, jobId, stepIdx, agentId, services, level, order)
                .subscribe(
                    (data) => {
                        if (what === 'first') {
                            this.logs = data.items
                            this.logsBegin = 0
                            this.logsEnd = this.logs.length
                        } else if (what === 'prev') {
                            this.logs = data.items.concat(this.logs)
                            this.logsBegin -= data.items.length
                        } else if (what === 'next') {
                            this.logs = this.logs.concat(data.items)
                            this.logsEnd += data.items.length
                        } else if (what === 'last') {
                            this.logs = data.items.reverse()
                            this.logsBegin = data.total - this.logs.length
                            this.logsEnd = data.total
                        }
                        this.logsTotal = data.total
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
        msg = replaceEntityIntoLink(msg)

        // turn ansi codes into spans with css colors
        const p = parse(msg)
        const spans = []
        for (const el of p.spans) {
            spans.push(`<span style="${el.css}">${el.text}</span>`)
        }
        msg = spans.join('')

        return msg
    }

    scrolled(event) {
        const percent = event.target.scrollTop /  (event.target.scrollHeight - event.target.clientHeight)
        if (percent < 0.5) {
            this.stickySide = 'top: calc(100% - 5.5rem);'
        } else {
            this.stickySide = 'top: 0;'
        }
    }
}
