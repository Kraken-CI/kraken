import { Component, Input, OnInit, OnDestroy, ViewChild } from '@angular/core'
import { ActivatedRoute } from '@angular/router'

import { Subscription } from 'rxjs'

import { MessageService } from 'primeng/api'
import { Table } from 'primeng/table'

import { marked } from 'marked'
import { combineLatest } from 'rxjs'

import { ManagementService } from '../backend/api/management.service'
import { ExecutionService } from '../backend/api/execution.service'
import { ResultsService } from '../backend/api/results.service'
import { TestCaseResults } from '../test-case-results'
import { Run, System, Group } from '../backend/model/models'

@Component({
    selector: 'app-tcr-table',
    templateUrl: './tcr-table.component.html',
    styleUrls: ['./tcr-table.component.sass'],
})
export class TcrTableComponent implements OnInit, OnDestroy {
    @Input()
    run: Run = { state: 'in-progress', tests_passed: 0 }

    systems: System[] = []
    groups: Group[] = []

    // results
    results: any[]
    totalResults = 0
    loadingResults = true
    resultStatuses: any[]
    filterStatuses: any[] = []
    resultChanges: any[]
    filterChanges: any[] = []
    filterMinAge = 0
    filterMaxAge = 1000
    filterInstabilityRange: number[] = [0, 10]
    filterTestCaseText = ''
    filterResultJob = ''
    filterResultSystems: System[] = []
    filterResultGroups: Group[] = []

    @ViewChild('resultsTable') resultsTable: Table

    // comment dialog
    tcrCommentDlgVisible = false
    tcrCommentName = ''
    commentAuthor = ''
    commentState: any
    commentText = ''
    preview = false
    previewHtml = ''
    tcr = { id: 0, comment: { data: [], state: 0 }, relevancy: 0 }
    commentStates = []

    private subs: Subscription = new Subscription()

    constructor(
        private route: ActivatedRoute,
        protected managementService: ManagementService,
        protected executionService: ExecutionService,
        protected resultsService: ResultsService,
        private msgSrv: MessageService
    ) {
        this.resultStatuses = [
            { name: 'Not Run', code: 0 },
            { name: 'Passed', code: 1 },
            { name: 'Failed', code: 2 },
            { name: 'Error', code: 3 },
            { name: 'Disabled', code: 4 },
            { name: 'Unsupported', code: 5 },
        ]

        this.resultChanges = [
            { name: 'No changes', code: 0 },
            { name: 'Fixes', code: 1 },
            { name: 'Regressions', code: 2 },
            { name: 'New', code: 3 },
        ]

        this.commentStates = [
            {
                name: this.cmtStateToTxt(0),
                value: 0,
            },
            {
                name: this.cmtStateToTxt(1),
                value: 1,
            },
            {
                name: this.cmtStateToTxt(2),
                value: 2,
            },
            {
                name: this.cmtStateToTxt(3),
                value: 3,
            },
        ]
    }

