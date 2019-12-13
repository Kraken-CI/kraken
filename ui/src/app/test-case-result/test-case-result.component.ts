import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {MenuItem} from 'primeng/api';

import 'chartjs-plugin-error-bars';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { TestCaseResults } from '../test-case-results';


@Component({
  selector: 'app-test-case-result',
  templateUrl: './test-case-result.component.html',
  styleUrls: ['./test-case-result.component.sass']
})
export class TestCaseResultComponent implements OnInit {

    tcrId = 0;
    result = null;
    results: any[];
    totalRecords = 0;
    loading = false;

    // charts
    statusData = {};
    statusOptions = {};
    valueNames: any[];
    selectedValue: any;
    valueData: any
    valueOptions = {};
    chartPlugins: any[];

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
        this.valueData = {}

        this.tcrId = parseInt(this.route.snapshot.paramMap.get("id"));
        this.breadcrumbService.setCrumbs([{
            label: 'Result',
            url: '/test_case_result/' + this.tcrId,
            id: this.tcrId
        }]);

        this.executionService.getResult(this.tcrId).subscribe(result => {
            this.result = result;
            let crumbs = [{
                label: 'Projects',
                url: '/projects/' + this.result.project_id,
                id: this.result.project_name
            }, {
                label: 'Branches',
                url: '/branches/' + this.result.branch_id,
                id: this.result.branch_name
            }, {
                label: 'Flows',
                url: '/flows/' + this.result.flow_id,
                id: this.result.flow_id
            }, {
                label: 'Stages',
                url: '/runs/' + this.result.run_id,
                id: this.result.stage_name
            }, {
                label: 'Results',
                url: '/test_case_result/' + this.result.id,
                id: this.result.test_case_name
            }];
            this.breadcrumbService.setCrumbs(crumbs);

            let valueNames = [];
            for (let name in result.values) {
                valueNames.push({name: name});
            }
            this.valueNames = valueNames;
            this.selectedValue = valueNames[0];
        });

        this.statusOptions = {
            elements: {
		rectangle: {
		    backgroundColor: this.statusColors
		}
	    },
            tooltips: {
		mode: 'index',
		callbacks: {
		    title: function(tooltipItems, data) {
                        let res = data.datasets[0].origData[tooltipItems[0].index];
                        return TestCaseResults.resultToTxt(res);
		    },
		},
		footerFontStyle: 'normal'
	    }
        };
    }

    statusColors(ctx) {
        let res = ctx.dataset.origData[ctx.dataIndex];
        return TestCaseResults.resultColor(res);
    }

    resultToChartVal(res) {
        var resultMapping = {
            0: 0, // 'Not run',
            1: 5, // 'Passed',
            2: 2, // 'Failed',
            3: 1, // 'ERROR',
            4: 3, // 'Disabled',
            5: 4, // 'Unsupported',
        };
        return resultMapping[res];
    }

    prepareValueChartData() {
        if (this.results[0].values === null) {
            // no perf data, skip processing
            return
        }
        let flowIds = [];
        let values = [];
        let median = [];
        let errorBars = {};
        let minVal = 0;
        let maxVal = null;
        for (let res of this.results.slice().reverse()) {
            flowIds.push(res.flow_id);
            let val = res.values[this.selectedValue.name]
            values.push(val.value);
            if (val.median) {
                median.push(val.median);
            }
            errorBars[res.flow_id] = {plus: val.stddev, minus: -val.stddev};

            let v = val.value - val.stddev;
            if (minVal > v) {
                minVal = v;
            }
            v = val.value + val.stddev;
            if (maxVal == null || maxVal < v) {
                maxVal = v;
            }
        }

        let valueData = {
            labels: flowIds,
            datasets: [{
                label: this.selectedValue.name,
                data: values,
                fill: false,
		borderColor: '#f00',
		backgroundColor: '#f00',
                lineTension: 0,
                errorBars: errorBars,
                borderWidth: 2
            }]
        };
        if (median.length > 0) {
            valueData.datasets.push({
                label: 'median',
                data: median,
                fill: false,
		borderColor: '#f88',
		backgroundColor: '#f88',
                lineTension: 0,
                errorBars: {},
                borderWidth: 1
            });
        }
        this.valueData = valueData;

        this.valueOptions = {
            scales: {
                yAxes: [{
                    ticks: {
                        suggestedMin: minVal,
                        suggestedMax: maxVal
                    }
                }]
            }
        };

    }

    loadResultsLazy(event) {
        this.executionService.getResultHistory(this.tcrId, event.first, event.rows).subscribe(data => {
            this.results = data.items;
            this.totalRecords = data.total;

            let flowIds = [];
            let statuses = [];
            let origStatuses = [];
            for (let res of this.results.slice().reverse()) {
                flowIds.push(res.flow_id);
                statuses.push(this.resultToChartVal(res.result));
                //statuses.push(TestCaseResults.resultToTxt(res.result));
                origStatuses.push(res.result);
            }

            this.statusData = {
                labels: flowIds,
                //yLabels: ['Not run', 'ERROR', 'Failed', 'Disabled', 'Unsupported', 'Passed'],
                datasets: [{
                    label: 'Status',
                    data: statuses,
                    origData: origStatuses
                }]
            };

            this.prepareValueChartData();
        });
    }

    formatResult(result) {
        return TestCaseResults.formatResult(result);
    }

    resultToTxt(result) {
        return TestCaseResults.resultToTxt(result);
    }

    resultToClass(result) {
        return 'result' + result;
    }

    changeToTxt(change) {
        if (change == 0) {
            return "";
        } else if (change == 1) {
            return "fix";
        } else {
            return "regression";
        }
    }

    changeToClass(change) {
        return "change" + change;
    }

    handleTabChange(event) {
        console.info(event);
    }

    valueChange() {
        this.prepareValueChartData();
    }

    showCmdLine() {
    }
}
