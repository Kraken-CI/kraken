import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute, ParamMap } from '@angular/router'
import { Title } from '@angular/platform-browser'

import { MenuItem } from 'primeng/api'

import 'chartjs-plugin-error-bars'

import { ExecutionService } from '../backend/api/execution.service'
import { BreadcrumbsService } from '../breadcrumbs.service'
import { TestCaseResults } from '../test-case-results'

@Component({
    selector: 'app-test-case-result',
    templateUrl: './test-case-result.component.html',
    styleUrls: ['./test-case-result.component.sass'],
})
export class TestCaseResultComponent implements OnInit {
    tcrId = 0
    result = null
    results: any[]
    totalRecords = 0
    loading = false

    // charts
    statusData = {}
    statusOptions = {}
    valueNames: any[]
    selectedValue: any
    valueData: any
    valueOptions = {}
    chartPlugins: any[]
    iterations = 1

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        protected executionService: ExecutionService,
        protected breadcrumbService: BreadcrumbsService,
        private titleService: Title
    ) {}

    ngOnInit() {
        this.valueData = {}

        this.tcrId = parseInt(this.route.snapshot.paramMap.get('id'), 10)
        this.breadcrumbService.setCrumbs([
            {
                label: 'Result',
                tcr_id: this.tcrId,
                tc_name: this.tcrId,
            },
        ])


        this.executionService.getResult(this.tcrId).subscribe(result => {
            this.result = result
            const crumbs = [
                {
                    label: 'Projects',
                    project_id: this.result.project_id,
                    project_name: this.result.project_name,
                },
                {
                    label: 'Branches',
                    branch_id: this.result.branch_id,
                    branch_name: this.result.branch_name,
                },
                {
                    label: 'Results',
                    branch_id: this.result.branch_id,
                    flow_kind: this.result.flow_kind,
                },
                {
                    label: 'Flows',
                    flow_id: this.result.flow_id,
                },
                {
                    label: 'Stages',
                    run_id: this.result.run_id,
                    run_name: this.result.stage_name,
                },
                {
                    label: 'Result',
                    tcr_id: this.result.id,
                    tc_name: this.result.test_case_name,
                },
            ]
            this.breadcrumbService.setCrumbs(crumbs)

            this.titleService.setTitle('Kraken - Test ' + this.result.test_case_name + ' ' + this.tcrId)

            const valueNames = []
            if (result.values) {
                for (const name of Object.keys(result.values)) {
                    valueNames.push({ name })
                }
            }
            this.valueNames = valueNames
            this.selectedValue = valueNames[0]
        })

        this.statusOptions = {
            elements: {
                rectangle: {
                    backgroundColor: this.statusColors,
                },
            },
            tooltips: {
                mode: 'index',
                callbacks: {
                    title(tooltipItems, data) {
                        const res =
                            data.datasets[0].origData[tooltipItems[0].index]
                        return TestCaseResults.resultToTxt(res)
                    },
                },
                footerFontStyle: 'normal',
            },
        }
    }

    statusColors(ctx) {
        const res = ctx.dataset.origData[ctx.dataIndex]
        return TestCaseResults.resultColor(res)
    }

    resultToChartVal(res) {
        const resultMapping = {
            0: 0, // 'Not run',
            1: 5, // 'Passed',
            2: 2, // 'Failed',
            3: 1, // 'ERROR',
            4: 3, // 'Disabled',
            5: 4, // 'Unsupported',
        }
        return resultMapping[res]
    }

    prepareValueChartData() {
        if (this.results[0].values === null) {
            // no perf data, skip processing
            return
        }

        const lastRes = this.results[0]
        this.iterations = 1
        for (const res of this.results) {
            if (res.values) {
                this.iterations = res.values[this.selectedValue.name].iterations
                break
            }
        }

        const flowIds = []
        const values = []
        const median = []
        const errorBars = {}
        let errorBarsOk = true
        let minVal = 0
        let maxVal = null
        for (const res of this.results.slice().reverse()) {
            if (!res.values) {
                continue
            }
            const val = res.values[this.selectedValue.name]
            if (val === undefined || val.value === undefined) {
                continue
            }
            flowIds.push(res.flow_id)
            values.push(val.value)
            if (val.median) {
                median.push(val.median)
            }
            if (val.stddev !== undefined) {
                errorBars[res.flow_id] = {
                    plus: val.stddev,
                    minus: -val.stddev,
                }

                let v = val.value - val.stddev
                if (minVal > v) {
                    minVal = v
                }
                v = val.value + val.stddev
                if (maxVal == null || maxVal < v) {
                    maxVal = v
                }
            } else {
                errorBarsOk = false
            }
        }

        const valueData = {
            labels: flowIds,
            datasets: [
                {
                    label: this.selectedValue.name,
                    data: values,
                    fill: false,
                    borderColor: '#f00',
                    backgroundColor: '#f00',
                    lineTension: 0,
                    borderWidth: 2,
                    errorBars: null,
                },
            ],
        }
        if (errorBarsOk) {
            valueData.datasets[0].errorBars = errorBars
        }
        if (median.length > 0) {
            valueData.datasets.push({
                label: 'median',
                data: median,
                fill: false,
                borderColor: '#f88',
                backgroundColor: '#f88',
                lineTension: 0,
                borderWidth: 1,
                errorBars: null,
            })
        }
        if (errorBarsOk) {
            valueData.datasets[1].errorBars = {}
        }
        this.valueData = valueData

        this.valueOptions = {
            scales: {
                yAxes: [
                    {
                        ticks: {
                            suggestedMin: minVal,
                            suggestedMax: maxVal,
                        },
                    },
                ],
            },
        }
    }

    loadResultsLazy(event) {
        this.executionService
            .getResultHistory(this.tcrId, event.first, event.rows)
            .subscribe(data => {
                this.results = data.items
                this.totalRecords = data.total

                const flowIds = []
                const statuses = []
                const origStatuses = []
                for (const res of this.results.slice().reverse()) {
                    flowIds.push(res.flow_id)
                    statuses.push(this.resultToChartVal(res.result))
                    // statuses.push(TestCaseResults.resultToTxt(res.result));
                    origStatuses.push(res.result)
                }

                this.statusData = {
                    labels: flowIds,
                    // yLabels: ['Not run', 'ERROR', 'Failed', 'Disabled', 'Unsupported', 'Passed'],
                    datasets: [
                        {
                            label: 'Status',
                            data: statuses,
                            origData: origStatuses,
                        },
                    ],
                }

                this.prepareValueChartData()
            })
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

    changeToTxt(change) {
        if (change === 0) {
            return ''
        } else if (change === 1) {
            return 'fix'
        } else {
            return 'regression'
        }
    }

    changeToClass(change) {
        return 'change' + change
    }

    handleTabChange(event) {
        console.info(event)
    }

    valueChange() {
        this.prepareValueChartData()
    }

    showCmdLine() {}
}
