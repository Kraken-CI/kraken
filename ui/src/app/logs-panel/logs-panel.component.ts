import { Component, OnInit, OnDestroy, Input, ViewChild, ElementRef, ViewChildren, QueryList } from '@angular/core';
import { Pipe, PipeTransform } from '@angular/core'
import { DomSanitizer, SafeHtml } from '@angular/platform-browser'

import { Subscription } from 'rxjs'

import { parse } from 'ansicolor'
import { DateTime } from 'luxon'

import { ExecutionService } from '../backend/api/execution.service'

@Component({
  selector: 'app-logs-panel',
  templateUrl: './logs-panel.component.html',
  styleUrls: ['./logs-panel.component.sass']
})
export class LogsPanelComponent implements OnInit, OnDestroy {
    @ViewChild('logPanel') logPanel: ElementRef
    @ViewChildren('logStep') logSteps: QueryList<any>

    prvJob: any
    @Input()
    set job(job) {
        let prevJob = this.prvJob
        this.prvJob = job

        if ((!prevJob && job) ||
            (prevJob && !job) ||
            (prevJob.id !== job.id)) {
            this.resetState()
            // TODO: maybe add some jobs states caching
        }

        if (job) {
            this.handleJobUpdate()
        }
    }
    get job() {
        return this.prvJob
    }

    stepsStates: any = []

    timer: any = null
    lastLogChecksCount = 0

    logInternals = false
    logTimestamps = false

    isNearBottom = false

    private subs: Subscription = new Subscription()

    constructor(protected executionService: ExecutionService) {
    }

    ngOnInit(): void {
        this.resetState()
    }

    resetState() {
        console.info('reset state')
        this.stepsStates = []
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
        this.resetLogging()
    }

    handleJobUpdate() {
        if (this.job.steps.length === 0) {
            return
        }

        console.info('job update')

        // in initialload prepare steps local states
        if (this.stepsStates.length === 0) {
            for (let i = 0; i < this.job.steps.length; i++) {
                this.stepsStates.push({
                    step: this.job.steps[i],
                    expanded: false,
                    loading: false,
                    logs: [],
                    total: 0,
                    start: 0,
                    end: 0
                })
            }
        } else {
            for (let i = 0; i < this.job.steps.length; i++) {
                this.stepsStates[i].step = this.job.steps[i]
            }
        }
    }

    toggleStep(stepIdx) {
        let stepLogsState = this.stepsStates[stepIdx]
        stepLogsState.expanded = !stepLogsState.expanded

        // TODO if step not started to not load logs
        //if

        this.resetLogging()

        if (stepLogsState.expanded) {
            this.loadLastPage(stepIdx)
        }

    }

    loadAllPages(stepIdx) {
        let stepLogsState = this.stepsStates[stepIdx]
        stepLogsState.loading = true
        let start = 0
        let limit = stepLogsState.total
        this.subs.add(
            this.executionService.getStepLogs(this.prvJob.id, stepIdx, start, limit, 'asc', this.logInternals).subscribe(
                (data) => {
                    stepLogsState.logs = data.items
                    stepLogsState.total = data.total
                    stepLogsState.start = 1
                    stepLogsState.end = limit
                    stepLogsState.loading = false
                },
                (err) => {
                }
            )
        )
    }

    loadFirstPage(stepIdx) {
        let stepLogsState = this.stepsStates[stepIdx]
        stepLogsState.loading = true
        let start = 0
        let limit = 100
        this.subs.add(
            this.executionService.getStepLogs(this.prvJob.id, stepIdx, start, limit, 'asc', this.logInternals).subscribe(
                (data) => {
                    stepLogsState.logs = data.items
                    stepLogsState.total = data.total
                    stepLogsState.start = 1
                    stepLogsState.end = limit
                    stepLogsState.loading = false
                },
                (err) => {
                }
            )
        )
    }

    loadPrevPage(stepIdx) {
        let stepLogsState = this.stepsStates[stepIdx]
        stepLogsState.loading = true
        let start = stepLogsState.start - 101
        let limit = 100
        if (start < 0) {
            limit += start
            start = 0
        }
        this.subs.add(
            this.executionService.getStepLogs(this.prvJob.id, stepIdx, start, limit, 'asc', this.logInternals).subscribe(
                (data) => {
                    stepLogsState.logs = data.items.concat(stepLogsState.logs)
                    stepLogsState.total = data.total
                    stepLogsState.start = start + 1
                    stepLogsState.loading = false
                },
                (err) => {
                }
            )
        )
    }

    loadNextPage(stepIdx, carryOn) {
        let stepLogsState = this.stepsStates[stepIdx]
        stepLogsState.loading = true
        let start = stepLogsState.end
        let limit = 100
        this.subs.add(
            this.executionService.getStepLogs(this.prvJob.id, stepIdx, start, limit, 'asc', this.logInternals).subscribe(
                (data) => {
                    stepLogsState.logs = stepLogsState.logs.concat(data.items)
                    stepLogsState.total = data.total
                    stepLogsState.end += data.items.length
                    stepLogsState.loading = false

                    if (carryOn) {
                        this.continueLogLoadingIfNeeded(stepIdx)
                    }
                },
                (err) => {
                }
            )
        )
    }

    loadLastPage(stepIdx) {
        let stepLogsState = this.stepsStates[stepIdx]
        stepLogsState.loading = true
        this.subs.add(
            this.executionService.getStepLogs(this.prvJob.id, stepIdx, 0, 100, 'desc', this.logInternals).subscribe(
                (data) => {
                    stepLogsState.logs = data.items.reverse()
                    stepLogsState.total = data.total
                    stepLogsState.start = data.total - data.items.length + 1
                    stepLogsState.end = data.total
                    stepLogsState.loading = false

                    this.continueLogLoadingIfNeeded(stepIdx)
                },
                (err) => {
                }
            )
        )
    }

