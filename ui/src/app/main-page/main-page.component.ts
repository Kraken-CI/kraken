import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute, ParamMap } from '@angular/router';

import {PanelModule} from 'primeng/panel';
import {TreeModule} from 'primeng/tree';
import {TreeNode} from 'primeng/api';

import { ExecutionService } from '../backend/api/execution.service';
import { BreadcrumbsService } from '../breadcrumbs.service';
import { datetimeToLocal } from '../utils';

@Component({
  selector: 'app-main-page',
  templateUrl: './main-page.component.html',
  styleUrls: ['./main-page.component.sass']
})
export class MainPageComponent implements OnInit {

    projects: any[];

    constructor(private route: ActivatedRoute,
                private router: Router,
                protected executionService: ExecutionService,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
        this.breadcrumbService.setCrumbs([{
            label: 'Projects',
            url: '/',
            id: 0
        }]);

        this.refresh();
    }

    refresh() {
        this.executionService.getProjects().subscribe(data => {
            for (let proj of data.items) {
                let branches = []
                for (let b of proj.branches) {
                    let extraText = 'no flows yet';
                    if (b.flows.length > 0) {
                        extraText = 'last flow: ' + datetimeToLocal(b.flows[0].created);
                    }
                    let br = {
                        label: b.name,
                        extraText: extraText,
                        branchId: b.id,
                        'type': 'branch',
                        icon: "fa fa-code-fork",
                        children: []
                    };
                    for (let f of b.flows) {
                        br.children.push({
                            label: '' + f.id + '. ' + datetimeToLocal(f.created) + ', stages:' + f.runs.length,
                            icon: 'fa fa-th-list',
                        });
                    }
                    branches.push(br);
                }
                proj.branches = branches;
            }
            this.projects = data.items;
        });
    }
}
