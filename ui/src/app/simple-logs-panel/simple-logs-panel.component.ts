import { Component, OnInit, OnDestroy, Input } from '@angular/core';

import { Subscription } from 'rxjs'
import { parse } from 'ansicolor'

import { ExecutionService } from '../backend/api/execution.service'

@Component({
  selector: 'app-simple-logs-panel',
  templateUrl: './simple-logs-panel.component.html',
  styleUrls: ['./simple-logs-panel.component.sass']
})
export class SimpleLogsPanelComponent implements OnInit, OnDestroy {
    @Input() topOffset: number = 0
    @Input() branchId: number
    @Input() flowId: number
    @Input() runId: number
    @Input() jobId: number
    @Input() agentId: number

    private subs: Subscription = new Subscription()

    logs: any = []
    loading = false

    constructor(protected executionService: ExecutionService) { }

    ngOnInit(): void {
        this.loadLogs()
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
        //this.resetLogging()
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
        let order = 'desc'

        this.loading = true
        this.subs.add(
            this.executionService
                .getLogs(start, limit, branchId, flowKind, flowId, runId, jobId, stepIdx, agentId, order)
                .subscribe(
                    (data) => {
                        this.logs = data.items
                        this.loading = false
                    },
                    (err) => {
                        this.loading = false
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
