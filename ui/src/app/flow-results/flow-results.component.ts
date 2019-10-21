import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {TreeNode} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';

@Component({
  selector: 'app-flow-results',
  templateUrl: './flow-results.component.html',
  styleUrls: ['./flow-results.component.sass']
})
export class FlowResultsComponent implements OnInit {

    flowId = 0;
    flow = null;
    runs: any[];
    runsTree: TreeNode[];

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
        this.flowId = parseInt(this.route.snapshot.paramMap.get("id"));

        this.runsTree = [{
            label: `Flow [${this.flowId}]`,
            expanded: true,
            'type': 'root',
            data: {created: ''},
            children: []
        }];

        this.executionService.getFlow(this.flowId).subscribe(flow => {
            this.flow = flow;
            this.runsTree[0].data = flow;
            let crumbs = [{
                label: 'Projects',
                url: '/projects/' + flow.project_id,
                id: flow.project_name
            }, {
                label: 'Branches',
                url: '/branches/' + flow.branch_id,
                id: flow.branch_name
            }, {
                label: 'Flows',
                url: '/flows/' + flow.id,
                id: flow.id
            }];
            this.breadcrumbService.setCrumbs(crumbs);

            for (let run of flow.runs) {
                if (run.parent) {
                    // TODO
                } else {
                    this.runsTree[0].children.push({
                        label: run.name,
                        data: run
                    });
                }
            }
            console.info(this.runsTree);
        });
    }

}
