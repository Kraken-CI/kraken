import { Component, OnInit, OnDestroy } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'
import { Title } from '@angular/platform-browser'
import { Observable } from 'rxjs'
import { switchMap } from 'rxjs/operators'

import { MessageService } from 'primeng/api'

import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { Run } from '../backend/model/run'
import { datetimeToLocal, humanBytes } from '../utils'

@Component({
    selector: 'app-branch-results',
    templateUrl: './branch-results.component.html',
    styleUrls: ['./branch-results.component.sass'],
})
export class BranchResultsComponent implements OnInit, OnDestroy {
    branchId = 0
    branch: any
    kind: string
    start = 0
    limit = 10
    refreshTimer: any = null

    flows: any[]

    totalFlows = 100

    stagesAvailable: any[]
    selectedStages: any[]
    selectedStage: any
    filterStageName = 'All'

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService,
        private msgSrv: MessageService,
        private titleService: Title
    ) {}

    ngOnInit() {
        this.branch = null
        this.branchId = parseInt(this.route.snapshot.paramMap.get('id'), 10)
        this.kind = this.route.snapshot.paramMap.get('kind')
        this.selectedStage = null
        this.stagesAvailable = [{ name: 'All' }]

        this.managementService.getBranch(this.branchId).subscribe(branch => {
            this.titleService.setTitle('Kraken - Branch Results - ' + branch.name + ' ' + this.kind)
            this.branch = branch
            this.updateBreadcrumb()
        })

        this.route.paramMap.subscribe(params => {
            this.branchId = parseInt(params.get('id'), 10)
            this.kind = params.get('kind')
            this.updateBreadcrumb()
            this.start = 0
            this.limit = 10
            this.refresh()
        })
    }

    cancelRefreshTimer() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer)
            this.refreshTimer = null
        }
    }

    ngOnDestroy() {
        this.cancelRefreshTimer()
    }

    updateBreadcrumb() {
        if (this.branch == null) {
            return
        }
        const crumbs = [
            {
                label: 'Projects',
                project_id: this.branch.project_id,
                project_name: this.branch.project_name,
            },
            {
                label: 'Branches',
                branch_id: this.branch.id,
                branch_name: this.branch.name,
            },
            {
                label: 'Results',
                branch_id: this.branch.id,
                flow_kind: this.kind,
            },
        ]
        this.breadcrumbService.setCrumbs(crumbs)
    }

    _processFlowData(flow, stages) {
        for (const run of flow.runs) {
            stages.add(run.stage_name)
        }
    }

    refresh() {
        this.cancelRefreshTimer()

        this.route.paramMap
            .pipe(
                switchMap((params: ParamMap) =>
                    this.executionService.getFlows(
                        parseInt(params.get('id'), 10),
                        this.kind,
                        this.start,
                        this.limit
                    )
                )
            )
            .subscribe(data => {
                let flows = []
                const stages = new Set<string>()
                this.totalFlows = data.total
                flows = flows.concat(data.items)
                for (const flow of flows) {
                    this._processFlowData(flow, stages)
                }
                this.flows = flows
                const newStages = [{ name: 'All' }]
                for (const st of Array.from(stages).sort()) {
                    newStages.push({ name: st })
                }
                this.stagesAvailable = newStages

                // refresh again in 10 seconds
                this.refreshTimer = setTimeout(() => {
                    this.refresh()
                }, 10000)
            })
    }

    paginateFlows(event) {
        this.start = event.first
        this.limit = event.rows
        this.refresh()
    }

    filterStages(event) {
        this.filterStageName = event.value.name
    }

    onStageRun(newRun) {}

    humanFileSize(bytes) {
        return humanBytes(bytes, false)
    }

    hasFlowCommits(flow) {
        if (flow.trigger && (flow.trigger.commits || flow.trigger.pull_request)) {
            return true
        }
        return false
    }

    getFlowCommits(flow) {
        let repoUrl = flow.trigger.repo
        if (repoUrl.endsWith('.git')) {
            repoUrl = repoUrl.slice(0, -4)
        }
        let html = `<p>`
        html += `<a href="${repoUrl}" target="blank" style="font-size: 1.5em; font-weight: bold;">${repoUrl}</a>`
        let startCommit = ''
        if (flow.trigger.commits) {
            startCommit = flow.trigger.before
        }
        if (flow.trigger.pull_request) {
            startCommit = flow.trigger.pull_request.base.sha
        }
        const diffUrl = `${repoUrl}/compare/${startCommit}...${flow.trigger.after}`
        html += `<a href="${diffUrl}" target="blank" style="margin-left: 20px;">diff</a><br>`
        html += `</p>`

        if (flow.trigger.commits) {
            for (const c of flow.trigger.commits) {
                html += `<p>`
                html += `<a href="${c.url}" target="blank"><b>${c.id.slice(0, 8)}</b></a>`
                html += ` by <a href="mailto:${c.author.email}">${c.author.name}</a>`
                const ts = datetimeToLocal(c.timestamp, null)
                html += ` at ${ts}<br>`
                html += `${c.message}<br>`
                const files = []
                if (c.modified) {
                    files.push(`modified ${c.modified.length}`)
                }
                if (c.added) {
                    files.push(`added ${c.added.length}`)
                }
                if (c.removed) {
                    files.push(`removed ${c.removed.length}`)
                }
                if (files.length > 0) {
                    html += '<span style="font-size: 0.8em">'
                    html += files.join(', ') + ' files'
                    html += '</span>'
                }
                html += `</p>`
            }
        }

        if (flow.trigger.pull_request) {
            const pr = flow.trigger.pull_request
            html += `<p>`
            html += `Pull Request `
            html += ` <a href="${pr.html_url}" target="blank">#${pr.number}</a> `
            html += ` by <a href="${pr.user.html_url}" target="blank">${pr.user.login}</a> `
            const ts = datetimeToLocal(pr.updated_at, null)
            html += ` at ${ts}<br>`
            html += `${pr.title}<br>`
            html += `branch: ${pr.head.ref}<br>`
            html += `commits: ${pr.commits}`
            html += `</p>`
        }

        return html
    }
}
