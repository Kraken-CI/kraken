import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';
import { Observable } from 'rxjs';
import { switchMap } from 'rxjs/operators';

import {TableModule} from 'primeng/table';

import { ExecutionService } from '../backend/api/execution.service';


@Component({
  selector: 'app-run-results',
  templateUrl: './run-results.component.html',
  styleUrls: ['./run-results.component.sass']
})
export class RunResultsComponent implements OnInit {

    results: any[];

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService) { }

    ngOnInit() {
        this.results = [];
        this.refresh();
    }

    refresh() {
        this.route.paramMap.pipe(
            switchMap((params: ParamMap) =>
                      this.executionService.getRunResults(parseInt(params.get('id'))))
        ).subscribe(data => {
            console.info(data);
            this.results = data;
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
}
