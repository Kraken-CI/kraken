import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';
import { Observable, BehaviorSubject } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import {TableModule} from 'primeng/table';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';


@Component({
  selector: 'app-run-results',
  templateUrl: './run-results.component.html',
  styleUrls: ['./run-results.component.sass']
})
export class RunResultsComponent implements OnInit {

    runId = 0;
    results: any[];
    totalRecords = 0;
    loading = false;

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
        this.runId = parseInt(this.route.snapshot.paramMap.get("id"));
        this.breadcrumbService.setCrumbs([{
            label: 'Stages',
            url: '/runs/' + this.runId,
            id: this.runId
        }]);
        this.results = [];
        this.executionService.getRun(this.runId).subscribe(run => {
            let crumbs = [{
                label: 'Projects',
                url: '/projects/' + run.project_id,
                id: run.project_name
            }, {
                label: 'Branches',
                url: '/branches/' + run.branch_id,
                id: run.branch_name
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
        var resultMapping = {
            0: {style: 'color: #FF8800;', txt: 'Not run'},
            1: {style: 'color: #008800;', txt: 'Passed'},
            2: {style: 'color: #FF2200;', txt: 'Failed'},
            3: {style: 'color: #880000;', txt: 'ERROR'},
            4: {style: 'color: #888888;', txt: 'Disabled'},
            5: {style: 'color: #444444;', txt: 'Unsupported'},
        };

        let val = resultMapping[result]

        return '<span style="' + val.style + '">' + val.txt + '</span>';
    }

    resultToTxt(result) {
        var resultMapping = {
            0: 'Not run',
            1: 'Passed',
            2: 'Failed',
            3: 'ERROR',
            4: 'Disabled',
            5: 'Unsupported',
        };
        return resultMapping[result];
    }

    resultToClass(result) {
        return 'result' + result;
    }

    loadResultsLazy(event) {
        console.info(event);

        this.executionService.getRunResults(this.runId, event.first, event.rows).subscribe(data => {
            this.results = data.items;
            this.totalRecords = data.total;
        });
    }

    showCmdLine() {
    }
}
