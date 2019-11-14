import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {MenuItem} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { TestCaseResults } from '../test-case-results';
import { Job } from '../backend/model/models';


@Component({
  selector: 'app-run-results',
  templateUrl: './run-results.component.html',
  styleUrls: ['./run-results.component.sass']
})
export class RunResultsComponent implements OnInit {
    tabs: MenuItem[]
    activeTab: MenuItem

    runId = 0;
    results: any[];
    totalRecords = 0;
    loading = false;

    jobs: Job[]
    totalJobs = 0
    loadingJobs = false

    job: Job
    selectedJobId = 0

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    switchToTab(tabLabel) {
        for (let t of this.tabs) {
            if (t.label.toLowerCase() === tabLabel.toLowerCase() && this.activeTab.label !== t.label) {
                this.activeTab = t
                break
            }
        }
    }

    ngOnInit() {
        this.runId = parseInt(this.route.snapshot.paramMap.get("id"));
        let tab = this.route.snapshot.paramMap.get("tab");

        this.tabs = [
            {label: 'Results', routerLink: '/runs/' + this.runId + '/results'},
            {label: 'Jobs', routerLink: '/runs/' + this.runId + '/jobs'},
        ]
        this.activeTab = this.tabs[0]
        if (tab === 'jobs') {
            this.activeTab = this.tabs[1]
        }

        this.route.paramMap.subscribe(params => {
            let newTab = params.get("tab");
            if (newTab) {
                this.switchToTab(newTab)
            }
        })

        this.breadcrumbService.setCrumbs([{
            label: 'Stages',
            url: '/runs/' + this.runId,
            id: this.runId
        }]);

        this.results = [];
        this.executionService.getRun(this.runId).subscribe(run => {
            if (run.state !== 'completed') {
                this.tabs = [
                    {label: 'Jobs', routerLink: '/runs/' + this.runId + '/jobs'},
                    {label: 'Results', routerLink: '/runs/' + this.runId + '/results'},
                ]
            }
            this.switchToTab(this.activeTab.label)

            let crumbs = [{
                label: 'Projects',
                url: '/projects/' + run.project_id,
                id: run.project_name
            }, {
                label: 'Branches',
                url: '/branches/' + run.branch_id,
                id: run.branch_name
            }, {
                label: 'Results',
                url: '/branches/' + run.branch_id + '/' + run.flow_kind,
                id: run.flow_kind,
                items: [{
                    label: 'CI',
                    routerLink: '/branches/' + run.branch_id + '/ci'
                }, {
                    label: 'dev',
                    routerLink: '/branches/' + run.branch_id + '/dev'
                }]
            }, {
                label: 'Flows',
                url: '/flows/' + run.flow_id,
                id: run.flow_id
            }, {
                label: 'Stages',
                url: '/runs/' + run.id,
                id: run.name
            }];
            this.breadcrumbService.setCrumbs(crumbs);
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

    loadResultsLazy(event) {
        this.executionService.getRunResults(this.runId, event.first, event.rows).subscribe(data => {
            this.results = data.items;
            this.totalRecords = data.total;
        });
    }

    loadJobsLazy(event) {
        this.executionService.getRunJobs(this.runId, event.first, event.rows).subscribe(data => {
            this.jobs = data.items
            this.totalJobs = data.total

            this.job = this.jobs[0]
            this.selectedJobId = this.job.id
        })
    }

    showCmdLine() {
    }

    jobSelected(event) {
        this.selectedJobId = event.data.id
    }
}
