import {
    Component,
    OnInit,
    OnDestroy,
    Input,
    AfterViewInit,
    ElementRef,
    ViewChild,
    ViewChildren,
    QueryList,
} from '@angular/core'

import { ExecutionService } from '../backend/api/execution.service'

@Component({
    selector: 'app-log-box',
    templateUrl: './log-box.component.html',
    styleUrls: ['./log-box.component.sass'],
})
export class LogBoxComponent implements OnInit, OnDestroy, AfterViewInit {
    @ViewChild('logBox', { static: false }) logBox: ElementRef
    @ViewChildren('logFrag') logFrags: QueryList<any>
    logBoxEl: any
    isNearBottom = true

    logFragments: any[]
    skippedAngLoadedLogs = 0
    lastAttempts = 0
    fontSize = 1.0

    timer1 = null
    timer2 = null
    timer3 = null

    prvJobId: number
    @Input()
    set jobId(id) {
        this.prvJobId = id

        if (id !== 0) {
            this.loadJobLogs(id)
        }
    }
    get jobId() {
        return this.prvJobId
    }

    constructor(protected executionService: ExecutionService) {}

    ngOnInit() {}

    _prepareLogs(logs, job) {
        let fragment
        if (this.logFragments.length > 0) {
            // remove last entry with ... running ...
            if (this.logFragments[this.logFragments.length - 1].loading) {
                this.logFragments.splice(this.logFragments.length - 1, 1)
            }
            // get last fragment
            fragment = this.logFragments[this.logFragments.length - 1]
        }
        for (const l of logs) {
            if (fragment === undefined) {
                let title = ''
                if (l.step !== undefined) {
                    title = l.tool
                }
                fragment = {
                    title,
                    step: l.step,
                    expanded: true,
                    logs: [],
                }
                this.logFragments.push(fragment)
            } else {
                if (l.step !== fragment.step) {
                    console.info(l)
                    this._addStepStatusEntryToLogs(job, fragment.step)
                    let title = ''
                    if (l.step !== undefined) {
                        title = l.tool
                    }
                    fragment = {
                        title,
                        step: l.step,
                        expanded: true,
                        logs: [],
                    }
                    this.logFragments.push(fragment)
                }
            }
            if (fragment.title === '' && l.tool !== '') {
                fragment.title = l.tool
            }
            l.cls = ''
            if (l.level === 'ERROR') {
                l.cls = 'log-red'
            }
            if (l.message.includes('ERRO')) {
                for (const line of l.message.match(/[^\r\n]+/g)) {
                    const l2 = { message: line, cls: l.cls }
                    if (line.includes('ERRO')) {
                        l2.cls = 'log-red'
                    }
                    fragment.logs.push(l2)
                }
            } else {
                fragment.logs.push(l)
            }
        }
    }

    _addLoadingMoreEntryToLogs() {
        this.logFragments.push({
            title: '',
            expanded: true,
            loading: true,
            logs: [
                {
                    message: '... running ...',
                    cls: 'log-blue',
                },
            ],
        })
    }

    _addStepStatusEntryToLogs(job, stepIdx) {
        if (
            this.logFragments.length > 0 &&
            this.logFragments[this.logFragments.length - 1].stepStatus
        ) {
            // if last frag is already step status then do not add another one
            return
        }
        let msg = ''
        let cls = ''
        for (const step of job.steps) {
            if (step.index === stepIdx) {
                if (step.status === 2) {
                    msg = 'Step succeeded'
                    cls = 'log-green'
                } else if (step.status === 3) {
                    msg = 'Step error'
                    cls = 'log-red'
                }
            }
        }
        if (msg) {
            this.logFragments.push({
                title: '',
                expanded: true,
                stepStatus: true,
                logs: [
                    {
                        message: msg,
                        cls,
                    },
                ],
            })
        }
    }

    _processNewLogs(data, skippedLogsCount) {
        // console.info('process new logs', data)
        if (skippedLogsCount > 0) {
            this.logFragments.push({
                title: '',
                expanded: true,
                logs: [
                    {
                        message:
                            '... skipped ' + skippedLogsCount + ' lines ...',
                        cls: '',
                    },
                ],
            })
        }
        this._prepareLogs(data.items.reverse(), data.job)

        if (data.job.state !== 5 && this.lastAttempts < 4) {
            // completed
            this._addLoadingMoreEntryToLogs()
        }
    }