    continueLogLoadingIfNeeded(stepIdx) {
        if (this.isNearBottom) {
            this.scrollToBottom()
        }

        let stepLogsState = this.stepsStates[stepIdx]

        if (!stepLogsState.expanded) {
            return
        }

        if (stepLogsState.total > stepLogsState.end) {
            this.lastLogChecksCount = 0
            this.loadNextPage(stepIdx, true)
        } else {
            let waitTime = 3000
            let step = this.job.steps[stepIdx]
            console.info('STEP idx:', stepIdx, 'status:', step.status, 'chk cnt:', this.lastLogChecksCount)
            if (step.status !== 1) {
                this.lastLogChecksCount += 1
                if (this.lastLogChecksCount === 4) {
                    return
                }
                waitTime = 2000 + 1000 * this.lastLogChecksCount
            }
            this.timer = setTimeout(() => {
                this.timer = null
                this.loadNextPage(stepIdx, true)
            }, waitTime)
        }
    }

    resetLogging() {
        if (this.timer !== null) {
            clearTimeout(this.timer)
            this.timer = null
        }
        this.lastLogChecksCount = 0
    }

    getStepHeadingClass(step) {
        let stepLogsState = this.stepsStates[step.index]

        let classes = 'flex justify-content-between align-items-baseline sticky top-0 z-1 p-2 cursor-pointer transition-colors transition-duration-200'

        if (stepLogsState.expanded) {
            classes += ' font-semibold bg-gray-800 hover:bg-gray-700'
        } else {
            classes += ' font-normal bg-gray-900 hover:bg-gray-800'
        }

        if (step.status === 1) { // in-progress
            classes += ' step-heading-pulse'
        } else {
            if (stepLogsState.expanded) {
                classes += ' text-300'
            } else {
                classes += ' text-400'
            }
        }

        return classes
    }

    getStepStatusClass(step) {
        switch (step.status) {
            case 0:  // not-started
                return 'pi pi-circle text-gray-600'
            case 1:  // in-progress
                return 'pi pi-spin pi-spinner text-blue-400'
            case 2:  // done
                return 'pi pi-check-circle text-green-400'
            case 3:  // error
                return 'pi pi-exclamation-circle text-red-400'
            default:
                return 'pi pi-circle text-gray-600'
        }
    }

    getStepStatus(step) {
        switch (step.status) {
            case null:
                return 'not started'
            case 0:
                return 'not started'
            case 1:
                return 'in progress'
            case 2:
                return 'done'
            case 3:
                return 'error'
            default:
                return 'unknown'
        }
    }

    getStepInfo(step) {
        let kv = {}

        for (const [key, value] of Object.entries(step)) {
            if (['env', 'id', 'index', 'job_id', 'name', 'result', 'status',
                 'tool', 'tool_entry', 'tool_id', 'tool_location',
                 'tool_version'].includes(key)) {
                continue
            }
            kv[key] = value
        }
        if (kv['script']) {
            let t = kv['script'].trim().split(/\r?\n/)[0]
            kv['script'] = t + '...'
        }
        return kv
    }

    prepareLogLine(stepState, line) {
        const currTs = line.slice(0, 23)
        const currTsObj = DateTime.fromFormat(
            currTs,
            'yyyy-MM-dd HH:mm:ss,SSS'
        )
        if (this.logTimestamps) {
            // fix missing timestamps
            if (currTsObj.isValid) {
                stepState.prevTs = currTs
            } else if (stepState.prevTs) {
                line = stepState.prevTs + ' ' + line
            }
        } else {
            // strip timestamps
            if (currTsObj.isValid) {
                line = line.slice(24)
            }
        }

        // turn ansi codes into spans with css colors
        const p = parse(line)
        const spans = []
        for (const el of p.spans) {
            spans.push(`<span style="${el.css}">${el.text}</span>`)
        }
        line = spans.join('')

        return line
    }

    toggleTimestamps(stepIdx) {
        event.stopPropagation()
        this.logTimestamps = !this.logTimestamps
        this.loadLastPage(stepIdx)
    }

    toggleInternals(stepIdx) {
        event.stopPropagation()
        this.logInternals = !this.logInternals
        this.loadLastPage(stepIdx)
    }

    scrollToStepBottom(event, idx) {
        event.stopPropagation()
        console.info('bottom')

        if (!this.logPanel) {
            console.info('no logPanel yet')
            return
        }
        let logPanelEl = this.logPanel.nativeElement

        let logStepEls = this.logSteps.toArray()
        if (logStepEls.length === 0) {
            return
        }
        let firstLogStepEl = logStepEls[idx].nativeElement
        let currLogStepEl = logStepEls[idx].nativeElement

        let scrollTo = currLogStepEl.offsetTop + currLogStepEl.offsetHeight - logPanelEl.offsetHeight - firstLogStepEl.offsetTop + 30
        if (scrollTo < 0) {
            scrollTo = 0
        }

        logPanelEl.scroll({
            top: scrollTo,
            left: 0,
        })
    }

    isScrollNearBottom() {
        let logPanelEl = this.logPanel.nativeElement
        const threshold = 300
        const position = logPanelEl.scrollTop + logPanelEl.offsetHeight
        const height = logPanelEl.scrollHeight
        return position > height - threshold
    }

    scrolled(event) {
        this.isNearBottom = this.isScrollNearBottom()
        console.info('this.isNearBottom', this.isNearBottom)
    }

    scrollToBottom() {
        let logPanelEl = this.logPanel.nativeElement
        logPanelEl.scroll({
            top: logPanelEl.scrollHeight,
            left: 0,
        })
    }
}
