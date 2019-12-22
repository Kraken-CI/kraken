import { Component } from '@angular/core';

import {PanelMenuModule} from 'primeng/panelmenu';
import {MenuModule} from 'primeng/menu';
import {MenuItem} from 'primeng/api';
import {SplitButtonModule} from 'primeng/splitbutton';
import {MultiSelectModule} from 'primeng/multiselect';
import {ToastModule} from 'primeng/toast';

import { environment } from './../environments/environment'

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.sass']
})
export class AppComponent {
    title = 'Kraken';
    logoClass = "logo1";
    krakenVersion = '0.4'

    topMenuItems: MenuItem[];
    sItems: MenuItem[];

    constructor() {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 9) + 1);
    }

    ngOnInit() {
        this.krakenVersion = environment.krakenVersion

        this.topMenuItems = [{
            label: 'Dashboard',
            icon: 'pi pi-pw pi-home',
            items: [{
                label: 'New',
                icon: 'pi pi-fw pi-plus',
                items: [
                    {label: 'User', icon: 'pi pi-fw pi-user-plus'},
                    {label: 'Filter', icon: 'pi pi-fw pi-filter'}
                ]
            }, {
                label: 'Open', icon: 'pi pi-fw pi-external-link'
            }, {
                separator: true
            }, {
                label: 'Quit', icon: 'pi pi-fw pi-times'
            }, {
                label: 'Edit',
                icon: 'pi pi-fw pi-pencil',
            }]
        }];
    }

    randomLogoFont() {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 3) + 1);
    }
}
