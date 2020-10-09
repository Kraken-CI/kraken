import { Component, OnInit } from '@angular/core';
import { Title } from '@angular/platform-browser'

import { BreadcrumbsService } from '../breadcrumbs.service'
import { ManagementService } from '../backend/api/management.service'

@Component({
  selector: 'app-diags-page',
  templateUrl: './diags-page.component.html',
  styleUrls: ['./diags-page.component.sass']
})
export class DiagsPageComponent implements OnInit {

    data = {}

    constructor(
        protected breadcrumbService: BreadcrumbsService,
        protected managementService: ManagementService,
        private titleService: Title
    ) { }

    ngOnInit() {
        this.titleService.setTitle('Kraken - Diagnostics')

        this.breadcrumbService.setCrumbs([
            {
                label: 'Home',
            },
            {
                label: 'Diagnostics',
            },
        ])

        this.managementService.getDiagnostics().subscribe(
            data => {
                this.data = data
            }
        )
  }

}
