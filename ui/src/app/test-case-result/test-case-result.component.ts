import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {TableModule} from 'primeng/table';

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

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
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
        });
    }

    loadResultsLazy(event) {

        this.executionService.getResultHistory(this.tcrId, event.first, event.rows).subscribe(data => {
            this.results = data.items;
            this.totalRecords = data.total;
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
}
