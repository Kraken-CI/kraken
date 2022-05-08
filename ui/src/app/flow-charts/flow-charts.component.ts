import { Component, OnInit, OnDestroy, Input } from '@angular/core'

import { Subscription } from 'rxjs'

import { ResultsService } from '../backend/api/results.service'

@Component({
    selector: 'app-flow-charts',
    templateUrl: './flow-charts.component.html',
    styleUrls: ['./flow-charts.component.sass'],
})
export class FlowChartsComponent implements OnInit, OnDestroy {
    @Input() flow: any

    passRatioData: any
    passRatioOptions = {}

    passedTotalData: any
    passedTotalOptions = {}

    private subs: Subscription = new Subscription()

    constructor(protected resultsService: ResultsService) {}

    ngOnInit(): void {
        this.subs.add(
            this.resultsService
                .getBranchHistory(this.flow.id, 30)
                .subscribe((data) => {
                    console.info(data)
                    this.loadDataToChart(data)
                })
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    loadDataToChart(data) {
        const flowLabels = []
        const passRatioValues = []
        const passedValues = []
        const totalValues = []

        for (const f of data.items) {
            flowLabels.push(f.label)
            let passRatio = NaN
            if (f.tests_total && f.tests_total > 0) {
                passRatio = (100 * f.tests_passed) / f.tests_total
            }
            passRatioValues.push(passRatio)
            passedValues.push(f.tests_passed)
            totalValues.push(f.tests_total)
        }

        this.passRatioOptions = {
            // plugins: {
            //     tooltip: {
            //         callbacks: {
            //             title: (tooltipItems) => {
            //                 const idx = tooltipItems[0].dataIndex
            //                 const data = tooltipItems[0].dataset.origData[idx]
            //                 return (
            //                     data.flow_label +
            //                     ' @ ' +''
            //                     //datetimeToLocal(data.flow_created_at, null)
            //                 )
            //             },
            //         },
            //     },
            // },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Flows',
                    },
                },
                y: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Pass ratio [%]',
                    },
                    position: 'left',
                    ticks: {
                        suggestedMin: 0,
                        suggestedMax: 100,
                    },
                },
            },
            plugins: {
                zoom: {
                    zoom: {
                        wheel: {
                            enabled: true,
                        },
                        pinch: {
                            enabled: true,
                        },
                        drag: {
                            enabled: true,
                            borderColor: 'rgb(54, 162, 235)',
                            borderWidth: 1,
                            backgroundColor: 'rgba(54, 162, 235, 0.3)',
                        },
                        mode: 'xy',
                    },
                    pan: {
                        enabled: true,
                        mode: 'xy',
                        modifierKey: 'shift',
                    },
                    limits: {
                        x: { min: 0, max: 'original', minRange: 5 },
                        y: { min: 0, max: 100, minRange: 5 },
                    },
                },
            },
        }
        this.passedTotalOptions = {
            // plugins: {
            //     tooltip: {
            //         callbacks: {
            //             title: (tooltipItems) => {
            //                 const idx = tooltipItems[0].dataIndex
            //                 const data = tooltipItems[0].dataset.origData[idx]
            //                 return (
            //                     data.flow_label +
            //                     ' @ ' +''
            //                     //datetimeToLocal(data.flow_created_at, null)
            //                 )
            //             },
            //         },
            //     },
            // },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Flows',
                    },
                },
                y: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Passed & Total',
                    },
                    position: 'left',
                },
            },
            plugins: {
                zoom: {
                    zoom: {
                        wheel: {
                            enabled: true,
                        },
                        pinch: {
                            enabled: true,
                        },
                        drag: {
                            enabled: true,
                            borderColor: 'rgb(54, 162, 235)',
                            borderWidth: 1,
                            backgroundColor: 'rgba(54, 162, 235, 0.3)',
                        },
                        mode: 'xy',
                    },
                    pan: {
                        enabled: true,
                        mode: 'xy',
                        modifierKey: 'shift',
                    },
                    limits: {
                        x: { min: 0, max: 'original', minRange: 5 },
                        y: { min: 0, max: 'original', minRange: 5 },
                    },
                },
            },
        }

        this.passRatioData = {
            labels: flowLabels,
            datasets: [
                {
                    label: 'Pass ratio',
                    yAxisID: 'y',
                    data: passRatioValues,
                    //fill: false,
                    borderColor: '#0f0',
                    backgroundColor: '#0f0',
                    borderWidth: 5,
                },
            ],
        }

        this.passedTotalData = {
            labels: flowLabels,
            datasets: [
                {
                    label: 'Passed',
                    yAxisID: 'y',
                    data: passedValues,
                    borderColor: '#0a0',
                    backgroundColor: '#0a0',
                },
                {
                    label: 'Total',
                    yAxisID: 'y',
                    data: totalValues,
                    borderColor: '#00f',
                    backgroundColor: '#00f',
                    grid: {
                        drawOnChartArea: false, // only want the grid lines for one axis to show up
                    },
                },
            ],
        }
    }
}
