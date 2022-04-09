import { Component, OnInit, OnDestroy, Input } from '@angular/core'

import { Subscription } from 'rxjs'

import { ResultsService } from '../backend/api/results.service'

interface Dim {
    name: string
    code: string
}

@Component({
    selector: 'app-flow-analysis',
    templateUrl: './flow-analysis.component.html',
    styleUrls: ['./flow-analysis.component.sass'],
})
export class FlowAnalysisComponent implements OnInit, OnDestroy {
    @Input() flow: any

    data: any = {}
    recsMap: any = {}
    totalTests: number = 0

    dims: Dim[]
    dim1: Dim
    dim2: Dim
    dim3: Dim

    stats: any = {}
    statsCols: any

    private subs: Subscription = new Subscription()

    constructor(protected resultsService: ResultsService) {
        this.dims = [
            // stage -> group -> system -> config -> component
            { name: 'None', code: 'NN' },
            { name: 'Stage', code: 'ST' },
            { name: 'Agents Group', code: 'AG' },
            { name: 'System', code: 'SY' },
            // {name: 'Config', code: 'CG'},
            // {name: 'Component', code: 'CT'}
        ]
        this.dim1 = this.dims[1] // stages
        this.dim2 = this.dims[3] // systems
        this.dim3 = this.dims[2] // groups
    }

    ngOnInit(): void {
        this.subs.add(
            this.resultsService
                .getFlowAnalysis(this.flow.id)
                .subscribe((data) => {
                    this.data = data.stats
                    this.recsMap = data.recs_map
                    this.totalTests = data.total_tests
                    this.calculateStats()
                })
        )
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }

    calculateStats() {
        if (this.dim1.code === 'NN') {
            this.stats = { passed: 0, total: 0 }

            // stage -> group -> system -> config -> component
            for (const [stageName, groups] of Object.entries(this.data)) {
                for (const [groupName, systems] of Object.entries(groups)) {
                    for (const [systemName, results] of Object.entries(
                        systems
                    )) {
                        this.stats.passed += results['Passed']
                        this.stats.total += results['total']
                    }
                }
            }
        } else if (this.dim2.code === 'NN') {
            this.stats = {}

            // stage -> group -> system -> config -> component
            let key = ''
            for (const [stageName, groups] of Object.entries(this.data)) {
                for (const [groupName, systems] of Object.entries(groups)) {
                    for (const [systemName, results] of Object.entries(
                        systems
                    )) {
                        if (this.dim1.code === 'ST') {
                            key = stageName
                        } else if (this.dim1.code === 'AG') {
                            key = groupName
                        } else if (this.dim1.code === 'SY') {
                            key = systemName
                        }
                        if (!this.stats[key]) {
                            this.stats[key] = { passed: 0, total: 0 }
                        }
                        this.stats[key].passed += results['Passed']
                        this.stats[key].total += results['total']
                    }
                }
            }
        } else if (this.dim3.code === 'NN') {
            this.stats = {}
            let statsCols = {}

            // stage -> group -> system -> config -> component
            let key1 = ''
            let key2 = ''
            for (const [stageName, groups] of Object.entries(this.data)) {
                for (const [groupName, systems] of Object.entries(groups)) {
                    for (const [systemName, results] of Object.entries(
                        systems
                    )) {
                        if (this.dim1.code === 'ST') {
                            key1 = stageName
                        } else if (this.dim1.code === 'AG') {
                            key1 = groupName
                        } else if (this.dim1.code === 'SY') {
                            key1 = systemName
                        }
                        if (this.dim2.code === 'ST') {
                            key2 = stageName
                        } else if (this.dim2.code === 'AG') {
                            key2 = groupName
                        } else if (this.dim2.code === 'SY') {
                            key2 = systemName
                        }

                        statsCols[key1] = true

                        if (!this.stats[key2]) {
                            this.stats[key2] = {}
                        }
                        if (!this.stats[key2][key1]) {
                            this.stats[key2][key1] = { passed: 0, total: 0 }
                        }
                        this.stats[key2][key1].passed += results['Passed']
                        this.stats[key2][key1].total += results['total']
                    }
                }
            }

            this.statsCols = Object.keys(statsCols)
            this.statsCols.sort()
        } else {
            this.stats = {}
            let statsCols = {}

            // stage -> group -> system -> config -> component
            let key1 = ''
            let key2 = ''
            let key3 = ''
            for (const [stageName, groups] of Object.entries(this.data)) {
                for (const [groupName, systems] of Object.entries(groups)) {
                    for (const [systemName, results] of Object.entries(
                        systems
                    )) {
                        const runQueryParams = {
                            system: this.recsMap.systems[systemName],
                            group: this.recsMap.groups[groupName],
                        }

                        if (this.dim1.code === 'ST') {
                            key1 = stageName
                        } else if (this.dim1.code === 'AG') {
                            key1 = groupName
                        } else if (this.dim1.code === 'SY') {
                            key1 = systemName
                        }
                        if (this.dim2.code === 'ST') {
                            key2 = stageName
                        } else if (this.dim2.code === 'AG') {
                            key2 = groupName
                        } else if (this.dim2.code === 'SY') {
                            key2 = systemName
                        }
                        if (this.dim3.code === 'ST') {
                            key3 = stageName
                        } else if (this.dim3.code === 'AG') {
                            key3 = groupName
                        } else if (this.dim3.code === 'SY') {
                            key3 = systemName
                        }

                        if (!statsCols[key1]) {
                            statsCols[key1] = {}
                        }
                        statsCols[key1][key2] = true

                        if (!this.stats[key3]) {
                            this.stats[key3] = {}
                        }
                        if (!this.stats[key3][key1]) {
                            this.stats[key3][key1] = {}
                        }
                        if (!this.stats[key3][key1][key2]) {
                            const runRouterLink =
                                '/runs/' + groups['run_id'] + '/results'
                            this.stats[key3][key1][key2] = {
                                passed: 0,
                                total: 0,
                                runRouterLink: runRouterLink,
                                runQueryParams: runQueryParams,
                            }
                        }
                        this.stats[key3][key1][key2].passed += results['Passed']
                        this.stats[key3][key1][key2].total += results['total']
                    }
                }
            }

            this.statsCols = statsCols
        }
    }

    getPassRatio(passed, total) {
        const ratio = (100 * passed) / total
        return ratio.toFixed(1) + ' %'
    }

    getBgColor(stat) {
        if (!stat) {
            return '#fff'
        }
        if (stat.total === stat.passed) {
            return 'var(--greenish1)'
        } else if (stat.passed > 0.5 * stat.total) {
            return 'var(--orangish1)'
        }
        return 'var(--redish1)'
    }

    getBgColor2(stat, key1, key2) {
        if (!stat[key1]) {
            return '#fff'
        }
        return this.getBgColor(stat[key1][key2])
    }

    getLen(obj) {
        return Object.keys(obj).length
    }

    randomizeLayout() {
        let dims2 = [...this.dims]
        dims2.sort(() => 0.5 - Math.random())
        this.dim1 = dims2[0]
        this.dim2 = dims2[1]
        this.dim3 = dims2[2]
        this.calculateStats()
    }
}
