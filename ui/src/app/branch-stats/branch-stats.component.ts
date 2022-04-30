import { Component, OnInit, OnDestroy, Input } from '@angular/core'

import { Subscription } from 'rxjs'

import { MessageService } from 'primeng/api'

import { ManagementService } from '../backend/api/management.service'

@Component({
    selector: 'app-branch-stats',
    templateUrl: './branch-stats.component.html',
    styleUrls: ['./branch-stats.component.sass'],
})
export class BranchStatsComponent implements OnInit, OnDestroy {
    @Input() branch_id: number

    stats: any = null

    valueData = { ci: {}, dev: {} }
    valueOptions = {}

    private subs: Subscription = new Subscription()

    constructor(
        protected managementService: ManagementService,
        private msgSrv: MessageService
    ) {}

    ngOnInit(): void {
        this.subs.add(
            this.managementService
                .getBranchStats(this.branch_id)
                .subscribe((data) => {
                    console.info('STATS', data)
                    this.stats = data

                    for (const kind of ['ci', 'dev']) {
                        let flowLabels = []
                        let durValues = []

                        for (const f of data[kind].durations) {
                            flowLabels.push(f.flow_label)
                            durValues.push(f.duration)
                        }

                        this.valueData[kind] = {
                            labels: flowLabels,
                            datasets: [
                                {
                                    label: 'Duration',
                                    yAxisID: 'y',
                                    data: durValues,
                                    //fill: false,
                                    borderColor: '#0f0',
                                    backgroundColor: '#0f0',
                                    borderWidth: 5,
                                },
                            ],
                        }
                    }
                })
        )

        this.valueOptions = {
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
                        text: 'Duration [s]',
                    },
                    position: 'left',
                },
            },
        }
    }

    ngOnDestroy() {
        this.subs.unsubscribe()
    }
}
