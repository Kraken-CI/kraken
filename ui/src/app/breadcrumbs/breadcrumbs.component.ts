import { Component, OnInit } from '@angular/core';

import {ActivatedRoute, NavigationEnd, Router} from '@angular/router';
import {distinctUntilChanged, filter, map, switchMap} from 'rxjs/operators';

import { BreadcrumbsService } from '../breadcrumbs.service';


@Component({
  selector: 'app-breadcrumbs',
  templateUrl: './breadcrumbs.component.html',
  styleUrls: ['./breadcrumbs.component.sass']
})
export class BreadcrumbsComponent implements OnInit {

    breadcrumbs: any;

    constructor(private activatedRoute: ActivatedRoute,
                private router: Router,
                protected breadcrumbService: BreadcrumbsService) { }

    ngOnInit() {
        this.breadcrumbs = this.breadcrumbService.getCrumbs();
    }
}