    ngOnInit(): void {
        this.results = []
        this.resetResultsFilter(null)

        const systems$ = this.managementService.getSystems()
        const groups$ = this.managementService.getGroups(0, 1000)
        this.subs.add(
            combineLatest(systems$, groups$, this.route.queryParams).subscribe(
                ([systems, groups, params]) => {
                    this.systems = systems.items
                    this.groups = groups.items

                    const sysId = parseInt(params.system, 10)
                    if (sysId) {
                        const sys = this.systems.find((s) => s.id === sysId)
                        if (sys) {
                            this.filterResultSystems = [sys]
                        }
                    }

                    const grpId = parseInt(params.group, 10)
                    if (grpId) {
                        const grp = this.groups.find((g) => g.id === grpId)
                        if (grp) {
                            this.filterResultGroups = [grp]
                        }
                    }

                    this.loadResultsLazy({ first: 0, rows: 30 })
                }
            )
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    loadResultsLazy(event) {
        let statuses = this.filterStatuses.map((e) => e.code)
        if (statuses.length === 0) {
            statuses = null
        }
        let changes = this.filterChanges.map((e) => e.code)
        if (changes.length === 0) {
            changes = null
        }
        let sortField = 'name'
        if (event.sortField) {
            sortField = event.sortField
        }
        let sortDir = 'asc'
        if (event.sortOrder === -1) {
            sortDir = 'desc'
        }

        this.loadingResults = true
        this.subs.add(
            this.resultsService
                .getRunResults(
                    this.run.id,
                    event.first,
                    event.rows,
                    sortField,
                    sortDir,
                    statuses,
                    changes,
                    this.filterMinAge,
                    this.filterMaxAge,
                    this.filterInstabilityRange[0],
                    this.filterInstabilityRange[1],
                    this.filterTestCaseText,
                    this.filterResultJob,
                    this.filterResultSystems.map((x) => x.id),
                    this.filterResultGroups.map((x) => x.id)
                )
                .subscribe((data) => {
                    this.results = data.items
                    this.totalResults = data.total
                    this.loadingResults = false
                })
        )
    }

    refreshResults() {
        this.resultsTable.onLazyLoad.emit(
            this.resultsTable.createLazyLoadMetadata()
        )
    }

    showLastTestChanges(resultsTable) {
        this.filterMinAge = 0
        this.filterMaxAge = 0
        this.refreshResults()
    }

    resetResultsFilter(resultsTable) {
        this.filterStatuses = []
        this.filterChanges = []
        this.filterMinAge = 0
        this.filterMaxAge = 1000
        this.filterInstabilityRange = [0, 10]
        this.filterResultSystems = []
        this.filterResultGroups = []

        if (resultsTable) {
            this.refreshResults()
        }
    }

    filterResultsKeyDown(event, resultsTable) {
        if (event.key === 'Enter') {
            this.refreshResults()
        }
    }

    formatResult(result) {
        return TestCaseResults.formatResult(result)
    }

    resultToTxt(result) {
        return TestCaseResults.resultToTxt(result)
    }

    resultToClass(result) {
        return 'result' + result
    }

    getResultChangeTxt(change) {
        switch (change) {
            case 0:
                return ''
            case 1:
                return 'FIX'
            case 2:
                return 'REGR'
            case 3:
                return 'NEW'
            default:
                return 'UNKN'
        }
    }

    getResultChangeCls(change) {
        switch (change) {
            case 1:
                return 'result-fix'
            case 2:
                return 'result-regr'
            case 3:
                return 'result-new'
            default:
                return ''
        }
    }

    getRelevancyDescr(res) {
        let txts = []
        let val = 0
        if (res.result !== 1) {
            txts.push('+1 for not passed')
            val += 1

            if (
                !res.comment ||
                (res.comment.state != 2 && res.comment.state != 3)
            ) {
                txts.push('+1 for not root caused problem')
                val += 1
            }
        }
        if (res.result === 2) {
            txts.push('+1 for failure')
            val += 1
        }
        if (res.instability <= 3) {
            txts.push('+1 for instability <= 3')
            val += 1
        }
        if (res.age < 5) {
            txts.push('+1 for age < 5')
            val += 1
        }
        if (res.change === 2) {
            txts.push('+1 for regression')
            val += 1
        }

        if (val > 0) {
            txts.push('= ' + val)
        }

        return txts.join('<br>')
    }

    cmtStateToTxt(state) {
        switch (state) {
            case 0:
                return 'new'
            case 1:
                return 'investigating'
            case 2:
                return 'bug in product'
            case 3:
                return 'bug in test'
            default:
                return 'uknown ' + state
        }
    }

    showCommentDialog(res) {
        this.tcrCommentName = res.test_case_name
        this.tcrCommentDlgVisible = true
        this.tcr = res

        if (res.comment) {
            for (let c of res.comment.data) {
                c.html = marked.parse(c.text)
                c.stateTxt = this.cmtStateToTxt(c.state)
            }
        }
    }

    cancelTcrComment() {
        this.tcrCommentDlgVisible = false
    }

    addTcrComment() {
        this.subs.add(
            this.resultsService
                .createOrUpdateTestCaseComment(this.tcr.id, {
                    author: this.commentAuthor,
                    state: parseInt(this.commentState, 10),
                    text: this.commentText,
                })
                .subscribe(
                    (data) => {
                        this.msgSrv.add({
                            severity: 'success',
                            summary: 'Comment updated',
                            detail: 'Comment has been updated.',
                        })
                        this.commentAuthor = ''
                        this.commentState = 0
                        this.commentText = ''
                        this.tcrCommentDlgVisible = false

                        this.refreshResults()
                    },
                    (err) => {
                        this.msgSrv.add({
                            severity: 'error',
                            summary: 'Comment update erred',
                            detail: 'Updating comment erred: ' + err.statusText,
                            life: 10000,
                        })
                    }
                )
        )
    }

    previewComment() {
        this.preview = !this.preview
        if (this.preview) {
            this.previewHtml = marked.parse(this.commentText)
        }
    }
}
