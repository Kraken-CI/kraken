import { Component, OnInit } from '@angular/core';
import {ActivatedRoute, NavigationEnd, Router} from '@angular/router';
import {distinctUntilChanged, filter, map, switchMap} from 'rxjs/operators';

import {MenuItem} from 'primeng/api';

import { ManagementService } from '../backend/api/management.service';
import { BreadcrumbsService } from '../breadcrumbs.service';


@Component({
  selector: 'app-breadcrumbs',
  templateUrl: './breadcrumbs.component.html',
  styleUrls: ['./breadcrumbs.component.sass']
})
export class BreadcrumbsComponent implements OnInit {

    breadcrumbs: any
    crumbMenuItems: MenuItem[]
    projects: any[] = []

    constructor(private activatedRoute: ActivatedRoute,
                private router: Router,
                protected managementService: ManagementService,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
        this.breadcrumbs = this.breadcrumbService.getCrumbs();

        this.managementService.getProjects().subscribe(data => {
            this.projects = data.items
        })
    }

    showCrumbMenu(event, crumbMenu, breadcrumb) {
        if (breadcrumb.label === 'Projects') {
            this.crumbMenuItems = this.projects.map(p => {
                return {label: p.name, routerLink: '/projects/' + p.id}
            })
        } else {
            this.crumbMenuItems = breadcrumb.items
        }
        crumbMenu.toggle(event)
    }
}
