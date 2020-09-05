import { Component, OnInit } from '@angular/core'

import { PanelMenuModule } from 'primeng/panelmenu'
import { MenuModule } from 'primeng/menu'
import { MenuItem } from 'primeng/api'
import { SplitButtonModule } from 'primeng/splitbutton'
import { MultiSelectModule } from 'primeng/multiselect'
import { ToastModule } from 'primeng/toast'

import { environment } from './../environments/environment'

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.sass'],
})
export class AppComponent implements OnInit {
    title = 'Kraken'
    logoClass = 'logo1'
    krakenVersion = '0.4'

    topMenuItems: MenuItem[]

    constructor() {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 9) + 1)
    }

    ngOnInit() {
        this.krakenVersion = environment.krakenVersion

        this.topMenuItems = [
            {
                label: 'Agents',
                icon: 'fa fa-server',
                items: [
                    {
                        label: 'Agents',
                        routerLink: '/agents',
                    },
                    {
                        label: 'Groups',
                        routerLink: '/agents-groups',
                    },
                    {
                        label: 'Discovered',
                        routerLink: '/discovered-agents',
                    },
                ],
            },
            {
                label: 'Settings',
                icon: 'fa fa-wrench',
                routerLink: '/settings',
            },
        ]
    }

    randomLogoFont() {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 3) + 1)
    }
}