    _processNextLogs(jobId, data) {
        if (jobId !== this.prvJobId) {
            // console.info('!!!! job switch - stop processing in processNextLogs', jobId)
            return
        }
        // console.info('loaded next ' + data.items.length + ' of ' + data.total, jobId)
        this.skippedAngLoadedLogs += data.items.length

        if (data.items.length === 0) {
            if (data.job.state === 5 && this.lastAttempts === 4) {
                // console.info('completed loading', jobId)
                this._addStepStatusEntryToLogs(
                    data.job,
                    data.job.steps.length - 1
                )
            } else {
                if (data.job.state === 5) {
                    this.lastAttempts += 1
                }
                // nothing loaded but still running then wait 3 seconds and then load more
                // console.info('nothing loaded but still running then wait 3 seconds and then load more', jobId)
                this.timer2 = setTimeout(() => {
                    // console.info('timer2 fired ', jobId, this.timer2)
                    this.timer2 = null
                    if (jobId !== this.prvJobId) {
                        // console.info('!!!! job switch - stop processing in timer2 ', jobId, this.timer2)
                        return
                    }
                    this.executionService
                        .getJobLogs(
                            jobId,
                            this.skippedAngLoadedLogs,
                            200,
                            'asc'
                        )
                        .subscribe(data2 => {
                            this._processNextLogs(jobId, data2)
                        })
                }, 3000)
                return
            }
        }

        this._prepareLogs(data.items, data.job)

        if (this.skippedAngLoadedLogs < data.total) {
            // load the rest immediatelly
            let num = data.total - this.skippedAngLoadedLogs
            if (num > 1000) {
                num = 1000
            }
            // console.info('load the rest ' + num + ' immediatelly', jobId)
            this.executionService
                .getJobLogs(jobId, this.skippedAngLoadedLogs, num, 'asc')
                .subscribe(data2 => {
                    this._processNextLogs(jobId, data2)
                })
        } else if (data.job.state !== 5 || this.lastAttempts < 4) {
            if (data.job.state === 5) {
                this.lastAttempts += 1
            }
            this._addLoadingMoreEntryToLogs()
            // wait for next logs 3 seconds
            // console.info('wait for next logs 3 seconds', jobId)
            this.timer3 = setTimeout(() => {
                // console.info('timer3 fired ', jobId, this.timer3)
                this.timer3 = null
                if (jobId !== this.prvJobId) {
                    // console.info('!!!! job switch - stop processing in timer3 ', jobId, this.timer3)
                    return
                }
                this.executionService
                    .getJobLogs(jobId, this.skippedAngLoadedLogs, 200, 'asc')
                    .subscribe(data2 => {
                        this._processNextLogs(jobId, data2)
                    })
            }, 3000)
            return
        } else {
            // console.info('completed loading at next shot', jobId)
            this._addStepStatusEntryToLogs(data.job, data.job.steps.length - 1)
        }
    }

    loadJobLogs(jobId) {
        // console.info('loading logs for ', jobId)

        if (this.timer1 !== null) {
            // console.info('!!!! canceled timer1 ', jobId, this.timer1)
            clearTimeout(this.timer1)
            this.timer1 = null
        }
        if (this.timer2 !== null) {
            // console.info('!!!! canceled timer2 ', jobId, this.timer2)
            clearTimeout(this.timer2)
            this.timer2 = null
        }
        if (this.timer3 !== null) {
            // console.info('!!!! canceled timer3 ', jobId, this.timer3)
            clearTimeout(this.timer3)
            this.timer3 = null
        }

        this.logFragments = []
        this.executionService
            .getJobLogs(jobId, 0, 200, 'desc')
            .subscribe(data => {
                if (jobId !== this.prvJobId) {
                    // console.info('!!!! job switch - stop processing getJobLogs', jobId)
                    return
                }
                // console.info('loaded first ' + data.items.length + ' of ' + data.total, jobId)
                this.skippedAngLoadedLogs = data.total

                this._processNewLogs(data, data.total - 200)

                if (data.job.state !== 5 || this.lastAttempts < 4) {
                    // completed
                    if (data.job.state === 5) {
                        this.lastAttempts += 1
                    }
                    // wait for next logs 3 seconds
                    // console.info('waiting for next logs 3 seconds ', jobId)
                    this.timer1 = setTimeout(() => {
                        // console.info('timer1 fired ', jobId, this.timer1)
                        this.timer1 = null
                        if (jobId !== this.prvJobId) {
                            // console.info('!!!! job switch - stop processing in timer1 ', jobId, this.timer1)
                            return
                        }
                        this.executionService
                            .getJobLogs(
                                jobId,
                                this.skippedAngLoadedLogs,
                                200,
                                'asc'
                            )
                            .subscribe(data2 => {
                                this._processNextLogs(jobId, data2)
                            })
                    }, 3000)
                } else {
                    // console.info('completed loading at first shot', jobId)
                    this._addStepStatusEntryToLogs(
                        data.job,
                        data.job.steps.length - 1
                    )
                }
            })
    }

    ngAfterViewInit() {
        this.logBoxEl = this.logBox.nativeElement
        this.logFrags.changes.subscribe(_ => this.onLogFragsChanged())
    }

    ngOnDestroy() {
        if (this.timer1 !== null) {
            // console.info('!!!! canceled timer1 on destroy ', this.timer1)
            clearTimeout(this.timer1)
            this.timer1 = null
        }
        if (this.timer2 !== null) {
            // console.info('!!!! canceled timer2 on destroy ', this.timer2)
            clearTimeout(this.timer2)
            this.timer2 = null
        }
        if (this.timer3 !== null) {
            // console.info('!!!! canceled timer3 on destroy ', this.timer3)
            clearTimeout(this.timer3)
            this.timer3 = null
        }
    }

    onLogFragsChanged() {
        if (this.isNearBottom) {
            this.scrollToBottom()
        }
    }

    scrollToBottom() {
        this.logBoxEl.scroll({
            top: this.logBoxEl.scrollHeight,
            left: 0,
        })
    }

    scrollToTop() {
        this.logBoxEl.scroll({
            top: 0,
            left: 0,
        })
    }

    isScrollNearBottom(): boolean {
        const threshold = 150
        const position = this.logBoxEl.scrollTop + this.logBoxEl.offsetHeight
        const height = this.logBoxEl.scrollHeight
        return position > height - threshold
    }

    scrolled(event: any): void {
        this.isNearBottom = this.isScrollNearBottom()
    }

    logDownload() {}

    logZoomIn() {
        this.fontSize += 0.05
    }

    logZoomOut() {
        this.fontSize -= 0.05
    }

    logScrollUp() {
        this.scrollToTop()
    }

    logScrollDown() {
        this.scrollToBottom()
    }
}
